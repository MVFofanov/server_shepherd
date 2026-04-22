from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import os
import shutil
import time


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
    memory_percent: float
    disk_percent: float
    disk_free_gb: float
    uptime_seconds: int
    load_1m: float
    load_5m: float
    load_15m: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def collect_metrics(server_id: str, disk_path: Path, cpu_sample_seconds: float) -> MetricSnapshot:
    usage = shutil.disk_usage(disk_path)
    disk_percent = round((usage.used / usage.total) * 100, 2)
    disk_free_gb = round(usage.free / (1024 ** 3), 2)
    load_1m, load_5m, load_15m = os.getloadavg()

    return MetricSnapshot(
        server_id=server_id,
        timestamp=datetime.now(UTC).isoformat(),
        cpu_percent=_read_cpu_percent(cpu_sample_seconds),
        memory_percent=_read_memory_percent(),
        disk_percent=disk_percent,
        disk_free_gb=disk_free_gb,
        uptime_seconds=_read_uptime_seconds(),
        load_1m=round(load_1m, 2),
        load_5m=round(load_5m, 2),
        load_15m=round(load_15m, 2),
    )
