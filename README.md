# Server Shepherd

![Server Shepherd bot icon](images/server_shepherd_bot_icon.png)

Small first step for a privacy-first server monitoring project.

This MVP is intentionally narrow:

- runs locally on a Linux server
- reads CPU, RAM, disk, uptime, and load average
- can optionally check a website URL for HTTP status and response time
- appends snapshots to a JSON Lines file on disk
- can optionally send a Telegram message after each run
- uses a small TOML config file for changeable settings
- can run once for testing or stay in a 30-minute loop

## Why this is a good first step

It gives us a stable local agent and a stable output format before we add Telegram, a dashboard, or a collector API.

Each saved snapshot is already structured as JSON, so later we can:

- forward it to Telegram
- post it to an HTTP collector
- read it in a dashboard
- summarize it in a daily report

## Files

- `config.example.toml`: starter config
- `server_shepherd/agent.py`: entry point and scheduler loop
- `server_shepherd/config.py`: config loading
- `server_shepherd/metrics.py`: metric collection
- `server_shepherd/message_format.py`: privacy-aware Telegram message formatting
- `server_shepherd/storage.py`: JSONL persistence
- `server_shepherd/telegram_sender.py`: Telegram Bot API sender

## What it does now

Each server can:

- collect local metrics
- optionally check a website
- save snapshots into `data/metrics.jsonl`
- build a daily summary into `data/daily_metrics.jsonl`
- build daily traffic plots into `figures/YYYY-MM-DD.png`
- optionally send a Telegram message after each run or only for the daily report
- optionally send the traffic plot together with the daily report
- run on its own schedule with `systemd`

This works well for 2 or more servers sending updates to the same Telegram bot chat, even if they report at different times.

## Local run

1. Copy the config:

```sh
cp config.example.toml config.toml
```

2. Run one collection:

```sh
python3 -m server_shepherd.agent --config config.toml --once
```

3. Inspect the output file:

```sh
cat ./data/metrics.jsonl
```

4. Optional: run the built-in loop:

```sh
python3 -m server_shepherd.agent --config config.toml
```

For production on a VPS, prefer `systemd` with `--once` instead of the built-in loop.

## Install On A Linux VPS

These steps are suitable for your second server too.

### 1. Install system packages

Check Python version:

```sh
python3 --version
```

If `venv` is missing on Debian or Ubuntu, install the matching package:

```sh
sudo apt update
sudo apt upgrade
sudo apt install python3.12-venv
```

If your server uses another Python version, install the matching package instead, for example `python3.11-venv`.

### 2. Run The Installer

The easiest setup is the all-in-one installer:

```sh
git clone https://github.com/MVFofanov/server_shepherd.git
cd server_shepherd
chmod +x install_and_config_server_shepherd.sh
./install_and_config_server_shepherd.sh \
  server_id="server_3" \
  telegram_bot_token="your_bot_token_here" \
  chat_id="your_chat_id_here"
```

If this server has a website to check:

```sh
./install_and_config_server_shepherd.sh \
  server_id="web-server" \
  telegram_bot_token="your_bot_token_here" \
  chat_id="your_chat_id_here" \
  website_url="https://example.com/"
```

The installer:

- clones or updates the repository
- creates `config.toml`
- creates `server_shepherd.env`
- creates `server_shepherd_env`
- writes Telegram exports into `~/.bashrc`
- creates and enables the collect/report systemd timers

No Telegram Python package is required right now. The project uses the standard library for Telegram API calls.

### 3. Manual Script Steps

If you already cloned the repo and only want to rerun setup scripts, use:

```sh
chmod +x server_shepherd/set_config_and_telegram.sh
./server_shepherd/set_config_and_telegram.sh . \
  server_id="server_3" \
  telegram_bot_token="your_bot_token_here" \
  chat_id="your_chat_id_here"
source ~/.bashrc
```

If this server has a website to check, add `website_url`:

```sh
./server_shepherd/set_config_and_telegram.sh . \
  server_id="web-server" \
  telegram_bot_token="your_bot_token_here" \
  chat_id="your_chat_id_here" \
  website_url="https://example.com/"
source ~/.bashrc
```

The script writes:

- `config.toml`
- `server_shepherd.env`
- `server_shepherd_env`
- Telegram exports into `~/.bashrc`

Then set up services and timers:

```sh
chmod +x server_shepherd/make_services_and_timers.sh
sudo ./server_shepherd/make_services_and_timers.sh .
```

### 4. Test One Run

```sh
cd /home/your-user/server_shepherd
source server_shepherd_env/bin/activate
python3 -m server_shepherd.agent --config config.toml --once
python3 -m server_shepherd.agent --config config.toml --daily-report --no-save
```

Confirm:

- `data/metrics.jsonl` contains a new JSON line
- `--daily-report --no-save` builds a preview report without shifting the saved daily-report window
- the Telegram bot chat receives a message if Telegram is enabled for that command

### 5. Build A Daily Traffic Plot

Install matplotlib in the virtual environment once:

```sh
source server_shepherd_env/bin/activate
python3 -m pip install matplotlib
```

Then build a chart for one UTC day:

```sh
python3 -m server_shepherd.plot_daily_traffic --date 2026-04-23
```

Or build yesterday's chart in Berlin time:

```sh
python3 -m server_shepherd.plot_daily_traffic --previous-day --timezone Europe/Berlin
```

This reads `data/metrics.jsonl` and saves:

```text
figures/2026-04-23.png
```

The plot has:

- top panel: `network_rx_delta_mb`
- bottom panel: `network_tx_delta_mb`
- one bar per saved metric sample

