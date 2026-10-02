import streamlit as st

from common import CONFIG, conn, select_repo  # noqa: F401  (ensures import path + connection)

st.set_page_config(page_title="repo-pulse", layout="wide")
st.title("repo-pulse")
st.write("GitHub engineering intelligence on Snowflake. Pick a page on the left.")
st.page_link("pages/1_Overview.py", label="Overview")
st.page_link("pages/2_Similar_Issues.py", label="Similar Issues")
st.page_link("pages/3_Ask.py", label="Ask")
