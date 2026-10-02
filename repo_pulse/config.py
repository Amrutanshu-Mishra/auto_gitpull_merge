"""Load .env and config.yaml. Secrets come from env vars only; everything else from config.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("REPO_PULSE_CONFIG", ROOT / "config.yaml"))

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class CortexModels:
    embed_model: str      # must produce 768 dims (VECTOR(FLOAT, 768))
    complete_model: str


@dataclass(frozen=True)
class Config:
    repos: list[str]
    limits: dict[str, int]
    cortex: CortexModels
    categories: list[str]
    batch_size: int = 200

    def limit(self, source: str, default: int = 100) -> int:
        return int(self.limits.get(source, self.limits.get("default", default)))


def load_config(path: Path = CONFIG_PATH) -> Config:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    cortex = data.get("cortex", {})
    missing = [k for k in ("embed_model", "complete_model") if k not in cortex]
    if missing:
        raise SystemExit(f"{path}: cortex.{{{', '.join(missing)}}} missing")
    if not data.get("repos"):
        raise SystemExit(f"{path}: repos list is empty")
    return Config(
        repos=list(data.get("repos", [])),
        limits=dict(data.get("limits", {})),
        cortex=CortexModels(
            embed_model=cortex["embed_model"],
            complete_model=cortex["complete_model"],
        ),
        categories=list(data.get("categories", [])),
        batch_size=int((data.get("enrich") or {}).get("batch_size", 200)),
    )


def env(name: str, default: str | None = None) -> str:
    """Read a required env var; raises if missing and no default given."""
    value = os.environ.get(name, default)
    if value is None:
        raise SystemExit(f"Missing required environment variable {name} (see .env.example)")
    return value
