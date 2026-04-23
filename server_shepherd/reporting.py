from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import mean


def _parse_iso_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Expected ISO timestamp string.")
    return datetime.fromisoformat(value)


def _status_rank(status: str) -> int:
    return {
        "ok": 0,
        "warning": 1,
        "critical": 2,
    }.get(status, 0)


def _status_text(status: str) -> str:
    return {
        "ok": "normal",
        "warning": "warning",
        "critical": "critical",
    }.get(status, status)


def _status_icon(status: str) -> str:
    return {
        "ok": "✅",
        "warning": "⚠️",
        "critical": "❌",
    }.get(status, "•")


def _worst_status(statuses: list[str]) -> str:
    if not statuses:
        return "ok"
    return max(statuses, key=_status_rank)


def _round(value: float) -> float:
    return round(value, 2)


def _format_problem_time(row: dict[str, object]) -> str:
    timestamp = _parse_iso_timestamp(row["timestamp"])
    return timestamp.strftime("%H:%M UTC")


def _problem_details(
    rows: list[dict[str, object]],
    status_key: str,
    value_key: str,
) -> list[str]:
    problem_rows = [
        row for row in rows
        if str(row.get(status_key, "ok")) in {"warning", "critical"}
    ]
    if not problem_rows:
        return []

    worst_row = max(problem_rows, key=lambda row: float(row[value_key]))
    worst_status = str(worst_row.get(status_key, "warning")).capitalize()
    return [
        f"   {worst_status}: {len(problem_rows)} sample{'s' if len(problem_rows) != 1 else ''}",
        f"   Triggered at: {_format_problem_time(worst_row)}, {round(float(worst_row[value_key]))}%",
    ]


def _website_problem_details(rows: list[dict[str, object]]) -> list[str]:
    failed_rows = [
        row for row in rows
        if row.get("website_ok") is False
    ]
    if not failed_rows:
        return []

    return [
        f"   Failed: {len(failed_rows)} sample{'s' if len(failed_rows) != 1 else ''}",
        f"   First failure: {_format_problem_time(failed_rows[0])}",
        f"   Last failure: {_format_problem_time(failed_rows[-1])}",
    ]


def select_report_window(
    metrics_rows: list[dict[str, object]],
    previous_daily_report: dict[str, object] | None,
    default_window_hours: int,
) -> tuple[datetime, datetime, list[dict[str, object]]]:
    end = datetime.now(UTC)
    if previous_daily_report and "report_end" in previous_daily_report:
        start = _parse_iso_timestamp(previous_daily_report["report_end"])
    else:
        start = end - timedelta(hours=default_window_hours)

    filtered = [
        row for row in metrics_rows
        if start < _parse_iso_timestamp(row["timestamp"]) <= end
    ]
    return start, end, filtered


def build_daily_summary(
    server_id: str,
    start: datetime,
    end: datetime,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    if not rows:
        return {
            "server_id": server_id,
            "report_created_at": datetime.now(UTC).isoformat(),
            "report_start": start.isoformat(),
            "report_end": end.isoformat(),
            "sample_count": 0,
            "status": "ok",
            "status_label": "normal",
            "cpu_avg_percent": 0.0,
            "cpu_max_percent": 0.0,
            "memory_avg_percent": 0.0,
            "memory_max_percent": 0.0,
            "disk_percent": 0.0,
            "traffic_downloaded_mb": 0.0,
            "traffic_uploaded_mb": 0.0,
            "cpu_status": "ok",
            "memory_status": "ok",
            "disk_status": "ok",
            "website_status": "ok",
            "cpu_problem_details": [],
            "memory_problem_details": [],
            "disk_problem_details": [],
            "website_problem_details": [],
            "website_checks_ok": 0,
            "website_checks_total": 0,
        }

    cpu_values = [float(row["cpu_percent"]) for row in rows]
    memory_values = [float(row["memory_percent"]) for row in rows]
    disk_values = [float(row["disk_percent"]) for row in rows]
    rx_values = [float(row.get("network_rx_delta_mb", 0.0)) for row in rows]
    tx_values = [float(row.get("network_tx_delta_mb", 0.0)) for row in rows]
    statuses = [str(row.get("status", "ok")) for row in rows]
    cpu_statuses = [str(row.get("cpu_status", "ok")) for row in rows]
    memory_statuses = [str(row.get("memory_status", "ok")) for row in rows]
    disk_statuses = [str(row.get("disk_status", "ok")) for row in rows]

    website_rows = [row for row in rows if "website_ok" in row]
    website_ok_count = sum(1 for row in website_rows if row.get("website_ok") is True)
    website_status = "critical" if website_rows and website_ok_count < len(website_rows) else "ok"

    overall_status = _worst_status(statuses)

    return {
        "server_id": server_id,
        "report_created_at": datetime.now(UTC).isoformat(),
        "report_start": start.isoformat(),
        "report_end": end.isoformat(),
        "sample_count": len(rows),
        "status": overall_status,
        "status_label": _status_text(overall_status),
        "cpu_avg_percent": _round(mean(cpu_values)),
        "cpu_max_percent": _round(max(cpu_values)),
        "memory_avg_percent": _round(mean(memory_values)),
        "memory_max_percent": _round(max(memory_values)),
        "disk_percent": _round(max(disk_values)),
        "traffic_downloaded_mb": _round(sum(rx_values)),
        "traffic_uploaded_mb": _round(sum(tx_values)),
        "cpu_status": _worst_status(cpu_statuses),
        "memory_status": _worst_status(memory_statuses),
        "disk_status": _worst_status(disk_statuses),
        "website_status": website_status,
        "cpu_problem_details": _problem_details(rows, "cpu_status", "cpu_percent"),
        "memory_problem_details": _problem_details(rows, "memory_status", "memory_percent"),
        "disk_problem_details": _problem_details(rows, "disk_status", "disk_percent"),
        "website_problem_details": _website_problem_details(website_rows),
        "website_checks_ok": website_ok_count,
        "website_checks_total": len(website_rows),
    }


def build_daily_report_message(summary: dict[str, object]) -> str:
    status = str(summary["status"])
    header = f"{summary['server_id']} {_status_icon(status)} ({summary['status_label']})"
    lines = [header]

    lines.append(
        f"{_status_icon(str(summary['cpu_status']))} CPU avg/max: "
        f"{round(float(summary['cpu_avg_percent']))}% / {round(float(summary['cpu_max_percent']))}%"
    )
    lines.extend(str(line) for line in summary["cpu_problem_details"])

    lines.append(
        f"{_status_icon(str(summary['memory_status']))} RAM avg/max: "
        f"{round(float(summary['memory_avg_percent']))}% / {round(float(summary['memory_max_percent']))}%"
    )
    lines.extend(str(line) for line in summary["memory_problem_details"])

    lines.append(
        f"{_status_icon(str(summary['disk_status']))} Disk usage: "
        f"{round(float(summary['disk_percent']))} %"
    )
    lines.extend(str(line) for line in summary["disk_problem_details"])

    lines.append(
        "✅ Traffic ⬇️ "
        f"{float(summary['traffic_downloaded_mb']):.2f} MB "
        "⬆️ "
        f"{float(summary['traffic_uploaded_mb']):.2f} MB"
    )

    if int(summary["website_checks_total"]) > 0:
        lines.append(
            f"{_status_icon(str(summary['website_status']))} Website checks: {summary['website_checks_ok']}/{summary['website_checks_total']} OK"
        )
        lines.extend(str(line) for line in summary["website_problem_details"])

    lines.append(f"• Samples: {summary['sample_count']}")
    return "\n".join(lines)
