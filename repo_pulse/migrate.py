"""Apply numbered migrations exactly once, tracked in META.SCHEMA_MIGRATIONS.

Each migrations/V<NNN>__<name>.sql is applied in version order inside a
transaction and recorded with its checksum. A recorded file whose checksum
no longer matches aborts the run: applied migrations are immutable, add a
new one instead.

Note: Snowflake DDL auto-commits, so the transaction only makes DML-only
migrations atomic. A DDL migration that fails part-way is left unrecorded
and rerun next time, which is why migrations use IF NOT EXISTS.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import logging

from repo_pulse.config import ROOT, env
from repo_pulse.db import execute_script

log = logging.getLogger(__name__)

MIGRATIONS_DIR = ROOT / "migrations"
PATTERN = re.compile(r"^V(\d+)__(.+)\.sql$")

# Bootstrap must be self-sufficient: SCHEMA_MIGRATIONS lives inside the
# database that V001 creates. Names come from the same env vars get_connection() uses.
BOOTSTRAP = """
CREATE WAREHOUSE IF NOT EXISTS {wh} WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;
USE WAREHOUSE {wh};
CREATE DATABASE IF NOT EXISTS {db};
USE DATABASE {db};
CREATE SCHEMA IF NOT EXISTS META;
CREATE TABLE IF NOT EXISTS META.SCHEMA_MIGRATIONS (
    VERSION    INTEGER       NOT NULL PRIMARY KEY,
    NAME       STRING        NOT NULL,
    CHECKSUM   STRING        NOT NULL,
    APPLIED_AT TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);
"""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str


def _checksum(path: Path) -> str:
    # Normalise line endings so a CRLF checkout on Windows hashes the same as LF.
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    found: dict[int, Migration] = {}
    for path in sorted(directory.glob("V*.sql")):
        m = PATTERN.match(path.name)
        if not m:
            raise SystemExit(f"Bad migration filename: {path.name} (expected V001__name.sql)")
        version = int(m.group(1))
        if version in found:
            raise SystemExit(f"Duplicate migration version {version}: {found[version].path.name}, {path.name}")
        found[version] = Migration(version, m.group(2), path, _checksum(path))
    return [found[v] for v in sorted(found)]


def _bootstrap(cur) -> None:
    execute_script(cur, BOOTSTRAP.format(wh=env("SNOWFLAKE_WAREHOUSE"), db=env("SNOWFLAKE_DATABASE")))


def _applied(cur) -> dict[int, tuple[str, str]]:
    cur.execute("SELECT VERSION, NAME, CHECKSUM FROM META.SCHEMA_MIGRATIONS")
    return {row[0]: (row[1], row[2]) for row in cur.fetchall()}


def _verify(migrations: list[Migration], applied: dict[int, tuple[str, str]]) -> None:
    problems = []
    for mig in migrations:
        if mig.version not in applied:
            continue
        name, checksum = applied[mig.version]
        if checksum != mig.checksum:
            problems.append(f"  V{mig.version:03d} {mig.path.name}: checksum changed since it was applied")
        elif name != mig.path.name:
            problems.append(f"  V{mig.version:03d}: recorded as {name}, found {mig.path.name}")
    if problems:
        raise SystemExit(
            "Applied migrations have been modified. Applied migrations are immutable; "
            "add a new migration instead.\n" + "\n".join(problems)
        )


def migrate(conn) -> list[Migration]:
    """Apply pending migrations; returns those applied in this run."""
    migrations = discover_migrations()
    with conn.cursor() as cur:
        _bootstrap(cur)
        applied = _applied(cur)
    _verify(migrations, applied)

    done: list[Migration] = []
    for mig in migrations:
        if mig.version in applied:
            continue
        log.info("applying %s", mig.path.name)
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            try:
                execute_script(cur, mig.path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO META.SCHEMA_MIGRATIONS (VERSION, NAME, CHECKSUM) VALUES (%s, %s, %s)",
                    (mig.version, mig.path.name, mig.checksum),
                )
                cur.execute("COMMIT")
            except Exception as exc:
                cur.execute("ROLLBACK")
                raise SystemExit(
                    f"Migration {mig.path.name} failed; rolled back and left unrecorded: {exc}"
                ) from exc
        done.append(mig)
    if not done:
        log.info("no pending migrations")
    return done
