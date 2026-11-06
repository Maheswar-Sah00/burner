"""Tests for the node's scan driver helpers (burner/node/run_scan.py, bait.fill_env): fetch hardening,
.env setup from .env.example, and the steps.json entry (tail masking, real seconds, source/why).

  python -m pytest tests/test_run_scan.py
"""
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_scan", ROOT / "burner" / "node" / "run_scan.py")
run_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_scan)
import bait  # noqa: E402  (run_scan puts burner/node on sys.path)


def test_harden_fetch_removes_registry_overrides_and_restores_them():
    with tempfile.TemporaryDirectory() as d:
        proj, stash = Path(d, "p"), Path(d, "stash")
        (proj / "web").mkdir(parents=True)
        Path(proj, ".npmrc").write_text("registry=https://npm.evil.example/\n")
        Path(proj, "web", ".yarnrc.yml").write_text("npmRegistryServer: https://evil.example\n")
        Path(proj, "requirements.txt").write_text("flask==3.0\n--extra-index-url https://pypi.evil.example/simple\n"
                                                  "  -i https://x.example\nrequests\n")
        removed, restore = run_scan.harden_fetch(str(proj), str(stash))
        assert set(removed) == {".npmrc", "web/.yarnrc.yml",
                                "requirements.txt: --extra-index-url https://pypi.evil.example/simple",
                                "requirements.txt: -i https://x.example"}
        assert not Path(proj, ".npmrc").exists() and not Path(proj, "web", ".yarnrc.yml").exists()
        assert Path(proj, "requirements.txt").read_text() == "flask==3.0\nrequests\n"
        restore()   # the detonation sees the repo as the candidate would
        assert Path(proj, ".npmrc").read_text().startswith("registry=")
        assert "--extra-index-url" in Path(proj, "requirements.txt").read_text()


def test_fill_env_from_example_with_bait_for_secrets():
    with tempfile.TemporaryDirectory() as d:
        Path(d, ".env.example").write_text(
            "# config\nPORT=\nNODE_ENV=development\nMONGO_URI=mongodb+srv://<user>:<password>@cluster0.example/db\n"
            "JWT_SECRET=your_jwt_secret\nJWT_EXPIRATION_MINUTES=30\nSTRIPE_SECRET_KEY=\n"
            "export EMAIL_PASSWORD=\"changeme\"\nAUTH_URL=http://localhost:3000\n")
        setup, toks = bait.fill_env(d, "projects/x")
        assert setup["from"] == ".env.example" and setup["keys"][:2] == ["PORT", "NODE_ENV"] and len(setup["keys"]) == 8
        env = Path(d, ".env").read_text()
        assert "PORT=3000" in env and "NODE_ENV=development" in env and "mongodb://127.0.0.1:27017/app" in env
        assert "JWT_EXPIRATION_MINUTES=30" in env and "AUTH_URL=http://localhost:3000" in env and "# config" in env
        assert {t["env_key"] for t in toks} == {"JWT_SECRET", "STRIPE_SECRET_KEY", "EMAIL_PASSWORD"}
        assert all(t["source"] == "env" and t["value"] in env and len(t["value"]) >= 16 for t in toks)
        assert next(t for t in toks if t["env_key"] == "STRIPE_SECRET_KEY")["value"].startswith("sk_test_")
        assert setup["filled"] == 5


def test_fill_env_leaves_an_existing_env_alone():
    with tempfile.TemporaryDirectory() as d:
        Path(d, ".env").write_text("A=1\n")
        Path(d, ".env.example").write_text("A=\n")
        assert bait.fill_env(d, "projects/x") == (None, [])
        assert bait.fill_env(tempfile.gettempdir() + "/does-not-exist-burner", "p") == (None, [])


def test_setup_env_registers_bait_tokens():
    with tempfile.TemporaryDirectory() as d:
        home, out = Path(d, "home"), Path(d, "out")
        proj = home / "projects" / "x"
        proj.mkdir(parents=True)
        out.mkdir()
        Path(out, "tokens.json").write_text(json.dumps([{"kind": "k", "path": "p", "value": "v" * 20}]))
        Path(proj, ".env.sample").write_text("API_KEY=\n")
        setup = run_scan.setup_env(str(proj), str(home), str(out))
        toks = json.loads(Path(out, "tokens.json").read_text())
        assert setup["from"] == ".env.sample" and len(toks) == 2 and toks[1]["path"] == "projects/x/.env"
        assert json.loads(Path(out, "env_setup.json").read_text()) == setup


def test_step_result_masks_bait_and_records_secs_source_why():
    toks = [{"kind": "GitHub token", "path": ".git-credentials", "value": "ghp_BURNERFAKE0123456789"}]
    step = {"name": "npm run start", "cmd": "npm run start", "timeout": 45, "why": "the take-home asks you to start it"}
    so = "\n".join(f"log {i}" for i in range(40)) + "\ntoken ghp_BURNERFAKE0123456789 leaked\n"
    res = run_scan.step_result(step, 1, so, "boom\n", 100.0, 101.25, toks)
    assert res["secs"] == 1.25 and res["source"] == "default" and res["why"].startswith("the take-home")
    assert "ghp_BURNERFAKE" not in res["tail"] and "<bait:GitHub token>" in res["tail"]
    assert res["tail"].splitlines()[-1] == "boom" and len(res["tail"].splitlines()) == 20
    recruiter = run_scan.step_result({**step, "source": "recruiter"}, 0, "", "", 0, 1, toks)
    assert recruiter["source"] == "recruiter"
