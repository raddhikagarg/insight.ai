"""
Single place every Streamlit page goes through to talk to the FastAPI
backend. No page should call `requests` directly or read a local CSV --
this keeps every page in sync with whatever the backend actually returns.
"""
import requests
import streamlit as st


def get_api_url() -> str:
    return st.session_state.get("api_url", "http://127.0.0.1:8000/api")


def check_health() -> bool:
    try:
        r = requests.get(f"{get_api_url()}/health", timeout=3)
        return r.ok
    except Exception:
        return False


def ask_question(question: str, table_name: str = "sales") -> dict | None:
    try:
        resp = requests.post(
            f"{get_api_url()}/ask",
            json={"question": question, "table_name": table_name},
            timeout=60,
        )
        if resp.ok:
            return resp.json()
        st.error(f"Backend error: {resp.json().get('detail', resp.text)}")
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the backend. Make sure `uvicorn app:app --port 8000` is running.")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    return None


def get_history(limit: int = 20) -> list[dict]:
    try:
        r = requests.get(f"{get_api_url()}/history", params={"limit": limit}, timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


def get_datasets() -> list[dict]:
    try:
        r = requests.get(f"{get_api_url()}/datasets", timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


def get_kpis(table_name: str = "sales") -> dict:
    try:
        r = requests.get(f"{get_api_url()}/kpis", params={"table_name": table_name}, timeout=10)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def upload_dataset(filename: str, file_bytes: bytes) -> dict | None:
    try:
        resp = requests.post(
            f"{get_api_url()}/upload",
            files={"file": (filename, file_bytes)},
            timeout=60,
        )
        if resp.ok:
            return resp.json()
        st.error(f"Upload failed: {resp.json().get('detail', resp.text)}")
    except Exception as e:
        st.error(f"Upload failed: {e}")
    return None


def download_report(question: str, sql: str, rows: list[dict], insight_text: str, fmt: str = "pdf") -> bytes | None:
    try:
        resp = requests.post(
            f"{get_api_url()}/report",
            json={"question": question, "sql": sql, "rows": rows, "insight_text": insight_text, "format": fmt},
            timeout=30,
        )
        if resp.ok:
            return resp.content
        st.error("Report export failed.")
    except Exception as e:
        st.error(f"Report export failed: {e}")
    return None
