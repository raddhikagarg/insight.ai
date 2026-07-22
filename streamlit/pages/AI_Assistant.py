import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.io as pio
from utils.auth import require_login
from utils.api import ask_question
from utils.theme import apply_theme

st.set_page_config(page_title="AI Assistant — InsightAI", layout="wide")
apply_theme()
require_login()

st.title("AI Business Assistant")
st.caption(
    "This talks to the same NL-to-SQL engine as the Dashboard (Gemini if configured, "
    "otherwise a rule-based fallback) — not a fixed list of keywords."
)

active_table = st.session_state.get("active_table", "sales")

with st.container(border=True):
    question = st.text_area(
        "Ask your business question",
        placeholder="e.g. Give me a business summary, or 'Which category is most profitable?'",
    )

    if st.button("Analyze", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("Please enter a question.")
            st.stop()

        with st.spinner("Thinking..."):
            response = ask_question(question, active_table)

        if response:
            df = pd.DataFrame(response["rows"], columns=response["columns"])

            st.markdown("##### Generated SQL")
            st.code(response["sql"], language="sql")

            st.markdown("##### Result")
            st.dataframe(df, use_container_width=True)

            if response.get("chart_json"):
                fig = pio.from_json(response["chart_json"])
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("##### Insight")
            st.success(response["insight_text"])

st.divider()
st.caption(
    "Try: total revenue · monthly sales · profit by category · top products · "
    "customer growth · which region has the highest revenue"
)
