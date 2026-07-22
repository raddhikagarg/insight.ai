import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.auth import login, logout, is_logged_in
from utils.theme import apply_theme

st.set_page_config(page_title="Login — InsightAI")
apply_theme()

st.title("Login")

left, mid, right = st.columns([1, 1.2, 1])
with mid:
    with st.container(border=True):
        if not is_logged_in():
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            if st.button("Login", type="primary", use_container_width=True):
                if login(username, password):
                    st.success("Login successful.")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")

            st.caption("Demo credentials: `admin` / `admin123`")
        else:
            st.success(f"Welcome, {st.session_state.get('username')}!")
            st.page_link("pages/Dashboard.py", label="Go to Dashboard")
            if st.button("Logout", use_container_width=True):
                logout()
                st.rerun()
