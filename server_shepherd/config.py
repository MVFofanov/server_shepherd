from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tomllib


@dataclass(slots=True)
class ThresholdConfig:
    warning: float
    critical: float


@dataclass(slots=True)
class WebsiteCheckConfig:
    url: str
    expected_status: int
    timeout_seconds: float


@dataclass(slots=True)
class PrivacyConfig:
    message_mode: str


@dataclass(slots=True)
class TelegramConfig:
    enabled: bool
    chat_id: str
    bot_token_env: str

    def get_bot_token(self) -> str:
        token = os.environ.get(self.bot_token_env, "").strip()
        if not token:
            raise ValueError(
                f"Telegram is enabled, but environment variable {self.bot_token_env} is not set."
            )
        return token


@dataclass(slots=True)
class AgentConfig:
    server_id: str
    interval_minutes: int
    output_path: Path
    disk_path: Path
    cpu_sample_seconds: float
    website: WebsiteCheckConfig | None
    privacy: PrivacyConfig
    telegram: TelegramConfig | None
    cpu_percent_thresholds: ThresholdConfig
    memory_percent_thresholds: ThresholdConfig
    disk_percent_thresholds: ThresholdConfig


def _load_threshold(section: dict[str, object], default_warning: float, default_critical: float) -> ThresholdConfig:
    warning = float(section.get("warning", default_warning))
    critical = float(section.get("critical", default_critical))
    if warning < 0 or critical < 0:
        raise ValueError("Thresholds must be non-negative.")
    if critical <= warning:
        raise ValueError("Threshold critical value must be greater than warning.")
    return ThresholdConfig(warning=warning, critical=critical)


def _load_website_config(section: dict[str, object]) -> WebsiteCheckConfig | None:
    if not section:
        return None

    url = str(section.get("url", "")).strip()
    if not url:
        return None

    expected_status = int(section.get("expected_status", 200))
    timeout_seconds = float(section.get("timeout_seconds", 5.0))
    if timeout_seconds <= 0:
        raise ValueError("website.timeout_seconds must be greater than zero.")

    return WebsiteCheckConfig(
        url=url,
        expected_status=expected_status,
        timeout_seconds=timeout_seconds,
    )


def _load_privacy_config(section: dict[str, object]) -> PrivacyConfig:
    message_mode = str(section.get("message_mode", "middle")).strip().lower()
    if message_mode not in {"privacy_first", "middle"}:
        raise ValueError("privacy.message_mode must be 'privacy_first' or 'middle'.")
    return PrivacyConfig(message_mode=message_mode)


def _load_telegram_config(section: dict[str, object]) -> TelegramConfig | None:
    if not section or not bool(section.get("enabled", False)):
        return None

    chat_id = str(section.get("chat_id", "")).strip()
    bot_token_env = str(section.get("bot_token_env", "")).strip()
    if not chat_id:
        raise ValueError("telegram.chat_id must be set when telegram is enabled.")
    if not bot_token_env:
        raise ValueError("telegram.bot_token_env must be set when telegram is enabled.")

    return TelegramConfig(
        enabled=True,
        chat_id=chat_id,
        bot_token_env=bot_token_env,
    )


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

    website = _load_website_config(data.get("website", {}))
    privacy = _load_privacy_config(data.get("privacy", {}))
    telegram = _load_telegram_config(data.get("telegram", {}))
    thresholds = data.get("thresholds", {})
    cpu_thresholds = _load_threshold(thresholds.get("cpu_percent", {}), 70.0, 90.0)
    memory_thresholds = _load_threshold(thresholds.get("memory_percent", {}), 75.0, 90.0)
    disk_thresholds = _load_threshold(thresholds.get("disk_percent", {}), 80.0, 90.0)

    return AgentConfig(
        server_id=server_id,
        interval_minutes=interval_minutes,
        output_path=output_path,
        disk_path=disk_path,
        cpu_sample_seconds=cpu_sample_seconds,
        website=website,
        privacy=privacy,
        telegram=telegram,
        cpu_percent_thresholds=cpu_thresholds,
        memory_percent_thresholds=memory_thresholds,
        disk_percent_thresholds=disk_thresholds,
    )
