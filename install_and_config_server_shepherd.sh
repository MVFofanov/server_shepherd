#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage:"
  echo "  ./install_and_config_server_shepherd.sh server_id=<id> telegram_bot_token=<token> chat_id=<id> [install_dir=<dir>] [repo_url=<url>] [website_url=<url>] [message_mode=middle|privacy_first]"
  echo
  echo "Example:"
  echo "  ./install_and_config_server_shepherd.sh server_id=server_3 telegram_bot_token=your_bot_token_here chat_id=your_chat_id_here"
}

SERVER_ID=""
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "${SCRIPT_DIR}/.git" ]]; then
  INSTALL_DIR="${SCRIPT_DIR}"
else
  INSTALL_DIR="${HOME}/server_shepherd"
fi
REPO_URL="https://github.com/MVFofanov/server_shepherd.git"
WEBSITE_URL=""
MESSAGE_MODE="middle"

for arg in "$@"; do
  case "${arg}" in
    server_id=*) SERVER_ID="${arg#server_id=}" ;;
    telegram_bot_token=*) TELEGRAM_BOT_TOKEN="${arg#telegram_bot_token=}" ;;
    chat_id=*) TELEGRAM_CHAT_ID="${arg#chat_id=}" ;;
    install_dir=*) INSTALL_DIR="${arg#install_dir=}" ;;
    repo_url=*) REPO_URL="${arg#repo_url=}" ;;
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
  usage
  exit 1
fi

if [[ -z "${TELEGRAM_BOT_TOKEN}" ]]; then
  echo "Missing required argument: telegram_bot_token=<token>"
  usage
  exit 1
fi

if [[ -z "${TELEGRAM_CHAT_ID}" ]]; then
  echo "Missing required argument: chat_id=<id>"
  usage
  exit 1
fi

if [[ "${MESSAGE_MODE}" != "privacy_first" && "${MESSAGE_MODE}" != "middle" ]]; then
  echo "message_mode must be 'privacy_first' or 'middle'."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required. Install it first, for example:"
  echo "  sudo apt update && sudo apt install git"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install it first."
  exit 1
fi

if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
  mkdir -p "$(dirname "${INSTALL_DIR}")"
  git clone "${REPO_URL}" "${INSTALL_DIR}"
else
  git -C "${INSTALL_DIR}" pull --ff-only
fi

SETUP_ARGS=(
  "${INSTALL_DIR}"
  "server_id=${SERVER_ID}"
  "telegram_bot_token=${TELEGRAM_BOT_TOKEN}"
  "chat_id=${TELEGRAM_CHAT_ID}"
  "message_mode=${MESSAGE_MODE}"
)

if [[ -n "${WEBSITE_URL}" ]]; then
  SETUP_ARGS+=("website_url=${WEBSITE_URL}")
fi

chmod +x "${INSTALL_DIR}/server_shepherd/set_config_and_telegram.sh"
"${INSTALL_DIR}/server_shepherd/set_config_and_telegram.sh" "${SETUP_ARGS[@]}"

chmod +x "${INSTALL_DIR}/server_shepherd/make_services_and_timers.sh"
sudo "${INSTALL_DIR}/server_shepherd/make_services_and_timers.sh" "${INSTALL_DIR}"

echo
echo "Server Shepherd installation complete."
echo "Project directory: ${INSTALL_DIR}"
echo
echo "Run this once in your current shell if you want manual commands to see Telegram env vars:"
echo "  source ~/.bashrc"
echo
echo "Check timers:"
echo "  systemctl list-timers --all | grep server-shepherd"
echo
echo "Test commands:"
echo "  cd ${INSTALL_DIR}"
echo "  source server_shepherd_env/bin/activate"
echo "  python -m server_shepherd.agent --config config.toml --once"
echo "  python -m server_shepherd.agent --config config.toml --daily-report --no-save"
