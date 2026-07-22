import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.auth import require_login
from utils.api import get_history
from utils.theme import apply_theme

st.set_page_config(page_title="Reports — InsightAI", layout="wide")
apply_theme()
require_login()

st.title("Reports & Query History")

history = get_history(limit=50)

if not history:
    st.info("No queries yet — ask something on the Dashboard or AI Assistant first.")
    st.stop()

with st.container(border=True):
    df = pd.DataFrame(history)[["created_at", "question", "sql", "row_count"]]
    df.columns = ["Timestamp", "Question", "Generated SQL", "Rows"]
    st.dataframe(df, use_container_width=True, height=400)

st.divider()
with st.container(border=True):
    st.markdown("#### Re-run a previous question")
    choice = st.selectbox("Pick a question", [h["question"] for h in history])
    if st.button("Re-run on Dashboard", use_container_width=True):
        st.session_state["prefill_question"] = choice
        st.success("Question loaded — switch to Dashboard to see fresh results.")
        st.page_link("pages/Dashboard.py", label="Go to Dashboard")
