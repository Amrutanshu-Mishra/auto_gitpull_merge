"""Cortex enrichment: STAGING.STG_ISSUES -> ANALYTICS.ISSUES_ENRICHED, in batches.

Each batch is one MERGE whose source subquery picks the next `batch_size` issues that are
new or whose updated_at moved, and runs the Cortex functions inside Snowflake. Nothing is
pulled into Python. Loops until a MERGE touches zero rows.

SENTIMENT / CLASSIFY_TEXT / SUMMARIZE are task functions with no model parameter;
EMBED_TEXT_768 takes config.cortex.embed_model. MODEL_VERSION records exactly what was used.
"""

from __future__ import annotations

import json
import logging
import math

from repo_pulse.config import Config
from repo_pulse.runs import logged_step, new_run_id

log = logging.getLogger(__name__)

SUMMARIZE_MIN_BODY_CHARS = 300
EMBED_MAX_CHARS = 2000  # EMBED_TEXT_768 input is capped at 512 tokens

PENDING_COUNT_SQL = """
SELECT COUNT(*)
FROM STAGING.STG_ISSUES s
LEFT JOIN ANALYTICS.ISSUES_ENRICHED e ON e.repo = s.repo AND e.issue_number = s.issue_number
WHERE e.issue_number IS NULL OR s.updated_at > e.updated_at
"""

BATCH_MERGE_SQL = """
MERGE INTO ANALYTICS.ISSUES_ENRICHED t
USING (
    WITH todo AS (
        SELECT s.repo, s.issue_number, s.updated_at, s.title, s.body
        FROM STAGING.STG_ISSUES s
        LEFT JOIN ANALYTICS.ISSUES_ENRICHED e
               ON e.repo = s.repo AND e.issue_number = s.issue_number
        WHERE e.issue_number IS NULL OR s.updated_at > e.updated_at
        ORDER BY s.updated_at, s.repo, s.issue_number
        LIMIT %(batch_size)s
    ),
    prepared AS (
        SELECT *, CONCAT_WS(' ', title, COALESCE(body, '')) AS text FROM todo
    )
    SELECT
        repo,
        issue_number,
        updated_at,
        SNOWFLAKE.CORTEX.SENTIMENT(text)                                             AS sentiment,
        SNOWFLAKE.CORTEX.CLASSIFY_TEXT(text, PARSE_JSON(%(categories)s)):label::STRING AS category,
        CASE WHEN LENGTH(body) > %(summarize_min)s
             THEN SNOWFLAKE.CORTEX.SUMMARIZE(body) END                               AS summary,
        SNOWFLAKE.CORTEX.EMBED_TEXT_768(%(embed_model)s, LEFT(text, %(embed_max)s))   AS embedding,
        %(model_version)s                                                            AS model_version
    FROM prepared
) s
   ON t.repo = s.repo AND t.issue_number = s.issue_number
WHEN MATCHED THEN UPDATE SET
    updated_at = s.updated_at, sentiment = s.sentiment, category = s.category,
    summary = s.summary, embedding = s.embedding, model_version = s.model_version,
    enriched_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT
    (repo, issue_number, updated_at, sentiment, category, summary, embedding, model_version)
    VALUES (s.repo, s.issue_number, s.updated_at, s.sentiment, s.category, s.summary,
            s.embedding, s.model_version)
"""


def model_version(config: Config) -> str:
    return "|".join(
        [
            "sentiment=SENTIMENT",
            "classify=CLASSIFY_TEXT",
            "summarize=SUMMARIZE",
            f"embed=EMBED_TEXT_768:{config.cortex.embed_model}",
        ]
    )


def enrich(conn, config: Config, run_id: str | None = None) -> int:
    """Enrich every new/changed issue. Returns total rows merged."""
    run_id = run_id or new_run_id()
    params = {
        "batch_size": config.batch_size,
        "categories": json.dumps(config.categories),
        "summarize_min": SUMMARIZE_MIN_BODY_CHARS,
        "embed_model": config.cortex.embed_model,
        "embed_max": EMBED_MAX_CHARS,
        "model_version": model_version(config),
    }
    total = 0
    with logged_step(conn, run_id, "enrich:issues") as result:
        pending = count_pending(conn)
        # Each batch removes its rows from the candidate set, so this bounds the loop even
        # if a row somehow keeps qualifying.
        max_batches = math.ceil(pending / config.batch_size) + 1
        log.info("enrich:issues %d issues pending, batch size %d", pending, config.batch_size)
        for _ in range(max_batches):
            n = run_batch(conn, params)
            if n == 0:
                break
            total += n
            result["rows"] = total
            log.info("enrich:issues merged %d (total %d)", n, total)
        else:
            raise RuntimeError(f"enrich did not converge after {max_batches} batches")
    return total


def count_pending(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(PENDING_COUNT_SQL)
        return int(cur.fetchone()[0])


def run_batch(conn, params: dict) -> int:
    with conn.cursor() as cur:
        cur.execute(BATCH_MERGE_SQL, params)
        # MERGE returns one row: (rows inserted, rows updated)
        row = cur.fetchone() or (0, 0)
    return int(sum(v or 0 for v in row))
