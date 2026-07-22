"""
Minimal session-based auth gate. This is intentionally simple (a single
hardcoded demo account) -- good enough for a capstone/demo, not meant as
real production auth. Swap `_check_credentials` for a real user store
(database table + hashed passwords) before deploying for real users.
"""
import streamlit as st

DEMO_USERNAME = "admin"
DEMO_PASSWORD = "admin123"


def _check_credentials(username: str, password: str) -> bool:
    return username == DEMO_USERNAME and password == DEMO_PASSWORD


def is_logged_in() -> bool:
    return st.session_state.get("logged_in", False)


def login(username: str, password: str) -> bool:
    if _check_credentials(username, password):
        st.session_state["logged_in"] = True
        st.session_state["username"] = username
        return True
    return False


def logout():
    st.session_state["logged_in"] = False
    st.session_state.pop("username", None)


def require_login():
    """Call at the top of any page that should be gated. Stops execution
    and points the user to the Login page if they aren't signed in."""
    if not is_logged_in():
        st.warning("Please log in first.")
        st.page_link("pages/Login.py", label="Go to Login")
        st.stop()
