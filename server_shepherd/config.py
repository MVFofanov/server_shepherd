from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(slots=True)
class AgentConfig:
    server_id: str
    interval_minutes: int
    output_path: Path
    disk_path: Path
    cpu_sample_seconds: float


def load_config(path: str | Path) -> AgentConfig:
    config_path = Path(path)
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)

    agent = data.get("agent", {})
    if not agent:
        raise ValueError("Missing [agent] section in config file.")

    server_id = str(agent.get("server_id", "")).strip()
    if not server_id:
        raise ValueError("agent.server_id must be set.")

    interval_minutes = int(agent.get("interval_minutes", 30))
    if interval_minutes <= 0:
        raise ValueError("agent.interval_minutes must be greater than zero.")

    output_path = Path(agent.get("output_path", "./data/metrics.jsonl"))
    disk_path = Path(agent.get("disk_path", "/"))
    cpu_sample_seconds = float(agent.get("cpu_sample_seconds", 1.0))
    if cpu_sample_seconds <= 0:
        raise ValueError("agent.cpu_sample_seconds must be greater than zero.")

    return AgentConfig(
        server_id=server_id,
        interval_minutes=interval_minutes,
        output_path=output_path,
        disk_path=disk_path,
        cpu_sample_seconds=cpu_sample_seconds,
    )
