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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    sys.exit(0)
