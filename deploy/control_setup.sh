#!/usr/bin/env bash
# Runs ON the control VM. Installs/updates the Burner web app behind Caddy (HTTPS).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
APP=/opt/burner-app
DOMAIN="$1"

if ! command -v caddy >/dev/null; then
  apt-get update -y -q
  apt-get install -y -q python3-venv git caddy
fi
[ -d $APP/venv ] || python3 -m venv $APP/venv
$APP/venv/bin/pip install -q --upgrade fastapi "uvicorn[standard]" boto3 pydantic

chmod 600 $APP/src/.env $APP/src/.burner/id_ed25519

cat > /etc/systemd/system/burner-web.service <<UNIT
[Unit]
Description=Burner web app
After=network-online.target
[Service]
WorkingDirectory=$APP/src
EnvironmentFile=$APP/src/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=$APP/venv/bin/uvicorn burner.web.app:app --host 127.0.0.1 --port 8000
Restart=always
[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/burner-reaper.service <<UNIT
[Unit]
Description=Delete leftover Burner scan VMs
[Service]
Type=oneshot
WorkingDirectory=$APP/src
EnvironmentFile=$APP/src/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=$APP/venv/bin/python -c "from burner.control import vultr; print('reaped', vultr.reap(), vultr.reap_stuck_pool())"
UNIT
cat > /etc/systemd/system/burner-reaper.timer <<UNIT
[Unit]
Description=Run the Burner VM reaper every 5 minutes
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
UNIT

cat > /etc/caddy/Caddyfile <<CADDY
$DOMAIN {
  encode gzip
  reverse_proxy 127.0.0.1:8000 {
    flush_interval -1
  }
}
CADDY

ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
systemctl daemon-reload
systemctl enable --now burner-reaper.timer >/dev/null
systemctl enable burner-web >/dev/null
systemctl restart burner-web
systemctl reload caddy || systemctl restart caddy
sleep 2
systemctl is-active burner-web caddy
