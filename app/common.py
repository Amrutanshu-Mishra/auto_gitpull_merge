"""Shared page plumbing: import path, config, connection, sidebar repo selector."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app import queries  # noqa: E402
from repo_pulse.config import load_config  # noqa: E402

CONFIG = load_config()


@st.cache_resource
def conn():
    return queries.get_conn()


def select_repo() -> str | None:
    repos = queries.list_repos(conn())
    if not repos:
        st.warning("No issues ingested yet. Run `make all` first.")
        return None
    default = st.session_state.get("repo", repos[0])
    idx = repos.index(default) if default in repos else 0
    repo = st.sidebar.selectbox("Repository", repos, index=idx)
    st.session_state["repo"] = repo
    return repo
