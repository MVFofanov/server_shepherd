from __future__ import annotations

from datetime import datetime


def _format_timestamp(iso_timestamp: str) -> str:
    timestamp = datetime.fromisoformat(iso_timestamp)
    return timestamp.strftime("%Y-%m-%d %H:%M UTC")


def _friendly_metric_status(status: str) -> str:
    return {
        "ok": "normal",
        "warning": "high",
        "critical": "critical",
    }.get(status, status)


def _friendly_traffic_level(payload: dict[str, object], medium_mb: float, high_mb: float, very_high_mb: float) -> str:
    total_mb = float(payload.get("network_rx_delta_mb", 0.0)) + float(payload.get("network_tx_delta_mb", 0.0))
    if total_mb >= very_high_mb:
        return "very high"
    if total_mb >= high_mb:
        return "high"
    if total_mb >= medium_mb:
        return "medium"
    return "low"


def build_status_message(
    payload: dict[str, object],
    message_mode: str,
    traffic_medium_mb: float,
    traffic_high_mb: float,
    traffic_very_high_mb: float,
) -> str:
    website_text = "OK" if payload.get("website_ok") is True else "DOWN" if payload.get("website_ok") is False else "not checked"
    time_text = _format_timestamp(str(payload["timestamp"]))

    if message_mode == "privacy_first":
        return "\n".join(
            [
                str(payload["server_id"]),
                f"Status: {str(payload['status']).upper()}",
                f"CPU: {_friendly_metric_status(str(payload['cpu_status']))}",
                f"RAM: {_friendly_metric_status(str(payload['memory_status']))}",
                f"Disk: {_friendly_metric_status(str(payload['disk_status']))}",
                f"Website: {website_text}",
                f"Traffic: {_friendly_traffic_level(payload, traffic_medium_mb, traffic_high_mb, traffic_very_high_mb)}",
                f"Time: {time_text}",
            ]
        )

    return "\n".join(
        [
            str(payload["server_id"]),
            f"Status: {str(payload['status']).upper()}",
            f"CPU: {round(float(payload['cpu_percent']))}%",
            f"RAM: {round(float(payload['memory_percent']))}%",
            f"Disk: {round(float(payload['disk_percent']))}%",
            f"Website: {website_text}",
            f"Downloaded traffic: {float(payload.get('network_rx_delta_mb', 0.0)):.2f} MB",
            f"Uploaded traffic: {float(payload.get('network_tx_delta_mb', 0.0)):.2f} MB",
            f"Time: {time_text}",
        ]
    )
