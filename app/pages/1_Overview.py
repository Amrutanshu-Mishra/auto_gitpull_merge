import pandas as pd
import streamlit as st

from common import conn, select_repo
from app import queries

st.set_page_config(page_title="repo-pulse · Overview", layout="wide")
st.title("Overview")

repo = select_repo()
if repo:
    c = conn()
    kpis = queries.repo_kpis(c, repo)
    if kpis.empty:
        st.info("No health metrics yet for this repo. Run `make transform` and `make enrich`.")
    else:
        k = kpis.iloc[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("Open issues", int(k["OPEN_ISSUES"] or 0))
        col2.metric("Avg sentiment", "—" if pd.isna(k["AVG_SENTIMENT"]) else f"{k['AVG_SENTIMENT']:.2f}")
        col3.metric("Median days open", "—" if pd.isna(k["MEDIAN_DAYS_OPEN"]) else f"{k['MEDIAN_DAYS_OPEN']:.0f}")

    left, right = st.columns(2)
    with left:
        st.subheader("Issues by category")
        st.bar_chart(queries.issues_by_category(c, repo).set_index("CATEGORY"))
    with right:
        st.subheader("Issues created per week")
        st.line_chart(queries.issues_per_week(c, repo).set_index("WEEK"))

    st.subheader("Most negative open issues")
    neg = queries.most_negative_open(c, repo, 10)
    if neg.empty:
        st.info("No enriched open issues yet.")
    else:
        st.dataframe(
            neg,
            hide_index=True,
            use_container_width=True,
            column_config={
                "ISSUE_NUMBER": st.column_config.NumberColumn("#", format="%d"),
                "TITLE": "Title",
                "SENTIMENT": st.column_config.NumberColumn("Sentiment", format="%.2f"),
                "CATEGORY": "Category",
                "SUMMARY": "Summary",
                "DAYS_OPEN": st.column_config.NumberColumn("Days open", format="%d"),
                "HTML_URL": st.column_config.LinkColumn("Link", display_text="open"),
            },
        )
