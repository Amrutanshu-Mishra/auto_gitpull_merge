import streamlit as st

from common import CONFIG, conn, select_repo
from app import queries

st.set_page_config(page_title="repo-pulse · Ask", layout="wide")
st.title("Ask")

CONTEXT_ISSUES = 30

PROMPT = """You are an engineering analyst. Answer the question using only the GitHub issues listed
below for the repository {repo}. Cite issue numbers like #123. If the issues do not contain
the answer, say so.

Issues (most recently updated first):
{issues}

Question: {question}
Answer:"""

repo = select_repo()
question = st.text_area("Question", placeholder="What are users complaining about most this month?")

if repo and st.button("Ask", type="primary") and question.strip():
    ctx = queries.recent_issue_context(conn(), repo, CONTEXT_ISSUES)
    if ctx.empty:
        st.info("No issues for this repo yet.")
    else:
        lines = [
            f"- #{r.ISSUE_NUMBER} [{r.STATE}{', ' + r.CATEGORY if r.CATEGORY else ''}] {r.TITLE}"
            + (f" — {r.SUMMARY}" if r.SUMMARY else "")
            for r in ctx.itertuples()
        ]
        prompt = PROMPT.format(repo=repo, issues="\n".join(lines), question=question.strip())
        with st.spinner(f"Asking {CONFIG.cortex.complete_model}…"):
            answer = queries.complete(conn(), CONFIG.cortex.complete_model, prompt)
        st.markdown(answer)
        with st.expander(f"Context sent ({len(lines)} issues)"):
            st.code("\n".join(lines))
