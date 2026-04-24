from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .reporting import previous_calendar_day_window
from .storage import read_jsonl


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _local_day_bounds(day: date, timezone_name: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    local_start = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def _load_day_rows(input_path: Path, day: date, timezone_name: str) -> list[dict[str, object]]:
    start, end = _local_day_bounds(day, timezone_name)

    rows: list[dict[str, object]] = []
    for row in read_jsonl(input_path):
        timestamp = datetime.fromisoformat(str(row["timestamp"]))
        if start <= timestamp < end:
            rows.append(row)
    return rows


def _build_output_path(output_dir: Path, day: date) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{day.isoformat()}.png"


def create_daily_traffic_plot(
    input_path: Path,
    day: date,
    output_dir: Path,
    timezone_name: str = "Europe/Berlin",
) -> Path:
    try:
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required for plotting. Install it in the virtual environment with: "
            "python3 -m pip install matplotlib"
        ) from exc

    rows = _load_day_rows(input_path, day, timezone_name)
    if not rows:
        raise ValueError(f"No metric rows found in {input_path} for {day.isoformat()}.")

    utc_times = [datetime.fromisoformat(str(row["timestamp"])) for row in rows]
    local_tz = ZoneInfo(timezone_name)
    local_times = [timestamp.astimezone(local_tz) for timestamp in utc_times]
    rx_values = [float(row.get("network_rx_delta_mb", 0.0)) for row in rows]
    tx_values = [float(row.get("network_tx_delta_mb", 0.0)) for row in rows]
    server_id = str(rows[0].get("server_id", "server"))

    output_path = _build_output_path(output_dir, day)

    fig, (ax_top, ax_bottom) = plt.subplots(
        2,
        1,
        figsize=(14, 8),
        sharex=True,
        constrained_layout=True,
    )

    bar_width = timedelta(minutes=8)

    ax_top.bar(local_times, rx_values, width=bar_width, color="#2a9d8f", edgecolor="#1f6f66")
    ax_top.set_title(f"{server_id} traffic for {day.isoformat()} ({timezone_name})")
    ax_top.set_ylabel("Downloaded MB")
    ax_top.grid(axis="y", alpha=0.25)

    ax_bottom.bar(local_times, tx_values, width=bar_width, color="#e76f51", edgecolor="#b5543c")
    ax_bottom.set_ylabel("Uploaded MB")
    ax_bottom.set_xlabel(f"Time ({timezone_name})")
    ax_bottom.grid(axis="y", alpha=0.25)

    locator = mdates.HourLocator(interval=1, tz=local_tz)
    formatter = mdates.DateFormatter("%H:%M", tz=local_tz)
    ax_bottom.xaxis.set_major_locator(locator)
    ax_bottom.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate()

    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a daily traffic bar plot from metrics JSONL.")
    parser.add_argument("--date", help="Day to plot in YYYY-MM-DD format.")
    parser.add_argument(
        "--previous-day",
        action="store_true",
        help="Plot the previous calendar day in the chosen timezone.",
    )
    parser.add_argument(
        "--input",
        default="data/metrics.jsonl",
        help="Path to the metrics JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        default="figures",
        help="Directory where the PNG file should be saved.",
    )
    parser.add_argument(
        "--timezone",
        default="Europe/Berlin",
        help="Timezone used to interpret the requested day.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.previous_day:
        day = previous_calendar_day_window(args.timezone)[0]
    elif args.date:
        day = _parse_date(args.date)
    else:
        raise SystemExit("Use either --date YYYY-MM-DD or --previous-day.")
    output_path = create_daily_traffic_plot(
        input_path=Path(args.input),
        day=day,
        output_dir=Path(args.output_dir),
        timezone_name=args.timezone,
    )
    print(f"Saved plot to {output_path}")


if __name__ == "__main__":
    main()
