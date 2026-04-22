from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import os
import shutil
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _read_proc_stat() -> tuple[int, int]:
    with open("/proc/stat", "r", encoding="utf-8") as handle:
        first_line = handle.readline().split()

    values = [int(value) for value in first_line[1:]]
    idle = values[3] + values[4]
    total = sum(values)
    return idle, total


def _read_cpu_percent(sample_seconds: float) -> float:
    idle_before, total_before = _read_proc_stat()
    time.sleep(sample_seconds)
    idle_after, total_after = _read_proc_stat()

    idle_delta = idle_after - idle_before
    total_delta = total_after - total_before
    if total_delta <= 0:
        return 0.0

    busy = 1 - (idle_delta / total_delta)
    return round(busy * 100, 2)


def _read_memory_percent() -> float:
    meminfo: dict[str, int] = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as handle:
        for line in handle:
            key, value = line.split(":", maxsplit=1)
            meminfo[key] = int(value.strip().split()[0])

    total = meminfo["MemTotal"]
    available = meminfo["MemAvailable"]
    used_percent = ((total - available) / total) * 100
    return round(used_percent, 2)


def _read_uptime_seconds() -> int:
    with open("/proc/uptime", "r", encoding="utf-8") as handle:
        uptime = float(handle.read().split()[0])
    return int(uptime)


@dataclass(slots=True)
class MetricSnapshot:
    server_id: str
    timestamp: str
    cpu_percent: float
    cpu_count: int
    memory_percent: float
    memory_total_gb: float
    disk_percent: float
    disk_free_gb: float
    uptime_seconds: int
    load_1m: float
    load_5m: float
    load_15m: float
    network_rx_bytes: int
    network_rx_gb: float
    network_tx_bytes: int
    network_tx_gb: float
    website_url: str | None = None
    website_ok: bool | None = None
    website_status_code: int | None = None
    website_response_ms: float | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_memory_total_gb() -> float:
    with open("/proc/meminfo", "r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("MemTotal:"):
                total_kb = int(line.split(":", maxsplit=1)[1].strip().split()[0])
                return round(total_kb / (1024 ** 2), 2)

    raise ValueError("MemTotal not found in /proc/meminfo.")


def _read_network_totals() -> tuple[int, int]:
    rx_total = 0
    tx_total = 0

    with open("/proc/net/dev", "r", encoding="utf-8") as handle:
        lines = handle.readlines()[2:]

    for line in lines:
        interface, values = line.split(":", maxsplit=1)
        name = interface.strip()
        if name == "lo":
            continue

        fields = values.split()
        rx_total += int(fields[0])
        tx_total += int(fields[8])

    return rx_total, tx_total


def check_website(url: str, expected_status: int, timeout_seconds: float) -> dict[str, object]:
    request = Request(url, method="GET")
    started = time.perf_counter()

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.getcode()
    except HTTPError as exc:
        status_code = exc.code
        response_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "website_url": url,
            "website_ok": status_code == expected_status,
            "website_status_code": status_code,
            "website_response_ms": response_ms,
        }
    except URLError:
        return {
            "website_url": url,
            "website_ok": False,
            "website_status_code": None,
            "website_response_ms": None,
        }

    response_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "website_url": url,
        "website_ok": status_code == expected_status,
        "website_status_code": status_code,
        "website_response_ms": response_ms,
    }


def collect_metrics(server_id: str, disk_path: Path, cpu_sample_seconds: float) -> MetricSnapshot:
    usage = shutil.disk_usage(disk_path)
    disk_percent = round((usage.used / usage.total) * 100, 2)
    disk_free_gb = round(usage.free / (1024 ** 3), 2)
    load_1m, load_5m, load_15m = os.getloadavg()
    network_rx_bytes, network_tx_bytes = _read_network_totals()

    return MetricSnapshot(
        server_id=server_id,
        timestamp=datetime.now(UTC).isoformat(),
        cpu_percent=_read_cpu_percent(cpu_sample_seconds),
        cpu_count=os.cpu_count() or 0,
        memory_percent=_read_memory_percent(),
        memory_total_gb=_read_memory_total_gb(),
        disk_percent=disk_percent,
        disk_free_gb=disk_free_gb,
        uptime_seconds=_read_uptime_seconds(),
        load_1m=round(load_1m, 2),
        load_5m=round(load_5m, 2),
        load_15m=round(load_15m, 2),
        network_rx_bytes=network_rx_bytes,
        network_rx_gb=round(network_rx_bytes / (1024 ** 3), 2),
        network_tx_bytes=network_tx_bytes,
        network_tx_gb=round(network_tx_bytes / (1024 ** 3), 2),
    )
