#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_HOST="${PI_HOST:-10.0.0.6}"
PI_USER="${PI_USER:-liuzhuo}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/home/${PI_USER}/AutoCallBot}"
SERVICE_NAME="${SERVICE_NAME:-autocallbot}"
INSTALL_EDITABLE="${INSTALL_EDITABLE:-0}"
DELETE_REMOTE="${DELETE_REMOTE:-0}"

SSH_TARGET="${PI_USER}@${PI_HOST}"
RSYNC_ARGS=(-az --progress --stats)
if [[ "${DELETE_REMOTE}" == "1" ]]; then
  RSYNC_ARGS+=(--delete)
fi

cd "$APP_DIR"

echo "Syncing ${APP_DIR}/ -> ${SSH_TARGET}:${REMOTE_APP_DIR}/"
rsync "${RSYNC_ARGS[@]}" \
  --exclude ".git/" \
  --exclude ".idea/" \
  --exclude ".venv/" \
  --exclude "*.egg-info/" \
  --exclude "__pycache__/" \
  --exclude ".pytest_cache/" \
  --exclude ".ruff_cache/" \
  --exclude "data/logs/" \
  --exclude ".DS_Store" \
  ./ "${SSH_TARGET}:${REMOTE_APP_DIR}/"

echo "Restarting ${SERVICE_NAME}.service on ${SSH_TARGET}"
ssh "${SSH_TARGET}" bash -s -- "${REMOTE_APP_DIR}" "${SERVICE_NAME}" "${INSTALL_EDITABLE}" <<'EOF'
set -euo pipefail

REMOTE_APP_DIR="$1"
SERVICE_NAME="$2"
INSTALL_EDITABLE="$3"

cd "$REMOTE_APP_DIR"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing ${REMOTE_APP_DIR}/.venv/bin/python. Run scripts/deploy_pi.sh once first." >&2
  exit 1
fi

if [[ "$INSTALL_EDITABLE" == "1" ]]; then
  .venv/bin/python -m pip install -e .
fi

sudo systemctl restart "${SERVICE_NAME}.service"

PORT="$(systemctl show "${SERVICE_NAME}.service" -p ExecStart --value | sed -n 's/.*--port \([0-9][0-9]*\).*/\1/p' | head -n 1)"
for _ in {1..15}; do
  systemctl is-active --quiet "${SERVICE_NAME}.service"
  if [[ -n "$PORT" ]]; then
    ss -ltn | grep -E "[:.]${PORT}[[:space:]]" >/dev/null && break
  else
    pgrep -f "uvicorn.*autocallbot.main" >/dev/null && break
  fi
  sleep 1
done

systemctl status "${SERVICE_NAME}.service" --no-pager -l
echo "Listening ports:"
if [[ -n "$PORT" ]]; then
  ss -ltnp 2>/dev/null | grep -E "[:.]${PORT}[[:space:]]" || true
else
  ss -ltnp 2>/dev/null | grep uvicorn || true
fi
EOF
