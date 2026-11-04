"""Minimal Vultr API v2 client (stdlib only)."""
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.vultr.com/v2"
ROOT = Path(__file__).resolve().parents[2]


def load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


load_env()


def _call(method, path, body=None):
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": "Bearer " + os.environ["VULTR_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Vultr {method} {path} -> {e.code}: {e.read().decode()[:300]}")


def ensure_ssh_key(pub_path, name="burner-dev"):
    pub = Path(pub_path).read_text().strip()
    for k in _call("GET", "/ssh-keys?per_page=100").get("ssh_keys", []):
        if k["ssh_key"].strip() == pub:
            return k["id"]
    return _call("POST", "/ssh-keys", {"name": name, "ssh_key": pub})["ssh_key"]["id"]


def create_instance(label, region="blr", plan="vc2-2c-4gb", os_id=2284,
                    sshkey_id=None, snapshot_id=None, user_data=None, tags=None):
    body = {"region": region, "plan": plan, "label": label,
            "backups": "disabled", "tags": tags or ["burner"]}
    if snapshot_id:
        body["snapshot_id"] = snapshot_id
    else:
        body["os_id"] = os_id
    if sshkey_id:
        body["sshkey_id"] = [sshkey_id]
    if user_data:
        import base64
        body["user_data"] = base64.b64encode(user_data.encode()).decode()
    return _call("POST", "/instances", body)["instance"]


def get_instance(iid):
    return _call("GET", f"/instances/{iid}")["instance"]


def wait_ready(iid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        i = get_instance(iid)
        if i["status"] == "active" and i["power_status"] == "running" and i["server_status"] == "ok":
            return i
        time.sleep(4)
    raise TimeoutError(f"instance {iid} not ready after {timeout}s")


def delete_instance(iid):
    """Delete a VM. Returns False if it was already gone (404): the goal, so never an error."""
    try:
        _call("DELETE", f"/instances/{iid}")
        return True
    except RuntimeError as e:
        if " -> 404:" in str(e):
            return False
        raise


def list_instances(tag="burner"):
    return _call("GET", f"/instances?per_page=100&tag={tag}").get("instances", [])


def create_snapshot(iid, description):
    return _call("POST", "/snapshots", {"instance_id": iid, "description": description})["snapshot"]


def get_snapshot(sid):
    return _call("GET", f"/snapshots/{sid}")["snapshot"]


def plan_hourly_cost(plan_id):
    for p in _call("GET", "/plans?type=all&per_page=500")["plans"]:
        if p["id"] == plan_id:
            return p["monthly_cost"] / 730.0
    return None


def reap(max_age_min=20, tag="burner-scan"):
    """Safety net: delete scan VMs that outlived any possible scan (crash, lost connection)."""
    import datetime
    killed = []
    now = datetime.datetime.now(datetime.timezone.utc)
    for i in list_instances(tag):
        # a warm-pool VM can sit armed for hours before a scan claims it: age a scan VM from its claim, not its boot
        claimed = next((int(t.split("-", 1)[1]) for t in i.get("tags", []) if re.fullmatch(r"claimed-\d+", t)), None)
        start = (datetime.datetime.fromtimestamp(claimed, datetime.timezone.utc) if claimed
                 else datetime.datetime.fromisoformat(i["date_created"]))
        if (now - start).total_seconds() > max_age_min * 60:
            delete_instance(i["id"])
            killed.append(i["id"])
    return killed


def reap_stuck_pool(max_arming_min=15, tag="burner-pool"):
    """Pool VMs still 'arming' long after boot (control plane restarted mid-arm): never armed, never reaped,
    and they fill pool slots so the pool stops refilling. Delete them."""
    import datetime
    killed = []
    now = datetime.datetime.now(datetime.timezone.utc)
    for i in list_instances(tag):
        if "armed" in i.get("tags", []):
            continue
        if (now - datetime.datetime.fromisoformat(i["date_created"])).total_seconds() > max_arming_min * 60:
            delete_instance(i["id"])
            killed.append(i["id"])
    return killed
