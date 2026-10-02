"""Run transforms/*.sql in layer order (stg, int, then the rest), then filename. One model per file, one statement per file."""

from __future__ import annotations

import logging
from pathlib import Path

from repo_pulse.config import ROOT

log = logging.getLogger(__name__)

TRANSFORMS_DIR = ROOT / "transforms"


# Models run layer by layer, mirroring dbt's stg -> int -> marts DAG; within a layer, by name.
LAYER_ORDER = {"stg": 0, "int": 1}


def _layer_rank(path: Path) -> int:
    return LAYER_ORDER.get(path.stem.split("_", 1)[0], len(LAYER_ORDER))


def discover_transforms(directory: Path = TRANSFORMS_DIR) -> list[Path]:
    return sorted(directory.glob("*.sql"), key=lambda p: (_layer_rank(p), p.name))


def read_model(path: Path) -> str:
    """A model file is exactly one statement, so it ports 1:1 to a dbt model.

    Executed as a single statement: Snowflake itself rejects a file holding more than one.
    """
    return path.read_text(encoding="utf-8").strip().rstrip(";").strip()


def run_transforms(conn, directory: Path = TRANSFORMS_DIR) -> list[Path]:
    done = []
    for path in discover_transforms(directory):
        log.info("transform %s", path.stem)
        with conn.cursor() as cur:
            cur.execute(read_model(path))
        done.append(path)
    if not done:
        log.info("no transforms found")
    return done
