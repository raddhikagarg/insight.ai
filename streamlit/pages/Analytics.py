import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.io as pio
from utils.auth import require_login
from utils.api import ask_question
from utils.theme import apply_theme

st.set_page_config(page_title="Analytics — InsightAI", layout="wide")
apply_theme()
require_login()

st.title("Analytics Overview")
DEFAULT_DATASET = "uploaded_sales_dataset_v2"

active_table = st.session_state.get("active_table", DEFAULT_DATASET)
st.session_state["active_table"] = active_table

PRESET_VIEWS = [
    ("Revenue by Region", "Which region generated the highest revenue?"),
    ("Profit by Category", "Profit by category"),
    ("Monthly Revenue Trend", "Show monthly sales"),
    ("Top Products", "Top 10 products by revenue"),
]

for title, question in PRESET_VIEWS:
    with st.container(border=True):
        st.subheader(title)
        with st.spinner(f"Loading '{title}'..."):
            response = ask_question(question, active_table)
        if response and response.get("chart_json"):
            fig = pio.from_json(response["chart_json"])
            st.plotly_chart(fig, use_container_width=True)
        elif response:
            st.dataframe(pd.DataFrame(response["rows"], columns=response["columns"]), use_container_width=True)
        else:
            st.caption("Could not load this view.")
    st.write("")
