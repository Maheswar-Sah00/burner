"""Deploy/update the Burner control plane (web app) on a small always-on Vultr VM.

  python deploy/deploy.py
"""
import io
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from burner.control import vultr  # noqa: E402
from burner.control.scan import SSH_OPTS, KEY, wait_ssh  # noqa: E402

LABEL = "burner-control"


def bundle():
    buf = io.BytesIO()
    skip = ("node_modules", "__pycache__", ".git")
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for p in ("burner", "samples", "deploy", ".env", ".burner"):
            if (ROOT / p).exists():
                t.add(ROOT / p, arcname=p, filter=lambda ti: None if any(s in ti.name for s in skip) else ti)
    return buf.getvalue()


def main():
    inst = next((i for i in vultr.list_instances("burner-control")), None)
    if not inst:
        key_id = vultr.ensure_ssh_key(str(KEY) + ".pub")
        print("creating control VM")
        inst = vultr.create_instance(LABEL, region="blr", plan="vc2-1c-2gb", sshkey_id=key_id, tags=["burner-control"])
        inst = vultr.wait_ready(inst["id"])
    ip = inst["main_ip"]
    domain = ip.replace(".", "-") + ".sslip.io"
    wait_ssh(ip)
    print(f"uploading to {ip}")
    ssh = ["ssh", *SSH_OPTS, f"root@{ip}"]
    subprocess.run(ssh + ["mkdir -p /opt/burner-app && rm -rf /opt/burner-app/src.new && mkdir /opt/burner-app/src.new "
                          "&& tar -xzf - -C /opt/burner-app/src.new "
                          # keep stored scans (share links /r/<id> and evidence) across deploys
                          "&& { [ ! -d /opt/burner-app/src/scans ] || mv /opt/burner-app/src/scans /opt/burner-app/src.new/; } "
                          "&& rm -rf /opt/burner-app/src "
                          "&& mv /opt/burner-app/src.new /opt/burner-app/src"], input=bundle(), check=True)
    print("installing")
    subprocess.run(ssh + [f"bash /opt/burner-app/src/deploy/control_setup.sh {domain}"], check=True)
    print(f"\nlive at https://{domain}")


if __name__ == "__main__":
    main()
