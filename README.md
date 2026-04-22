# server_shepherd

Small first step for a privacy-first server monitoring project.

This MVP is intentionally narrow:

- runs locally on a Linux server
- reads CPU, RAM, disk, uptime, and load average
- appends snapshots to a JSON Lines file on disk
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
- `server_shepherd/storage.py`: JSONL persistence

## Quick start

1. Copy the config:

```sh
cp config.example.toml config.toml
```

2. Run one collection:

```sh
python -m server_shepherd.agent --config config.toml --once
```

3. Inspect the output file:

```sh
cat ./data/metrics.jsonl
```

4. Run the loop:

```sh
python -m server_shepherd.agent --config config.toml
```

## Notes

- This MVP targets Linux nodes because it reads `/proc` for low-dependency metric collection.
- The loop runs in-process for easy testing. For production, the cleaner next step is usually a systemd timer or cron job that runs `--once`.
- The JSONL output is sanitized and local-only. No network transfer is done yet.

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
