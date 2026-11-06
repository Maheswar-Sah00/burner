#!/usr/bin/env python3
"""Plant fake secrets (honeytokens) in a fake developer home directory.

Every value is random and unique to this scan, so if any of it shows up in
captured network traffic we know exactly what was stolen.

  bait.py HOME_DIR TOKENS_JSON
"""
import base64
import json
import os
import re
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


# --- the project's own .env, made from its .env.example so the app gets far enough to start. Secret-looking keys
#     get unique bait values (registered in tokens.json) so stealing them is detected like any other bait.
ENV_EXAMPLES = (".env.example", ".env.sample", ".env.template", ".env.local.example")
SECRET_KEY = re.compile(r"(?i)secret|token|passw|pwd|api_?key|private|access_?key|credential|salt|signing|webhook|"
                        r"(?:^|_)(?:key|auth)$|_key_|dsn$")
NOT_SECRET_VALUE = re.compile(r"(?i)^(?:\d+[smhdwy]?|true|false|yes|no|on|off|https?://\S+|\$\{.*\}|\$\w+)$")
PLACEHOLDER = re.compile(r"(?i)^$|<[^>]*>|\[[^\]]*\]|\{\{.*\}\}|^x{3,}$|^\*{3,}$|^\.{3}$|change[_-]?(?:me|this)|"
                         r"\byour[_\s-]|^your|replace[_\s-]?(?:me|this|with)|^(?:todo|tbd|placeholder|null|none|undefined|"
                         r"secret|password|example|dummy|test|xxx.*|\.\.\.)$|insert[_\s-]|^put[_\s-]|^enter[_\s-]")
ENV_LINE = re.compile(r"^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_.]*)(\s*=\s*)(.*?)\s*$")


def env_secret(key):
    """A bait value shaped like what KEY usually holds (a Stripe key looks like a Stripe key)."""
    k = key.upper()
    if "STRIPE" in k:
        return ("pk_test_" if "PUBLISHABLE" in k or "PUBLIC" in k else "sk_test_") + rnd(24)
    if "OPENAI" in k:
        return "sk-proj-" + rnd(48)
    if "ANTHROPIC" in k:
        return "sk-ant-api03-" + rnd(40)
    if "GITHUB" in k or k.startswith("GH_"):
        return "ghp_" + rnd(36)
    if "SLACK" in k:
        return "xoxb-" + rnd(30)
    if "AWS" in k and "ACCESS" in k:
        return "AKIA" + rnd(16, string.ascii_uppercase + "234567")
    if "AWS" in k:
        return rnd(40)
    if "PASSW" in k or "PWD" in k:
        return "Pw" + rnd(18)
    return rnd(32)


def env_plain(key):
    """A plausible, harmless value for a non-secret placeholder (PORT, MONGO_URI, ...)."""
    k = key.upper()
    if k.endswith("PORT"):
        return "3000"
    if "MONGO" in k:
        return "mongodb://127.0.0.1:27017/app"
    if "REDIS" in k:
        return "redis://127.0.0.1:6379"
    if "MYSQL" in k:
        return "mysql://app:app@127.0.0.1:3306/app"
    if "POSTGRES" in k or "DATABASE" in k or k.startswith("PG") or k.startswith("DB_URL"):
        return "postgresql://app:app@127.0.0.1:5432/app"
    if k.endswith(("_URL", "_URI")) or k in ("URL", "URI"):
        return "http://localhost:3000"
    if "EMAIL" in k or k.endswith("_FROM"):
        return "dev@example.com"
    if k.endswith("HOST"):
        return "localhost"
    if k.endswith(("USER", "USERNAME")):
        return "dev"
    if k in ("NODE_ENV", "ENV", "APP_ENV", "FLASK_ENV"):
        return "development"
    return "dev"


