from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .storage import read_jsonl


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _load_day_rows(input_path: Path, day: date) -> list[dict[str, object]]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)

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
) -> Path:
    try:
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required for plotting. Install it in the virtual environment with: "
            "python3 -m pip install matplotlib"
        ) from exc

    rows = _load_day_rows(input_path, day)
    if not rows:
        raise ValueError(f"No metric rows found in {input_path} for {day.isoformat()}.")

    timestamps = [datetime.fromisoformat(str(row["timestamp"])) for row in rows]
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

    ax_top.bar(timestamps, rx_values, width=bar_width, color="#2a9d8f", edgecolor="#1f6f66")
    ax_top.set_title(f"{server_id} traffic for {day.isoformat()} (UTC)")
    ax_top.set_ylabel("Downloaded MB")
    ax_top.grid(axis="y", alpha=0.25)

    ax_bottom.bar(timestamps, tx_values, width=bar_width, color="#e76f51", edgecolor="#b5543c")
    ax_bottom.set_ylabel("Uploaded MB")
    ax_bottom.set_xlabel("Time (UTC)")
    ax_bottom.grid(axis="y", alpha=0.25)

    locator = mdates.HourLocator(interval=1)
    formatter = mdates.DateFormatter("%H:%M")
    ax_bottom.xaxis.set_major_locator(locator)
    ax_bottom.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate()

    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a daily traffic bar plot from metrics JSONL.")
    parser.add_argument("--date", required=True, help="Day to plot in YYYY-MM-DD format (UTC day).")
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
    return parser


def main() -> None:
    args = build_parser().parse_args()
    day = _parse_date(args.date)
    output_path = create_daily_traffic_plot(
        input_path=Path(args.input),
        day=day,
        output_dir=Path(args.output_dir),
    )
    print(f"Saved plot to {output_path}")


if __name__ == "__main__":
    main()
