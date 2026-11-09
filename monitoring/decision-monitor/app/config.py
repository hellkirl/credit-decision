"""Настройки экспортёра. Всё задаётся переменными окружения в docker-compose."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


def parse_window(text: str) -> int:
    """'30d' / '12h' / '15m' -> секунды."""
    m = re.fullmatch(r"\s*(\d+)\s*([mhd])\s*", text)
    if not m:
        raise ValueError(f"MONITOR_WINDOW must look like 30d, 12h or 15m, got {text!r}")
    return int(m.group(1)) * {"m": 60, "h": 3600, "d": 86400}[m.group(2)]


@dataclass(frozen=True)
class Settings:
    database_url: str
    port: int
    interval_seconds: int
    window: str
    window_seconds: int
    min_group_size: int
    min_psi_sample: int
    rub_per_dm: float
    reference_path: Path


def load() -> Settings:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    window = os.environ.get("MONITOR_WINDOW", "30d")
    return Settings(
        database_url=database_url,
        port=int(os.environ.get("MONITOR_PORT", "9108")),
        interval_seconds=int(os.environ.get("MONITOR_INTERVAL_SECONDS", "60")),
        window=window,
        window_seconds=parse_window(window),
        min_group_size=int(os.environ.get("MONITOR_MIN_GROUP_SIZE", "30")),
        min_psi_sample=int(os.environ.get("MONITOR_MIN_PSI_SAMPLE", "50")),
        # Должен совпадать с RUB_PER_DM у backend, иначе дрейф суммы будет ложным
        rub_per_dm=float(os.environ.get("RUB_PER_DM", "49.1")),
        reference_path=Path(os.environ.get("REFERENCE_PATH", APP_ROOT / "reference" / "reference.json")),
    )
