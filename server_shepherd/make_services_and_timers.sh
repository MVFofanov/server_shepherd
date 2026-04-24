#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run this script with sudo."
  echo "Example: sudo ./server_shepherd/make_services_and_timers.sh ."
  exit 1
fi

PROJECT_DIR="${1:-.}"
PROJECT_DIR="$(cd "${PROJECT_DIR}" && pwd)"

RUN_USER="${SUDO_USER:-$(id -un)}"
if [[ "${RUN_USER}" == "root" ]]; then
  echo "Could not detect the non-root user. Run with sudo from your normal user account."
  exit 1
fi

PYTHON_BIN="${PROJECT_DIR}/server_shepherd_env/bin/python"
CONFIG_FILE="${PROJECT_DIR}/config.toml"
ENV_FILE="${PROJECT_DIR}/server_shepherd.env"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python executable not found or not executable: ${PYTHON_BIN}"
  echo "Create the virtual environment first:"
  echo "  python3 -m venv server_shepherd_env"
  exit 1
fi

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Config file not found: ${CONFIG_FILE}"
  echo "Create it first:"
  echo "  cp config.example.toml config.toml"
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Environment file not found: ${ENV_FILE}"
  echo "Create it first with your Telegram bot token, for example:"
  echo "  SERVER_SHEPHERD_TELEGRAM_BOT_TOKEN=your_real_bot_token_here"
  exit 1
fi

cat > /etc/systemd/system/server-shepherd-collect.service <<EOF
[Unit]
Description=Server Shepherd metric collection

[Service]
Type=oneshot
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${PYTHON_BIN} -m server_shepherd.agent --config ${CONFIG_FILE} --once
EOF

cat > /etc/systemd/system/server-shepherd-collect.timer <<EOF
[Unit]
Description=Run Server Shepherd collection every 10 minutes

[Timer]
OnCalendar=*:0/10
Persistent=true
Unit=server-shepherd-collect.service

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/server-shepherd-report.service <<EOF
[Unit]
Description=Server Shepherd daily report

[Service]
Type=oneshot
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${PYTHON_BIN} -m server_shepherd.agent --config ${CONFIG_FILE} --daily-report
EOF

cat > /etc/systemd/system/server-shepherd-plot.service <<EOF
[Unit]
Description=Server Shepherd daily traffic plot

[Service]
Type=oneshot
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${PYTHON_BIN} -m server_shepherd.plot_daily_traffic --previous-day --input ${PROJECT_DIR}/data/metrics.jsonl --output-dir ${PROJECT_DIR}/figures --timezone Europe/Berlin
EOF

cat > /etc/systemd/system/server-shepherd-report.timer <<EOF
[Unit]
Description=Run Server Shepherd daily report at 09:00 Berlin time

[Timer]
OnCalendar=*-*-* 09:00:00 Europe/Berlin
Persistent=true
Unit=server-shepherd-report.service

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/server-shepherd-plot.timer <<EOF
[Unit]
Description=Run Server Shepherd daily traffic plot at 00:10 Berlin time

[Timer]
OnCalendar=*-*-* 00:10:00 Europe/Berlin
Persistent=true
Unit=server-shepherd-plot.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now server-shepherd-collect.timer
systemctl enable --now server-shepherd-plot.timer
systemctl enable --now server-shepherd-report.timer

if systemctl list-unit-files server-shepherd.timer >/dev/null 2>&1; then
  systemctl disable --now server-shepherd.timer >/dev/null 2>&1 || true
fi

echo
echo "Installed Server Shepherd systemd units for:"
echo "  Project directory: ${PROJECT_DIR}"
echo "  Run user: ${RUN_USER}"
echo
echo "Timers:"
systemctl list-timers --all | grep server-shepherd || true
echo
echo "Useful checks:"
echo "  systemctl status server-shepherd-collect.timer"
echo "  systemctl status server-shepherd-plot.timer"
echo "  systemctl status server-shepherd-report.timer"
echo "  systemctl status server-shepherd-collect.service"
echo "  systemctl status server-shepherd-plot.service"
echo "  systemctl status server-shepherd-report.service"
echo "  journalctl -u server-shepherd-collect.service -n 50 --no-pager"
echo "  journalctl -u server-shepherd-plot.service -n 50 --no-pager"
echo "  journalctl -u server-shepherd-report.service -n 50 --no-pager"
