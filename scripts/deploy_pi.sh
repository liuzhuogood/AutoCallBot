#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="${SERVICE_NAME:-autocallbot}"
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-$USER}}"

cd "$APP_DIR"

sudo apt update
sudo apt install -y \
  android-tools-adb \
  bluez \
  bluez-alsa-utils \
  bluez-tools \
  alsa-utils \
  ffmpeg \
  python3-venv

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

mkdir -p data/logs

sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF
[Unit]
Description=AutoCallBot
After=network-online.target bluetooth.service bluealsa.service
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/.venv/bin/uvicorn autocallbot.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"
sudo systemctl restart "${SERVICE_NAME}.service"
sudo systemctl status "${SERVICE_NAME}.service" --no-pager -l
