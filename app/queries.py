"""Every SQL the app runs, as functions taking a connection + parameters with bind variables.

Works against either the local connector (repo_pulse.db) or a Snowpark session from
Streamlit in Snowflake. Queries are written with `?` placeholders; `run()` adapts them.
Pages never contain SQL.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

TTL = 600


# --- connection ---------------------------------------------------------------

def get_conn():
    """Snowpark active session inside Streamlit in Snowflake, else the local connector."""
    try:
        from snowflake.snowpark.context import get_active_session

        return get_active_session()
    except Exception:
        from repo_pulse.db import get_connection

        return get_connection()


def _is_snowpark(conn) -> bool:
    return hasattr(conn, "sql") and not hasattr(conn, "cursor")


def run(conn, sql: str, params: tuple = ()) -> pd.DataFrame:
    if _is_snowpark(conn):
        return conn.sql(sql, params=list(params)).to_pandas()
    # connector default paramstyle is pyformat; our SQL never contains a literal '?'
    with conn.cursor() as cur:
        cur.execute(sql.replace("?", "%s"), params)
        return cur.fetch_pandas_all()


def scalar(conn, sql: str, params: tuple = ()):
    df = run(conn, sql, params)
    return None if df.empty else df.iloc[0, 0]


# --- overview -----------------------------------------------------------------

@st.cache_data(ttl=TTL)
def list_repos(_conn) -> list[str]:
    return run(_conn, "SELECT DISTINCT repo FROM STAGING.STG_ISSUES ORDER BY 1")["REPO"].tolist()


@st.cache_data(ttl=TTL)
def repo_kpis(_conn, repo: str) -> pd.DataFrame:
    return run(
        _conn,
        """
        SELECT open_issues, closed_issues, avg_sentiment, median_days_open,
               issues_per_week, issues_created_last_7d
        FROM ANALYTICS.REPO_HEALTH WHERE repo = ?
        """,
        (repo,),
    )


@st.cache_data(ttl=TTL)
def issues_by_category(_conn, repo: str) -> pd.DataFrame:
    return run(
        _conn,
        """
        SELECT COALESCE(e.category, 'unclassified') AS category, COUNT(*) AS issues
        FROM STAGING.STG_ISSUES i
        LEFT JOIN ANALYTICS.ISSUES_ENRICHED e ON e.repo = i.repo AND e.issue_number = i.issue_number
        WHERE i.repo = ?
        GROUP BY 1 ORDER BY 2 DESC
        """,
        (repo,),
    )


@st.cache_data(ttl=TTL)
def issues_per_week(_conn, repo: str) -> pd.DataFrame:
    return run(
        _conn,
        """
        SELECT DATE_TRUNC('week', created_at)::DATE AS week, COUNT(*) AS issues
        FROM STAGING.STG_ISSUES WHERE repo = ?
        GROUP BY 1 ORDER BY 1
        """,
        (repo,),
    )


@st.cache_data(ttl=TTL)
def most_negative_open(_conn, repo: str, n: int = 10) -> pd.DataFrame:
    return run(
        _conn,
        """
        SELECT i.issue_number, i.title, e.sentiment, e.category, e.summary, i.days_open, i.html_url
        FROM STAGING.STG_ISSUES i
        JOIN ANALYTICS.ISSUES_ENRICHED e ON e.repo = i.repo AND e.issue_number = i.issue_number
        WHERE i.repo = ? AND i.is_open AND e.sentiment IS NOT NULL
        ORDER BY e.sentiment ASC, i.updated_at DESC
        LIMIT ?
        """,
        (repo, n),
    )


# --- similar issues -----------------------------------------------------------

@st.cache_data(ttl=TTL)
def similar_issues(_conn, text: str, embed_model: str, repo: str | None = None, k: int = 5) -> pd.DataFrame:
    return run(
        _conn,
        """
        WITH q AS (SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_768(?, ?) AS v)
        SELECT i.repo, i.issue_number, i.title, i.state, e.category,
               VECTOR_COSINE_SIMILARITY(e.embedding, q.v) AS score, i.html_url
        FROM ANALYTICS.ISSUES_ENRICHED e
        JOIN STAGING.STG_ISSUES i ON i.repo = e.repo AND i.issue_number = e.issue_number
        CROSS JOIN q
        WHERE e.embedding IS NOT NULL AND (? IS NULL OR i.repo = ?)
        ORDER BY score DESC
        LIMIT ?
        """,
        (embed_model, text, repo, repo, k),
    )


# --- ask ----------------------------------------------------------------------

@st.cache_data(ttl=TTL)
def recent_issue_context(_conn, repo: str, n: int = 30) -> pd.DataFrame:
    return run(
        _conn,
        """
        SELECT i.issue_number, i.title, i.state, e.category,
               COALESCE(e.summary, LEFT(i.body, 300)) AS summary
        FROM STAGING.STG_ISSUES i
        LEFT JOIN ANALYTICS.ISSUES_ENRICHED e ON e.repo = i.repo AND e.issue_number = i.issue_number
        WHERE i.repo = ?
        ORDER BY i.updated_at DESC
        LIMIT ?
        """,
        (repo, n),
    )


@st.cache_data(ttl=TTL)
def complete(_conn, model: str, prompt: str) -> str:
    return str(scalar(_conn, "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?)", (model, prompt)))
