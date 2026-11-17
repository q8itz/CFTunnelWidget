"""Configuration and persisted traffic stats management."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ServiceMode = Literal["auto", "systemd-system", "systemd-user", "process"]


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def _xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


@dataclass
class AppConfig:
    """User-configurable settings for Tunnel Status."""

    mode: ServiceMode = "auto"
    service_name: str = "cloudflared.service"
    metrics_url: str = "http://127.0.0.1:20241/metrics"
    poll_interval_ms: int = 2000
    persist_stats: bool = True
    process_command: str = "cloudflared tunnel run"

    @classmethod
    def config_path(cls) -> Path:
        return _xdg_config_home() / "tunnel-status" / "config.json"

    @classmethod
    def stats_path(cls) -> Path:
        return _xdg_data_home() / "tunnel-status" / "stats.json"

    @classmethod
    def load(cls, path: Path | None = None) -> AppConfig:
        target = path or cls.config_path()
        if not target.exists():
            return cls()
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()

        defaults = cls()
        mode = raw.get("mode", defaults.mode)
        if mode not in ("auto", "systemd-system", "systemd-user", "process"):
            mode = defaults.mode

        poll = raw.get("poll_interval_ms", defaults.poll_interval_ms)
        if not isinstance(poll, int) or poll < 500:
            poll = defaults.poll_interval_ms

        return cls(
            mode=mode,
            service_name=str(raw.get("service_name", defaults.service_name)),
            metrics_url=str(raw.get("metrics_url", defaults.metrics_url)),
            poll_interval_ms=poll,
            persist_stats=bool(raw.get("persist_stats", defaults.persist_stats)),
            process_command=str(raw.get("process_command", defaults.process_command)),
        )

    def save(self, path: Path | None = None) -> None:
        target = path or self.config_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
