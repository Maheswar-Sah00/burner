"""Warm pool of pre-armed burner VMs.

Measured on Vultr (blr, vc2-2c-4gb): a fresh Ubuntu VM is ready in ~30-45 s, arming it
(docker + gVisor + sandbox image) takes ~2 min, and booting from a snapshot took 437 s.
So we keep N VMs already armed. A scan claims one, uses it once, and destroys it;
the pool immediately arms a replacement. One VM per scan is preserved.
"""
import threading
import time

from . import vultr

POOL_TAG = "burner-pool"
_lock = threading.Lock()


def _arm(iid, log):
    from .scan import NODE_DIR, ssh, tar_dirs, wait_ssh
    inst = vultr.wait_ready(iid)
    host = inst["main_ip"]
    wait_ssh(host)
    ssh(host, "rm -rf /scan && mkdir -p /scan && tar -xzf - -C /scan", input_bytes=tar_dirs([(NODE_DIR, "burner")]))
    p = ssh(host, "bash /scan/burner/setup.sh > /scan/setup.log 2>&1 && touch /scan/ARMED", timeout=900)
    if p.returncode:
        raise RuntimeError("arming failed")
    vultr._call("PATCH", f"/instances/{iid}", {"tags": [POOL_TAG, "armed"]})
    log(f"pool: {iid[:8]} armed at {host}")


def create_one(log=print, region="blr", plan="vc2-2c-4gb"):
    from .scan import KEY
    key_id = vultr.ensure_ssh_key(str(KEY) + ".pub")
    inst = vultr.create_instance(f"burner-pool-{int(time.time())}", region=region, plan=plan,
                                 sshkey_id=key_id, tags=[POOL_TAG, "arming"])
    log(f"pool: creating {inst['id'][:8]}")
    try:
        _arm(inst["id"], log)
    except Exception as e:
        log(f"pool: arming {inst['id'][:8]} failed ({e}); deleting")
        vultr.delete_instance(inst["id"])
        raise
    return inst["id"]


def claim():
    """Take an armed VM out of the pool (retagged as a scan VM so the reaper covers it)."""
    with _lock:
        for i in vultr.list_instances(POOL_TAG):
            if "armed" in i.get("tags", []):
                if not _firewalled(i):
                    continue
                # the claim time is what the reaper ages a scan VM by (it may have been armed hours ago)
                vultr._call("PATCH", f"/instances/{i['id']}", {"tags": ["burner-scan", f"claimed-{int(time.time())}"]})
                return i
    return None


def _firewalled(i):
    """A pool VM armed before the cloud firewall existed gets it attached before it runs anything.
    If that fails (and the firewall is required) the VM is deleted; the pool refills with a firewalled one."""
    try:
        fw = vultr.ensure_firewall_group()
        if i.get("firewall_group_id") != fw:
            vultr._call("PATCH", f"/instances/{i['id']}", {"firewall_group_id": fw})
            i["firewall_group_id"] = fw
        return True
    except Exception as e:
        if not vultr.firewall_required():
            vultr._warn(f"pool VM {i['id'][:8]} has no firewall ({e}); using it anyway (BURNER_FIREWALL_REQUIRED=0)")
            return True
        vultr._warn(f"pool VM {i['id'][:8]}: firewall would not attach ({e}); deleting it")
        vultr.delete_instance(i["id"])
        return False


def maintain(size=1, log=print, interval=20):
    """Background loop: keep `size` VMs armed or arming."""
    while True:
        try:
            have = len(vultr.list_instances(POOL_TAG))
            for _ in range(max(0, size - have)):
                threading.Thread(target=create_one, kwargs={"log": log}, daemon=True).start()
        except Exception as e:
            log(f"pool: {e}")
        time.sleep(interval)
