#!/usr/bin/env python3
"""Plant fake secrets (honeytokens) in a fake developer home directory.

Every value is random and unique to this scan, so if any of it shows up in
captured network traffic we know exactly what was stolen.

  bait.py HOME_DIR TOKENS_JSON
"""
import base64
import json
import os
import secrets
import sqlite3
import string
import sys


def rnd(n, alphabet=string.ascii_letters + string.digits):
    return "".join(secrets.choice(alphabet) for _ in range(n))


def write(path, content, mode=0o600):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(content, bytes) else "w") as f:
        f.write(content)
    os.chmod(path, mode)


def main(home, tokens_path):
    T = []   # {"kind","path","value","severity"}

    def tok(kind, path, value, severity="high"):
        T.append({"kind": kind, "path": path, "value": value, "severity": severity})
        return value

    # --- cloud credentials
    akid = tok("AWS access key", ".aws/credentials", "AKIA" + rnd(16, string.ascii_uppercase + "234567"))
    asec = tok("AWS secret key", ".aws/credentials", rnd(40, string.ascii_letters + string.digits + "+/"))
    write(f"{home}/.aws/credentials",
          f"[default]\naws_access_key_id = {akid}\naws_secret_access_key = {asec}\nregion = ap-south-1\n")
    write(f"{home}/.aws/config", "[default]\nregion = ap-south-1\noutput = json\n")

    # --- SSH private key (random bytes in a real-looking OpenSSH envelope)
    blob = base64.b64encode(b"openssh-key-v1\x00" + secrets.token_bytes(380)).decode()
    ssh_marker = tok("SSH private key", ".ssh/id_ed25519", blob[20:68])   # within the first 70-char line
    body = "\n".join(blob[i:i + 70] for i in range(0, len(blob), 70))
    write(f"{home}/.ssh/id_ed25519",
          f"-----BEGIN OPENSSH PRIVATE KEY-----\n{body}\n-----END OPENSSH PRIVATE KEY-----\n")
    write(f"{home}/.ssh/id_ed25519.pub", f"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI{rnd(43)} dev@laptop\n", 0o644)
    write(f"{home}/.ssh/known_hosts", "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl\n", 0o644)

    # --- developer tokens
    gh = tok("GitHub token", ".git-credentials", "ghp_" + rnd(36))
    write(f"{home}/.git-credentials", f"https://dev:{gh}@github.com\n")
    write(f"{home}/.gitconfig", "[user]\n\tname = Dev\n\temail = dev@example.com\n[credential]\n\thelper = store\n", 0o644)
    npm = tok("npm token", ".npmrc", "npm_" + rnd(36), "medium")   # npm itself reads .npmrc
    write(f"{home}/.npmrc", f"//registry.npmjs.org/:_authToken={npm}\n")

    # --- another project's .env (reading this is never needed by the take-home)
    stripe = tok("Stripe key", "work/client-api/.env", "sk_live_" + rnd(24))
    openai = tok("OpenAI key", "work/client-api/.env", "sk-proj-" + rnd(48))
    dburl = tok("Database password", "work/client-api/.env", rnd(20))
    write(f"{home}/work/client-api/.env",
          f"STRIPE_SECRET_KEY={stripe}\nOPENAI_API_KEY={openai}\nDATABASE_URL=postgres://admin:{dburl}@db.internal:5432/prod\n")

    # --- crypto wallets
    sol = tok("Solana wallet", ".config/solana/id.json", json.dumps([secrets.randbelow(256) for _ in range(64)]))
    write(f"{home}/.config/solana/id.json", sol)
    seed_words = " ".join(secrets.choice(["abandon", "orbit", "velvet", "canyon", "lunar", "bridge", "mango",
                                          "quartz", "harbor", "pixel", "ember", "falcon"]) for _ in range(12))
    exodus = tok("Exodus wallet", ".config/Exodus/exodus.wallet/seed.seco", "SECO" + rnd(60))
    write(f"{home}/.config/Exodus/exodus.wallet/seed.seco", exodus.encode() + secrets.token_bytes(200))
    mm_dir = f"{home}/.config/google-chrome/Default/Local Extension Settings/nkbihfbeogaeaoehlefnkodbefgpgknn"
    vault_salt = tok("MetaMask vault", "chrome MetaMask extension", rnd(44))
    write(f"{mm_dir}/000003.log",
          json.dumps({"vault": json.dumps({"data": rnd(400), "iv": rnd(24), "salt": vault_salt})}))
    tok("Wallet seed phrase", "Documents/wallet-backup.txt", seed_words)
    write(f"{home}/Documents/wallet-backup.txt", f"metamask backup\n{seed_words}\n")

    # --- browser saved passwords (Chrome "Login Data" sqlite)
    pw = tok("Browser saved password", "chrome Login Data", "Pw!" + rnd(17))
    ld = f"{home}/.config/google-chrome/Default/Login Data"
    os.makedirs(os.path.dirname(ld), exist_ok=True)
    db = sqlite3.connect(ld)
    db.execute("CREATE TABLE logins (origin_url TEXT, username_value TEXT, password_value BLOB)")
    db.execute("INSERT INTO logins VALUES (?,?,?)", ("https://accounts.binance.com/", "dev@example.com", pw.encode()))
    db.commit()
    db.close()

    # --- token exported in the login profile: every step runs in a login shell, so it is in the
    #     environment of everything the repo starts (stealers often dump process.env / os.environ)
    envtok = tok("GitHub token (shell environment)", ".profile", "ghp_" + rnd(36))
    write(f"{home}/.profile", f"# ~/.profile\nexport GITHUB_TOKEN={envtok}\nexport EDITOR=vim\n", 0o644)

    # --- shell history with a pasted secret
    hist = tok("Secret in shell history", ".bash_history", "xoxb-" + rnd(30), "medium")
    write(f"{home}/.bash_history", f"cd work/client-api\nexport SLACK_TOKEN={hist}\nnpm run dev\ngit push\n")

    os.system(f"chown -R 1000:1000 '{home}'")
    with open(tokens_path, "w") as f:
        json.dump(T, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
