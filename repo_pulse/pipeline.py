"""Pipeline core: extract per repo from a watermark, stage via write_pandas, MERGE into RAW."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import pandas as pd
from snowflake.connector.pandas_tools import write_pandas

from repo_pulse.config import Config
from repo_pulse.runs import logged_step, new_run_id
from repo_pulse.sources.base import Extractor, get_extractor

log = logging.getLogger(__name__)

RAW_TABLE = "GITHUB_EVENTS_RAW"

MERGE_SQL = """
MERGE INTO RAW.{raw} t
USING (
    SELECT SOURCE, REPO, ENTITY_ID,
           TO_TIMESTAMP_NTZ(UPDATED_AT) AS UPDATED_AT,
           PARSE_JSON(PAYLOAD) AS PAYLOAD
    FROM RAW.{tmp}
) s
   ON t.SOURCE = s.SOURCE AND t.REPO = s.REPO AND t.ENTITY_ID = s.ENTITY_ID
WHEN MATCHED AND s.UPDATED_AT > t.UPDATED_AT THEN UPDATE SET
    UPDATED_AT = s.UPDATED_AT, PAYLOAD = s.PAYLOAD, FETCHED_AT = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (SOURCE, REPO, ENTITY_ID, UPDATED_AT, PAYLOAD)
    VALUES (s.SOURCE, s.REPO, s.ENTITY_ID, s.UPDATED_AT, s.PAYLOAD)
"""

WATERMARK_SQL = """
MERGE INTO META.INGEST_WATERMARKS t
USING (SELECT %s AS SOURCE, %s AS REPO, TO_TIMESTAMP_NTZ(%s) AS LAST_UPDATED_AT, %s AS ROWS_LOADED) s
   ON t.SOURCE = s.SOURCE AND t.REPO = s.REPO
WHEN MATCHED THEN UPDATE SET
    LAST_UPDATED_AT = COALESCE(s.LAST_UPDATED_AT, t.LAST_UPDATED_AT),
    LAST_RUN_AT = CURRENT_TIMESTAMP(), ROWS_LOADED = s.ROWS_LOADED
WHEN NOT MATCHED THEN INSERT (SOURCE, REPO, LAST_UPDATED_AT, LAST_RUN_AT, ROWS_LOADED)
    VALUES (s.SOURCE, s.REPO, s.LAST_UPDATED_AT, CURRENT_TIMESTAMP(), s.ROWS_LOADED)
"""


def run_ingest(conn, config: Config, source_name: str) -> str:
    """Ingest one source for every configured repo. Returns the run id."""
    extractor = get_extractor(source_name)(config)
    run_id = new_run_id()
    for repo in config.repos:
        step = f"ingest:{source_name}:{repo}"
        with logged_step(conn, run_id, step) as result:
            result["rows"] = _ingest_repo(conn, extractor, repo)
        log.info("%s: %s rows", step, result["rows"])
    return run_id


def _ingest_repo(conn, extractor: Extractor, repo: str) -> int:
    since = _read_watermark(conn, extractor.name, repo)
    records = list(extractor.extract(repo, since))
    if records:
        _merge(conn, extractor.name, repo, records)
    high = max((r["updated_at"] for r in records), default=None)
    _write_watermark(conn, extractor.name, repo, high, len(records))
    return len(records)


def _read_watermark(conn, source: str, repo: str) -> datetime | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT LAST_UPDATED_AT FROM META.INGEST_WATERMARKS WHERE SOURCE = %s AND REPO = %s",
            (source, repo),
        )
        row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return row[0].replace(tzinfo=timezone.utc)


def _write_watermark(conn, source: str, repo: str, high: datetime | None, rows: int) -> None:
    with conn.cursor() as cur:
        cur.execute(WATERMARK_SQL, (source, repo, _ntz(high), rows))


def _merge(conn, source: str, repo: str, records: list) -> None:
    df = pd.DataFrame(
        {
            "SOURCE": source,
            "REPO": repo,
            "ENTITY_ID": [r["entity_id"] for r in records],
            "UPDATED_AT": [_ntz(r["updated_at"]) for r in records],
            "PAYLOAD": [json.dumps(r["payload"], separators=(",", ":")) for r in records],
        }
    )
    tmp = f"TMP_{source.upper()}_{uuid.uuid4().hex[:8]}"
    write_pandas(
        conn, df, tmp, schema="RAW", auto_create_table=True, table_type="temporary", overwrite=True
    )
    with conn.cursor() as cur:
        cur.execute(MERGE_SQL.format(raw=RAW_TABLE, tmp=tmp))
        cur.execute(f"DROP TABLE IF EXISTS RAW.{tmp}")


def _ntz(ts: datetime | None) -> str | None:
    """UTC ISO string without offset, for TIMESTAMP_NTZ columns."""
    return None if ts is None else ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
