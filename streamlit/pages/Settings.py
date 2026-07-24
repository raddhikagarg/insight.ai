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

# ---------------- Backend ----------------
with st.container(border=True):
    st.markdown("#### Backend connection")

    st.text_input(
        "API base URL",
        value=get_api_url(),
        disabled=True,
        help="Configured automatically from Streamlit Secrets."
    )

    if st.button("Test Connection"):
        import requests

        try:
            r = requests.get(f"{get_api_url()}/health", timeout=5)
            if r.ok:
                st.success("Backend is connected.")
            else:
                st.error("Backend responded with an error.")
        except Exception as e:
            st.error(f"Cannot connect to backend.\n\n{e}")

# ---------------- Dataset ----------------
st.divider()

with st.container(border=True):
    st.markdown("#### Active dataset")

    datasets = get_datasets()

    if datasets:
        table_names = [d["table_name"] for d in datasets]

        DEFAULT_DATASET = "uploaded_sales_dataset_v2"

        # Initialize the active dataset if it doesn't exist
        if "active_table" not in st.session_state:
            st.session_state["active_table"] = DEFAULT_DATASET

        current = st.session_state["active_table"]

        # If the current/default dataset isn't available, use the first one
        if current not in table_names:
            current = table_names[0]
            st.session_state["active_table"] = current

        chosen = st.selectbox(
            "Dataset used throughout the application",
            table_names,
            index=table_names.index(current),
        )

        st.session_state["active_table"] = chosen

        st.success(f"Current dataset: **{chosen}**")

    else:
        st.warning("No datasets available.")

# ---------------- AI ----------------
st.divider()

with st.container(border=True):
    st.markdown("#### AI Engine")

    st.info(
        "If a Gemini API key is configured, InsightAI uses Gemini for "
        "natural language to SQL generation and business insights.\n\n"
        "Otherwise it automatically falls back to the built-in "
        "rule-based SQL engine."
    )
# ---------------- Account ----------------
st.divider()

with st.container(border=True):
    st.markdown("#### Account")

    st.write(f"Signed in as **{st.session_state.get('username', 'unknown')}**")

    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()

# ---------------- Session ----------------
st.divider()

with st.container(border=True):
    st.markdown("#### Session")

    if st.button("Clear Session", use_container_width=True):
        keys = [
            "last_response",
            "prefill_question",
            "active_table",
        ]

        for key in keys:
            st.session_state.pop(key, None)

        st.success("Session cleared.")
        st.rerun()