"""
InsightAI - Streamlit entry point.

Run with:
    streamlit run streamlit/app.py

All other pages live in pages/ and are auto-discovered by Streamlit's
multipage nav (the folder MUST be named "pages" and sit next to this file).
"""

import os
import sys

sys.path.append(os.path.dirname(__file__))

import streamlit as st
from utils.api import check_health
from utils.auth import is_logged_in
from utils.theme import apply_theme

st.set_page_config(
    page_title="InsightAI — Conversational BI",
    layout="wide",
)

apply_theme()

# Backend API URL
if "api_url" not in st.session_state:
    st.session_state["api_url"] = os.getenv(
        "INSIGHTAI_API_URL",
        "http://127.0.0.1:8000/api",
    )

st.title("InsightAI")
st.caption(
    "Ask business questions in plain English. Get SQL, charts, and insights back."
)

left, mid, right = st.columns([1, 2, 1])

with mid:
    with st.container(border=True):

        if check_health():
            st.success("Backend connected.")
        else:
            st.warning(
                f"""
⚠️ **Backend unreachable**

Current API URL:

`{st.session_state['api_url']}`

If you're running locally, start the backend with:


