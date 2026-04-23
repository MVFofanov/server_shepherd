#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage:"
  echo "  ./server_shepherd/set_config_and_telegram.sh <project_dir> server_id=<id> telegram_bot_token=<token> chat_id=<id> [website_url=<url>] [message_mode=privacy_first|middle]"
  echo
  echo "Example:"
  echo "  ./server_shepherd/set_config_and_telegram.sh . server_id=server_1 telegram_bot_token=super_secret chat_id=123456"
}

if [[ $# -lt 4 ]]; then
  usage
  exit 1
fi

PROJECT_DIR="$1"
shift
PROJECT_DIR="$(cd "${PROJECT_DIR}" && pwd)"

SERVER_ID=""
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""
WEBSITE_URL=""
MESSAGE_MODE="privacy_first"

for arg in "$@"; do
  case "${arg}" in
    server_id=*) SERVER_ID="${arg#server_id=}" ;;
    telegram_bot_token=*) TELEGRAM_BOT_TOKEN="${arg#telegram_bot_token=}" ;;
    chat_id=*) TELEGRAM_CHAT_ID="${arg#chat_id=}" ;;
    website_url=*) WEBSITE_URL="${arg#website_url=}" ;;
    message_mode=*) MESSAGE_MODE="${arg#message_mode=}" ;;
    *)
      echo "Unknown argument: ${arg}"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${SERVER_ID}" ]]; then
  echo "Missing required argument: server_id=<id>"
  exit 1
fi

if [[ -z "${TELEGRAM_BOT_TOKEN}" ]]; then
  echo "Missing required argument: telegram_bot_token=<token>"
  exit 1
fi

if [[ -z "${TELEGRAM_CHAT_ID}" ]]; then
  echo "Missing required argument: chat_id=<id>"
  exit 1
fi

if [[ "${MESSAGE_MODE}" != "privacy_first" && "${MESSAGE_MODE}" != "middle" ]]; then
  echo "message_mode must be 'privacy_first' or 'middle'."
  exit 1
fi

CONFIG_FILE="${PROJECT_DIR}/config.toml"
ENV_FILE="${PROJECT_DIR}/server_shepherd.env"
BASHRC_FILE="${HOME}/.bashrc"

cat > "${CONFIG_FILE}" <<EOF
[agent]
server_id = "${SERVER_ID}"
interval_minutes = 10
output_path = "./data/metrics.jsonl"
disk_path = "/"
cpu_sample_seconds = 1.0

[privacy]
message_mode = "${MESSAGE_MODE}"

[privacy.traffic_mb]
medium = 5.0
high = 20.0
very_high = 100.0

[telegram]
enabled = true
chat_id_env = "SERVER_SHEPHERD_TELEGRAM_CHAT_ID"
bot_token_env = "SERVER_SHEPHERD_TELEGRAM_BOT_TOKEN"
send_on_regular_check = false
send_on_daily_report = true

[report]
output_path = "./data/daily_metrics.jsonl"
default_window_hours = 24
EOF

if [[ -n "${WEBSITE_URL}" ]]; then
  cat >> "${CONFIG_FILE}" <<EOF

[website]
url = "${WEBSITE_URL}"
expected_status = 200
timeout_seconds = 5.0
EOF
fi

cat >> "${CONFIG_FILE}" <<'EOF'

[thresholds.cpu_percent]
warning = 70.0
critical = 90.0

[thresholds.memory_percent]
warning = 75.0
critical = 90.0

[thresholds.disk_percent]
warning = 80.0
critical = 90.0
EOF

cat > "${ENV_FILE}" <<EOF
SERVER_SHEPHERD_TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
SERVER_SHEPHERD_TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
EOF
chmod 600 "${ENV_FILE}"

touch "${BASHRC_FILE}"
sed -i '/^export SERVER_SHEPHERD_TELEGRAM_BOT_TOKEN=/d' "${BASHRC_FILE}"
sed -i '/^export SERVER_SHEPHERD_TELEGRAM_CHAT_ID=/d' "${BASHRC_FILE}"
echo "export SERVER_SHEPHERD_TELEGRAM_BOT_TOKEN=\"${TELEGRAM_BOT_TOKEN}\"" >> "${BASHRC_FILE}"
echo "export SERVER_SHEPHERD_TELEGRAM_CHAT_ID=\"${TELEGRAM_CHAT_ID}\"" >> "${BASHRC_FILE}"

export SERVER_SHEPHERD_TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
export SERVER_SHEPHERD_TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}"

echo "Wrote:"
echo "  ${CONFIG_FILE}"
echo "  ${ENV_FILE}"
echo
echo "Current shell variables exported for this script process."
echo "For your current interactive shell, run:"
echo "  source ~/.bashrc"
echo
echo "Test commands:"
echo "  python -m server_shepherd.agent --config config.toml --once"
echo "  python -m server_shepherd.agent --config config.toml --daily-report --no-save"
