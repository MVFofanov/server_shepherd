from __future__ import annotations

import argparse
import time

from .config import load_config
from .metrics import collect_metrics
from .storage import append_jsonl


def run_once(config_path: str) -> dict[str, object]:
    config = load_config(config_path)
    snapshot = collect_metrics(
        server_id=config.server_id,
        disk_path=config.disk_path,
        cpu_sample_seconds=config.cpu_sample_seconds,
    )
    payload = snapshot.as_dict()
    append_jsonl(config.output_path, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect local server metrics.")
    parser.add_argument("--config", default="config.toml", help="Path to TOML config file.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one collection cycle and exit.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.once:
        payload = run_once(args.config)
        print(
            "Saved snapshot for "
            f"{payload['server_id']} at {payload['timestamp']} "
            f"to configured JSONL storage."
        )
        return

    config = load_config(args.config)
    interval_seconds = config.interval_minutes * 60

    while True:
        payload = run_once(args.config)
        print(
            "Saved snapshot for "
            f"{payload['server_id']} at {payload['timestamp']} "
            f"(next run in {config.interval_minutes} minutes)."
        )
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
