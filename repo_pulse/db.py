"""Snowflake connection and SQL script helpers.

Authentication is key-pair only (SNOWFLAKE_PRIVATE_KEY_FILE). The connection is opened
without a warehouse or database because V001 creates both; they are switched to afterwards
if they already exist, so the first `migrate` on a fresh account works.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import snowflake.connector

from repo_pulse.config import env

log = logging.getLogger(__name__)

_LINE_COMMENT = re.compile(r"--[^\n]*")


def get_connection():
    key_file = Path(env("SNOWFLAKE_PRIVATE_KEY_FILE")).expanduser()
    if not key_file.is_file():
        raise SystemExit(f"SNOWFLAKE_PRIVATE_KEY_FILE not found: {key_file} (see SETUP.md section 4)")
    conn = snowflake.connector.connect(
        account=env("SNOWFLAKE_ACCOUNT"),
        user=env("SNOWFLAKE_USER"),
        private_key_file=str(key_file),
        role=env("SNOWFLAKE_ROLE"),
        client_session_keep_alive=True,
    )
    _use_if_exists(conn, "WAREHOUSE", env("SNOWFLAKE_WAREHOUSE"))
    _use_if_exists(conn, "DATABASE", env("SNOWFLAKE_DATABASE"))
    return conn


def _use_if_exists(conn, kind: str, name: str) -> None:
    with conn.cursor() as cur:
        cur.execute(f"SHOW {kind}S LIKE %s", (name,))
        if cur.fetchone():
            cur.execute(f"USE {kind} {name}")
        else:
            log.debug("%s %s does not exist yet (created by V001)", kind.lower(), name)


def split_statements(sql: str) -> list[str]:
    """Split a script on `;`, ignoring `--` comments (which may themselves contain `;`).

    Good enough for our DDL; string literals containing `;` are not supported in scripts.
    """
    stripped = _LINE_COMMENT.sub("", sql)
    return [s.strip() for s in stripped.split(";") if s.strip()]


def execute_script(cur, sql: str) -> None:
    for stmt in split_statements(sql):
        cur.execute(stmt)
