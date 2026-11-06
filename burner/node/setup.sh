#!/usr/bin/env bash
# Prepares a fresh Ubuntu 24.04 Vultr VM to be a Burner detonation host.
# Idempotent: safe to re-run. Later baked into a Vultr snapshot.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
HERE="$(cd "$(dirname "$0")" && pwd)"

log() { echo "[setup] $*"; }

if ! command -v docker >/dev/null; then
  log "installing docker + tools"
  apt-get update -y -q
  apt-get install -y -q docker.io python3-cryptography git curl jq gnupg ca-certificates
fi

if ! command -v runsc >/dev/null; then
  log "installing gVisor (runsc)"
  curl -fsSL https://gvisor.dev/archive.key | gpg --dearmor --yes -o /usr/share/keyrings/gvisor-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" \
    > /etc/apt/sources.list.d/gvisor.list
  apt-get update -y -q
  apt-get install -y -q runsc
fi

log "configuring docker runtimes (runsc = isolate, runsc-trace = isolate + syscall log)"
mkdir -p /var/log/runsc
cat > /etc/docker/daemon.json <<'EOF'
{
  "runtimes": {
    "runsc": { "path": "/usr/bin/runsc" },
    "runsc-trace": {
      "path": "/usr/bin/runsc",
      "runtimeArgs": [
        "--strace",
        "--strace-syscalls=open,openat,creat,execve,execveat,connect,unlink,unlinkat,rename,renameat,renameat2,link,linkat,symlink,symlinkat,chmod,fchmod,fchmodat",
        "--debug",
        "--debug-log=/var/log/runsc/%ID%/"
      ]
    }
  }
}
EOF
systemctl restart docker

log "creating the burner network (no real internet)"
docker network inspect burnernet >/dev/null 2>&1 || \
  docker network create --driver bridge --subnet 10.77.0.0/24 --gateway 10.77.0.1 \
    -o com.docker.network.bridge.name=br-burner burnernet

# Fake internet: every TCP connection and DNS query from the sandbox is redirected
# to fakenet on the host. Nothing from br-burner is ever forwarded to the real internet.
apply_rules() {
  iptables -t nat -C PREROUTING -i br-burner -p udp -j DNAT --to-destination 10.77.0.1:5353 2>/dev/null || \
    iptables -t nat -I PREROUTING 1 -i br-burner -p udp -j DNAT --to-destination 10.77.0.1:5353
  iptables -t nat -C PREROUTING -i br-burner -p tcp -j DNAT --to-destination 10.77.0.1:9999 2>/dev/null || \
    iptables -t nat -I PREROUTING 1 -i br-burner -p tcp -j DNAT --to-destination 10.77.0.1:9999
  iptables -C DOCKER-USER -i br-burner -j DROP 2>/dev/null || iptables -I DOCKER-USER 1 -i br-burner -j DROP
  # Host services other than fakenet are unreachable from the sandbox.
  iptables -C INPUT -i br-burner -p tcp ! --dport 9999 -j DROP 2>/dev/null || \
    iptables -I INPUT 1 -i br-burner -p tcp ! --dport 9999 -j DROP
  iptables -C INPUT -i br-burner -p udp ! --dport 5353 -j DROP 2>/dev/null || \
    iptables -I INPUT 1 -i br-burner -p udp ! --dport 5353 -j DROP
  # ...but fakenet itself must be reachable (Vultr images ship ufw with INPUT policy DROP).
  iptables -C INPUT -i br-burner -p tcp --dport 9999 -j ACCEPT 2>/dev/null || \
    iptables -I INPUT 1 -i br-burner -p tcp --dport 9999 -j ACCEPT
  iptables -C INPUT -i br-burner -p udp --dport 5353 -j ACCEPT 2>/dev/null || \
    iptables -I INPUT 1 -i br-burner -p udp --dport 5353 -j ACCEPT
  ip6tables -C FORWARD -i br-burner -j DROP 2>/dev/null || ip6tables -I FORWARD 1 -i br-burner -j DROP || true
}
apply_rules

log "creating fake-internet certificate authority"
mkdir -p /opt/burner
if [ ! -f /opt/burner/ca.key ]; then
  python3 "$HERE/fakenet.py" --make-ca /opt/burner
fi

log "building sandbox image"
cp /opt/burner/ca.pem "$HERE/sandbox/burner-ca.crt"
docker build -q -t burner-sandbox "$HERE/sandbox"

log "ready"