def fill_env(project, rel_project):
    """If PROJECT has no .env but has an example one, write .env from it.

    -> (env_setup dict or None, [bait token entries]). rel_project is the project's path under the fake home.
    """
    if os.path.lexists(os.path.join(project, ".env")):
        return None, []
    src = next((n for n in ENV_EXAMPLES if os.path.isfile(os.path.join(project, n))
                and not os.path.islink(os.path.join(project, n))), None)
    if not src:
        return None, []
    with open(os.path.join(project, src), encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    keys, tokens, filled, out = [], [], 0, []
    for ln in lines:
        m = ENV_LINE.match(ln)
        if not m or ln.lstrip().startswith("#"):
            out.append(ln)
            continue
        pre, key, eq, raw = m.groups()
        value = raw
        if value[:1] in "\"'" and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].strip()
        keys.append(key)
        new = None
        if SECRET_KEY.search(key) and not NOT_SECRET_VALUE.match(value):
            new = env_secret(key)
            tokens.append({"kind": f"{key} (project .env)", "path": f"{rel_project}/.env", "value": new,
                           "severity": "medium", "source": "env", "env_key": key})
        elif PLACEHOLDER.search(value):
            new = env_plain(key)
        if new is None:
            out.append(ln)
        else:
            filled += 1
            out.append(f"{pre}{key}{eq.strip()}{new}")
    write(os.path.join(project, ".env"), "\n".join(out) + "\n", 0o644)
    return {"from": src, "keys": keys, "filled": filled}, tokens


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

    # --- AI developer tools. Fake MCP servers and AI-tool repos target these (FakeGit, Island Jul 2026: 800+ repos
    #     posing as MCP servers / AI skills; typosquatted MCP packages that register a rogue server in Claude
    #     Desktop / Cursor configs). Sending the Hugging Face token to huggingface.co is what huggingface_hub does,
    #     so "service" marks the hosts where that is expected (detect.py: worth a look, not a verdict).
    hf = tok("Hugging Face token", ".cache/huggingface/token", "hf_" + rnd(34))   # reading it: medium (detect.py)
    hf_entry = T[-1]
    hf_entry["service"] = ["huggingface.co", "hf.co"]
    write(f"{home}/.cache/huggingface/token", hf)
    mcp_gh = tok("MCP server token (Claude Desktop config)", ".config/Claude/claude_desktop_config.json",
                 "github_pat_" + rnd(22) + "_" + rnd(59))
    write(f"{home}/.config/Claude/claude_desktop_config.json", json.dumps({"mcpServers": {
        "github": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"],
                   "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": mcp_gh}},
        "filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/dev/work"]}}},
        indent=2))
    mcp_sb = tok("MCP server token (Cursor config)", ".cursor/mcp.json", "sbp_" + rnd(40, string.hexdigits.lower()[:16]))
    write(f"{home}/.cursor/mcp.json", json.dumps({"mcpServers": {
        "supabase": {"command": "npx", "args": ["-y", "@supabase/mcp-server-supabase@latest", "--read-only"],
                     "env": {"SUPABASE_ACCESS_TOKEN": mcp_sb}}}}, indent=2))

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
    write(f"{home}/.profile", f"# ~/.profile\nexport GITHUB_TOKEN={envtok}\nexport EDITOR=vim\n"
          'export PATH="$HOME/.pyenv/shims:$HOME/.local/bin:$PATH"\n', 0o644)

    # --- toolchain folders on PATH, like a real dev laptop (what a swapped-binary attack overwrites; see
    #     BINARY_SWAP in detect.py). The shim is harmless: it only prints a version.
    write(f"{home}/.pyenv/shims/pyenv", '#!/usr/bin/env bash\n# pyenv shim\nset -e\necho "pyenv 2.4.17"\n', 0o755)
    os.makedirs(f"{home}/.local/bin", exist_ok=True)

    # --- this laptop's name and user. The hostname is unique per scan so FINGERPRINT (detect.py) can recognise
    #     it in captured traffic; realistic "user-model" shape so it does not look like a sandbox.
    model = secrets.choice(["thinkpad-t14s", "xps-9530", "framework-13", "zenbook-ux3405", "precision-5570"])
    identity = {"hostname": f"dev-{model}-{rnd(4, string.ascii_lowercase + string.digits)}", "username": "dev"}
    with open(os.path.join(os.path.dirname(os.path.abspath(tokens_path)), "identity.json"), "w") as f:
        json.dump(identity, f)

    # --- shell history with a pasted secret
    hist = tok("Secret in shell history", ".bash_history", "xoxb-" + rnd(30), "medium")
    write(f"{home}/.bash_history", f"cd work/client-api\nexport SLACK_TOKEN={hist}\nnpm run dev\ngit push\n")

    os.system(f"chown -R 1000:1000 '{home}'")
    with open(tokens_path, "w") as f:
        json.dump(T, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
