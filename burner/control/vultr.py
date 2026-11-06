"""Minimal Vultr API v2 client (stdlib only)."""
import ipaddress
import json
import os
import re
import sys
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


# ---- cloud firewall for burner VMs ---------------------------------------------------------------
# Vultr firewall groups filter INBOUND traffic only and are default-deny: anything without an accept rule
# is dropped (IPv4 and IPv6). Every scan/pool VM gets this group, so the only thing reachable from the
# internet is sshd, and only from the control plane (plus an optional dev CIDR); fakenet's 9999/5353 never
# are. It does nothing for OUTBOUND traffic: containing what the repo sends is still iptables + gVisor.
FIREWALL_DESC = "burner-scan"
CONTROL_IP = os.environ.get("BURNER_CONTROL_IP", "139.84.215.1")
FW_TTL = 600   # re-check the group's rules at most every 10 min (catches hand edits)
_fw = {"id": None, "at": 0.0}


def _warn(msg):
    print(f"!!! burner firewall: {msg}", file=sys.stderr, flush=True)


def ssh_allow_cidrs():
    """Sources allowed to reach tcp/22: the control VM, plus BURNER_SSH_ALLOW (comma-separated CIDRs/IPs)."""
    out = []
    for c in [CONTROL_IP, *os.environ.get("BURNER_SSH_ALLOW", "").split(",")]:
        c = c.strip()
        if not c:
            continue
        net = ipaddress.ip_network(c, strict=False)   # a bare IP becomes /32 (or /128)
        if net.prefixlen == 0:
            raise ValueError(f"refusing to open SSH to the whole internet ({c})")
        if net not in out:
            out.append(net)
    return out


def _is_ssh_rule(r):
    return r.get("protocol") == "tcp" and str(r.get("port")) == "22"


def ensure_firewall_group(force=False):
    """Id of the 'burner-scan' firewall group, creating it and its rules if needed (idempotent, cached).

    Rules: tcp/22 from each ssh_allow_cidrs() source. SSH rules for other sources are kept (the dev box and
    the control VM share the group with different BURNER_SSH_ALLOW); any rule that isn't tcp/22 is deleted.
    """
    if _fw["id"] and not force and time.time() - _fw["at"] < FW_TTL:
        return _fw["id"]
    groups = _call("GET", "/firewalls?per_page=500").get("firewall_groups", [])
    g = next((g for g in groups if g.get("description") == FIREWALL_DESC), None)
    gid = g["id"] if g else _call("POST", "/firewalls", {"description": FIREWALL_DESC})["firewall_group"]["id"]
    rules = _call("GET", f"/firewalls/{gid}/rules?per_page=500").get("firewall_rules", [])
    for r in rules:
        if not _is_ssh_rule(r):
            _warn(f"deleting unexpected rule {r.get('id')} ({r.get('protocol')} {r.get('port')} from "
                  f"{r.get('subnet')}/{r.get('subnet_size')}): only SSH may reach a burner VM")
            _call("DELETE", f"/firewalls/{gid}/rules/{r['id']}")
    have = {(r.get("subnet"), int(r.get("subnet_size", -1))) for r in rules if _is_ssh_rule(r)}
    for net in ssh_allow_cidrs():
        if (str(net.network_address), net.prefixlen) not in have:
            _call("POST", f"/firewalls/{gid}/rules", {
                "ip_type": "v4" if net.version == 4 else "v6", "protocol": "tcp", "port": "22",
                "subnet": str(net.network_address), "subnet_size": net.prefixlen,
                "notes": "burner: ssh from control plane" if str(net.network_address) == CONTROL_IP
                else "burner: ssh (BURNER_SSH_ALLOW)"})
    _fw.update(id=gid, at=time.time())
    return gid


def firewall_required():
    """Refuse to create an unfirewalled burner VM unless BURNER_FIREWALL_REQUIRED=0 (see create_instance)."""
    return os.environ.get("BURNER_FIREWALL_REQUIRED", "1") != "0"


def create_instance(label, region="blr", plan="vc2-2c-4gb", os_id=2284,
                    sshkey_id=None, snapshot_id=None, user_data=None, tags=None, firewall=True):
    """Create a VM. firewall=True (every burner scan/pool VM) attaches the 'burner-scan' firewall group.

    If the firewall can't be set up or attached, refuse to create (or keep) the VM: a box running hostile
    code that is reachable from the internet is worse than a failed scan, which the pool simply retries.
    BURNER_FIREWALL_REQUIRED=0 downgrades that to a loud warning (emergency switch if the firewall API is
    down mid-demo; the VM still has ufw + iptables, and fakenet binds only to the sandbox bridge).
    """
    body = {"region": region, "plan": plan, "label": label,
            "backups": "disabled", "tags": tags or ["burner"]}
    fw = None
    if firewall:
        try:
            fw = ensure_firewall_group()
            body["firewall_group_id"] = fw
        except Exception as e:
            if firewall_required():
                raise RuntimeError(f"refusing to create {label} without its cloud firewall: {e}") from e
            _warn(f"could not set up the firewall group ({e}); creating {label} WITHOUT it "
                  "(BURNER_FIREWALL_REQUIRED=0)")
    if snapshot_id:
        body["snapshot_id"] = snapshot_id
    else:
        body["os_id"] = os_id
    if sshkey_id:
        body["sshkey_id"] = [sshkey_id]
    if user_data:
        import base64
        body["user_data"] = base64.b64encode(user_data.encode()).decode()
    inst = _call("POST", "/instances", body)["instance"]
    if fw and inst.get("firewall_group_id") != fw:
        try:   # the create call didn't take it: attach before anything is uploaded to the VM
            _call("PATCH", f"/instances/{inst['id']}", {"firewall_group_id": fw})
            inst["firewall_group_id"] = fw
        except Exception as e:
            if firewall_required():
                delete_instance(inst["id"])
                raise RuntimeError(f"firewall group would not attach to {inst['id']}; VM deleted: {e}") from e
            _warn(f"firewall group would not attach to {inst['id']} ({e}); continuing WITHOUT it")
    return inst


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
