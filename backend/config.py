"""
Central configuration for InsightAI backend.
All values can be overridden via environment variables (see .env.example).
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sales.db")

    # --- LLM (Gemini) ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    # If no API key is set, the app automatically falls back to a rule-based
    # NL->SQL engine so the whole project still runs end-to-end for demos.
    USE_LLM: bool = bool(GEMINI_API_KEY)

    # --- CORS ---
    ALLOWED_ORIGINS: list[str] = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8501"
    ).split(",")

    # --- App ---
    APP_NAME: str = "InsightAI"
    ALLOWED_SQL_KEYWORDS = {"SELECT", "WITH"}  # read-only, safety first
    BLOCKED_SQL_KEYWORDS = {
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
        "CREATE", "REPLACE", "GRANT", "REVOKE", "ATTACH", "PRAGMA"
    }
    MAX_ROWS_RETURNED: int = 5000

    # --- Reports ---
    REPORTS_DIR: str = os.getenv("REPORTS_DIR", "../reports/generated_reports")

settings = Settings()