### 6. Set Up Services And Timers

Create and enable the `systemd` services/timers:

```sh
chmod +x server_shepherd/make_services_and_timers.sh
sudo ./server_shepherd/make_services_and_timers.sh .
```

The script:

- detects the normal Linux user from `sudo`
- uses the current project directory
- writes the collect/plot/report service and timer files
- reloads `systemd`
- enables the collect, plot, and report timers
- disables the old `server-shepherd.timer` if it exists

Check the setup:

```sh
systemctl status server-shepherd-collect.timer
systemctl status server-shepherd-plot.timer
systemctl status server-shepherd-report.timer
systemctl list-timers --all | grep server-shepherd
```

Check service logs:

```sh
systemctl status server-shepherd-collect.service
systemctl status server-shepherd-report.service
sudo journalctl -u server-shepherd-collect.service -n 50 --no-pager
sudo journalctl -u server-shepherd-report.service -n 50 --no-pager
```

## Telegram Setup

The project can send messages without any external Python package by using the Telegram Bot API directly.

1. Create a bot with BotFather.
2. Open the bot chat and press `Start`.
3. Get your `chat_id` by opening:

```text
https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
```

Then look for:

```json
"chat":{"id":123456789,"type":"private"}
```

4. Put the bot token into `server_shepherd.env` or export it manually:

```sh
export SERVER_SHEPHERD_TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

5. Enable the `[telegram]` section in `config.toml` and set `chat_id_env = "SERVER_SHEPHERD_TELEGRAM_CHAT_ID"`.
6. Choose a message mode in `[privacy]`:

- `privacy_first`: only safe summaries like `CPU: normal` and `Traffic: low`
- `middle`: rounded percentages plus downloaded/uploaded traffic for the last interval

You can also tune privacy-first traffic labels in `[privacy.traffic_mb]`:

- below `medium`: `low`
- from `medium` to below `high`: `medium`
- from `high` to below `very_high`: `high`
- `very_high` or above: `very high`

## systemd Setup

The recommended production setup is two `oneshot` services with two timers:

- one every 10 minutes for raw metric collection
- one daily at 00:10 Berlin time for the previous day's traffic plot
- one daily at 09:00 Berlin time for the previous day's Telegram summary

```sh
cd /home/your-user/server_shepherd
chmod +x server_shepherd/make_services_and_timers.sh
sudo ./server_shepherd/make_services_and_timers.sh .
```

The script:

- detects the normal Linux user from `sudo`
- uses the project directory you pass as the first argument
- writes the collect/plot/report service and timer files
- reloads `systemd`
- enables the collect, plot, and report timers
- disables the old `server-shepherd.timer` if it exists

Before running it, make sure these files exist:

- `config.toml`
- `server_shepherd.env`
- `server_shepherd_env/bin/python`

If this server already had the older single-timer setup, disable it to avoid duplicate reports:

```sh
sudo systemctl disable --now server-shepherd.timer
```

Optional cleanup after you confirm the new timers work:

```sh
sudo rm /etc/systemd/system/server-shepherd.timer
sudo rm /etc/systemd/system/server-shepherd.service
sudo systemctl daemon-reload
```

Check timer status:

```sh
systemctl status server-shepherd-collect.timer
systemctl status server-shepherd-plot.timer
systemctl status server-shepherd-report.timer
systemctl list-timers --all | grep server-shepherd
```

After upgrading, `systemctl list-timers --all | grep server-shepherd` should show only:

- `server-shepherd-collect.timer`
- `server-shepherd-plot.timer`
- `server-shepherd-report.timer`

Test both services manually:

```sh
sudo systemctl start server-shepherd-collect.service
sudo systemctl start server-shepherd-plot.service
sudo systemctl start server-shepherd-report.service
```

Check service logs:

```sh
systemctl status server-shepherd-collect.service
systemctl status server-shepherd-plot.service
systemctl status server-shepherd-report.service
sudo journalctl -u server-shepherd-collect.service -n 50 --no-pager
sudo journalctl -u server-shepherd-plot.service -n 50 --no-pager
sudo journalctl -u server-shepherd-report.service -n 50 --no-pager
```

For a `Type=oneshot` service, `inactive (dead)` after a successful run is normal.

## Running On Two Servers

Repeat the same install steps on the second server:

- clone the repo
- create `server_shepherd_env`
- create that server's `config.toml`
- create that server's `server_shepherd.env`
- enable its own collect/report timers
- disable the old `server-shepherd.timer` if it exists

Good practice:

- use a different `server_id` on each server
- keep separate `config.toml` files on each server
- both servers can send to the same Telegram `chat_id`
- they do not need to run at the same minute
- frequent collection can stay local while only the daily summary goes to Telegram

Example:

- `server-a` collects every 10 minutes and reports daily at 21:00 Berlin time
- `server-b` collects every 10 minutes and reports daily at 21:00 Berlin time

Both can still send messages into the same bot chat.

## Notes

- This MVP targets Linux nodes because it reads `/proc` for low-dependency metric collection.
- The loop runs in-process for easy testing. For production, the cleaner next step is usually a systemd timer or cron job that runs `--once`.
- The JSONL output is sanitized and local-only. No network transfer is done yet.
- `interval_minutes` in `config.toml` matters for the built-in Python loop. If you use `systemd`, the timer file controls the real schedule.

## Git advice

Keep these in Git:

- source code
- `README.md`
- `pyproject.toml`
- `config.example.toml`

Keep these out of Git:

- real local config such as `config.toml`
- runtime output in `data/`
- environment files such as `.env`
- Python cache files and local virtual environments
