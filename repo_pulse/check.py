"""`make check`: verify env, key file, Snowflake connectivity and Cortex access. PASS/FAIL per item."""

from __future__ import annotations

import os
from pathlib import Path

from repo_pulse.config import Config

REQUIRED_ENV = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PRIVATE_KEY_FILE",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "GITHUB_TOKEN",
)


def _report(results: list[tuple[str, bool, str]]) -> bool:
    ok_all = True
    for name, ok, detail in results:
        ok_all &= ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    return ok_all


def check(config: Config) -> bool:
    """Returns True when every check passes. Never raises for an expected failure."""
    results: list[tuple[str, bool, str]] = []

    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    results.append(("env vars set", not missing, f"missing: {', '.join(missing)}" if missing else ""))
    if missing:
        return _report(results)

    key = Path(os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"]).expanduser()
    results.append(("private key file exists", key.is_file(), str(key)))
    if not key.is_file():
        return _report(results)

    from repo_pulse.db import get_connection

    try:
        conn = get_connection()
    except Exception as exc:  # auth / network / account id problems
        results.append(("snowflake connection", False, _short(exc)))
        return _report(results)

    try:
        results.append(_query(conn, "snowflake connection", "SELECT CURRENT_USER() || ' as ' || CURRENT_ROLE()"))
        results.append(_query(conn, "warehouse + database", "SELECT CURRENT_WAREHOUSE() || ' / ' || CURRENT_DATABASE()",
                              expect_non_null=True, hint="run `make migrate` first"))
        results.append(_query(conn, "cortex SENTIMENT", "SELECT SNOWFLAKE.CORTEX.SENTIMENT('this library is great')"))
        results.append(_query(conn, f"cortex COMPLETE ({config.cortex.complete_model})",
                              "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, 'say hi')", (config.cortex.complete_model,)))
        results.append(_query(conn, f"cortex EMBED_TEXT_768 ({config.cortex.embed_model})",
                              "SELECT ARRAY_SIZE(SNOWFLAKE.CORTEX.EMBED_TEXT_768(%s, 'test'))",
                              (config.cortex.embed_model,), expect="768"))
    finally:
        conn.close()
    return _report(results)


def _query(conn, name, sql, params=(), expect=None, expect_non_null=False, hint=""):
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            value = cur.fetchone()[0]
    except Exception as exc:
        return (name, False, _short(exc))
    if expect_non_null and value is None:
        return (name, False, hint)
    if expect is not None and str(value) != expect:
        return (name, False, f"expected {expect}, got {value}")
    return (name, True, str(value)[:60].replace("\n", " "))


def _short(exc: Exception) -> str:
    return str(exc).splitlines()[0][:160]
