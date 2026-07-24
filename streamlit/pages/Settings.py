import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.auth import require_login, logout
from utils.api import get_datasets, get_api_url
from utils.theme import apply_theme

st.set_page_config(page_title="Settings — InsightAI", layout="wide")
apply_theme()
require_login()

st.title("Settings")

with st.container(border=True):
    st.markdown("#### Backend connection")
    new_url = st.text_input("API base URL", value=get_api_url())
    if new_url != get_api_url():
        st.session_state["api_url"] = new_url
        st.rerun()

st.divider()
with st.container(border=True):
    st.markdown("#### Active dataset")
    datasets = get_datasets()
    if datasets:
        table_names = [d["table_name"] for d in datasets]
        current = st.session_state.get("active_table", "uploaded_sales_dataset_v2")
        chosen = st.selectbox(
            "Table used by Dashboard / Analytics / AI Assistant",
            table_names,
            index=table_names.index(current) if current in table_names else 0,
        )
        st.session_state["active_table"] = chosen
    else:
        st.caption("Could not load datasets.")

st.divider()
with st.container(border=True):
    st.markdown("#### LLM engine")
    st.caption(
        "InsightAI uses Google Gemini for NL-to-SQL and insights when `GEMINI_API_KEY` "
        "is set in `backend/.env`. Without a key, it automatically falls back to a "
        "rule-based engine so the app keeps working for demos."
    )

st.divider()
with st.container(border=True):
    st.markdown("#### Account")
    st.write(f"Signed in as **{st.session_state.get('username', 'unknown')}**")
    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()

st.divider()
with st.container(border=True):
    st.markdown("#### Danger zone")
    if st.button("Clear session state (client-side only)", use_container_width=True):
        for key in ["last_response", "prefill_question", "active_table"]:
            st.session_state.pop(key, None)
        st.success("Session cleared.")
        st.rerun()
