from __future__ import annotations

import argparse
import time

from .config import load_config
from .metrics import check_website, collect_metrics
from .storage import append_jsonl, read_last_jsonl


def _metric_status(value: float, warning: float, critical: float) -> str:
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "ok"


def run_once(config_path: str) -> dict[str, object]:
    config = load_config(config_path)
    previous_payload = read_last_jsonl(config.output_path)
    snapshot = collect_metrics(
        server_id=config.server_id,
        disk_path=config.disk_path,
        cpu_sample_seconds=config.cpu_sample_seconds,
    )
    payload = snapshot.as_dict()
    previous_rx = int(previous_payload.get("network_rx_bytes", 0)) if previous_payload else 0
    previous_tx = int(previous_payload.get("network_tx_bytes", 0)) if previous_payload else 0
    rx_delta_bytes = max(0, int(payload["network_rx_bytes"]) - previous_rx)
    tx_delta_bytes = max(0, int(payload["network_tx_bytes"]) - previous_tx)
    payload["network_rx_delta_bytes"] = rx_delta_bytes
    payload["network_rx_delta_mb"] = round(rx_delta_bytes / (1024 ** 2), 2)
    payload["network_tx_delta_bytes"] = tx_delta_bytes
    payload["network_tx_delta_mb"] = round(tx_delta_bytes / (1024 ** 2), 2)
    payload["cpu_status"] = _metric_status(
        float(payload["cpu_percent"]),
        config.cpu_percent_thresholds.warning,
        config.cpu_percent_thresholds.critical,
    )
    payload["memory_status"] = _metric_status(
        float(payload["memory_percent"]),
        config.memory_percent_thresholds.warning,
        config.memory_percent_thresholds.critical,
    )
    payload["disk_status"] = _metric_status(
        float(payload["disk_percent"]),
        config.disk_percent_thresholds.warning,
        config.disk_percent_thresholds.critical,
    )
    if config.website is not None:
        payload.update(
            check_website(
                url=config.website.url,
                expected_status=config.website.expected_status,
                timeout_seconds=config.website.timeout_seconds,
            )
        )
    payload["status"] = "critical" if "critical" in (
        payload["cpu_status"],
        payload["memory_status"],
        payload["disk_status"],
    ) else "warning" if "warning" in (
        payload["cpu_status"],
        payload["memory_status"],
        payload["disk_status"],
    ) else "ok"
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
