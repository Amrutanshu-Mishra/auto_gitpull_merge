"""META.PIPELINE_RUNS logging shared by ingest / enrich."""

from __future__ import annotations

import traceback
import uuid
from contextlib import contextmanager


def new_run_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def logged_step(conn, run_id: str, step: str):
    """Insert a 'running' row, then mark success (with rows from the yielded dict) or failed."""
    result = {"rows": None}
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO META.PIPELINE_RUNS (RUN_ID, STEP, STATUS) VALUES (%s, %s, 'running')",
            (run_id, step),
        )
    try:
        yield result
    except Exception as exc:
        _finish(conn, run_id, step, "failed", result["rows"], f"{exc}\n{traceback.format_exc()}")
        raise
    _finish(conn, run_id, step, "success", result["rows"], None)


def _finish(conn, run_id, step, status, rows, error) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE META.PIPELINE_RUNS SET STATUS = %s, FINISHED_AT = CURRENT_TIMESTAMP(), "
            "ROWS = %s, ERROR = %s WHERE RUN_ID = %s AND STEP = %s",
            (status, rows, error, run_id, step),
        )
