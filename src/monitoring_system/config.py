"""Load settings from config.default.toml, config.toml, and .env."""

from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


class RedisSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 6379
    db: int = 0
    stream: str = "stage:events"
    consumer_group: str = "stage_ingest"
    consumer_name: str = "worker-1"

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class SqliteSettings(BaseModel):
    path: str = "data/stages.db"

    def resolved_path(self, root: Path | None = None) -> Path:
        p = Path(self.path)
        if p.is_absolute():
            return p
        base = root or _project_root()
        return (base / p).resolve()


class IngestSettings(BaseModel):
    batch_size: int = 100
    block_ms: int = 1000
    claim_idle_ms: int = 60_000


class DashboardSettings(BaseModel):
    poll_seconds: float = 2.0
    page_title: str = "Stage Monitor"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MONITORING_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis: RedisSettings = RedisSettings()
    sqlite: SqliteSettings = SqliteSettings()
    ingest: IngestSettings = IngestSettings()
    dashboard: DashboardSettings = DashboardSettings()


def _merged_toml(root: Path) -> dict:
    config_path = Path(os.environ.get("MONITORING_CONFIG", root / "config.toml"))
    merged: dict = {}
    for path in (root / "config.default.toml", config_path):
        for section, values in _load_toml(path).items():
            if section not in merged:
                merged[section] = {}
            if isinstance(values, dict):
                merged[section].update(values)
    return merged


@lru_cache
def load_settings() -> Settings:
    root = _project_root()
    load_dotenv(root / ".env", override=False)
    merged = _merged_toml(root)
    return Settings(
        redis=RedisSettings(**merged.get("redis", {})),
        sqlite=SqliteSettings(**merged.get("sqlite", {})),
        ingest=IngestSettings(**merged.get("ingest", {})),
        dashboard=DashboardSettings(**merged.get("dashboard", {})),
    )
