from __future__ import annotations

import argparse
from datetime import date
import time

from .config import load_config
from .message_format import build_status_message
from .metrics import check_website, collect_metrics
from .plot_daily_traffic import create_daily_traffic_plot
from .reporting import (
    build_daily_report_message,
    build_daily_summary,
    calendar_day_window,
    previous_calendar_day_window,
    select_calendar_day_rows,
)
from .storage import append_jsonl, read_jsonl, read_last_jsonl
from .telegram_sender import send_telegram_message, send_telegram_photo


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
    metric_statuses = (
        payload["cpu_status"],
        payload["memory_status"],
        payload["disk_status"],
    )
    payload["status"] = "critical" if (
        payload.get("website_ok") is False or "critical" in metric_statuses
    ) else "warning" if "warning" in metric_statuses else "ok"
    append_jsonl(config.output_path, payload)
    if config.telegram is not None and config.telegram.send_on_regular_check:
        message = build_status_message(
            payload,
            config.privacy.message_mode,
            config.privacy.traffic_medium_mb,
            config.privacy.traffic_high_mb,
            config.privacy.traffic_very_high_mb,
        )
        send_telegram_message(
            bot_token=config.telegram.get_bot_token(),
            chat_id=config.telegram.get_chat_id(),
            text=message,
        )
    return payload


def run_daily_report(
    config_path: str,
    send_telegram: bool = True,
    save_report: bool = True,
    report_date: date | None = None,
) -> dict[str, object]:
    config = load_config(config_path)
    metrics_rows = read_jsonl(config.output_path)
    if report_date is None:
        target_day, report_start, report_end = previous_calendar_day_window(config.report.timezone)
    else:
        target_day = report_date
        report_start, report_end = calendar_day_window(report_date, config.report.timezone)
    report_rows = select_calendar_day_rows(metrics_rows, report_start, report_end)
    summary = build_daily_summary(
        server_id=config.server_id,
        start=report_start,
        end=report_end,
        rows=report_rows,
    )
    summary["report_day"] = target_day.isoformat()
    if save_report:
        append_jsonl(config.report.output_path, summary)

    plot_path = config.report.figures_dir / f"{target_day.isoformat()}.png"
    if config.telegram is not None and config.telegram.send_traffic_plot:
        if not plot_path.exists():
            plot_path = create_daily_traffic_plot(
                input_path=config.output_path,
                day=target_day,
                output_dir=config.report.figures_dir,
                timezone_name=config.report.timezone,
            )

    if (
        send_telegram
        and config.telegram is not None
        and config.telegram.send_on_daily_report
    ):
        send_telegram_message(
            bot_token=config.telegram.get_bot_token(),
            chat_id=config.telegram.get_chat_id(),
            text=build_daily_report_message(summary),
        )
        if config.telegram.send_traffic_plot:
            send_telegram_photo(
                bot_token=config.telegram.get_bot_token(),
                chat_id=config.telegram.get_chat_id(),
                photo_path=plot_path,
                caption=f"{config.server_id} traffic plot for {target_day.isoformat()}",
            )

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect local server metrics.")
    parser.add_argument("--config", default="config.toml", help="Path to TOML config file.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one collection cycle and exit.",
    )
    parser.add_argument(
        "--daily-report",
        action="store_true",
        help="Build a daily summary from saved metric snapshots and optionally send it to Telegram.",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Do not send Telegram for this run.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Build the report without saving it to daily JSONL storage.",
    )
    parser.add_argument(
        "--date",
        help="For daily report mode, build the report for a specific day in YYYY-MM-DD using the configured report timezone.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.daily_report:
        summary = run_daily_report(
            args.config,
            send_telegram=not args.no_telegram,
            save_report=not args.no_save,
            report_date=date.fromisoformat(args.date) if args.date else None,
        )
        print(
            f"{'Built' if args.no_save else 'Saved'} daily report for "
            f"{summary['server_id']} for {summary['report_day']} "
            f"{'without saving to daily JSONL storage.' if args.no_save else 'to configured daily JSONL storage.'}"
        )
        return

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
