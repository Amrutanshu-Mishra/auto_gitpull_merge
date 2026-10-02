import streamlit as st

from common import CONFIG, conn, select_repo
from app import queries

st.set_page_config(page_title="repo-pulse · Similar Issues", layout="wide")
st.title("Similar Issues")

repo = select_repo()
all_repos = st.sidebar.checkbox("Search across all repos", value=False)

text = st.text_input("Describe an issue", placeholder="e.g. app crashes when uploading a large CSV")
if text.strip():
    df = queries.similar_issues(
        conn(), text.strip(), CONFIG.cortex.embed_model, None if all_repos else repo, 5
    )
    if df.empty:
        st.info("No embedded issues yet. Run `make enrich`.")
    else:
        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "REPO": "Repo",
                "ISSUE_NUMBER": st.column_config.NumberColumn("#", format="%d"),
                "TITLE": "Title",
                "STATE": "State",
                "CATEGORY": "Category",
                "SCORE": st.column_config.NumberColumn("Similarity", format="%.3f"),
                "HTML_URL": st.column_config.LinkColumn("Link", display_text="open"),
            },
        )
