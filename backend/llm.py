"""
Thin wrapper around Google's Gemini API.

If GEMINI_API_KEY is not configured, `is_available()` returns False and
sql_generator.py / insights.py automatically use their rule-based fallback
paths, so the whole app still runs for demos/grading without any paid key.
"""
import json
from .config import settings

_client = None
if settings.USE_LLM:
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _client = genai.GenerativeModel(settings.GEMINI_MODEL)
    except Exception as e:  # library missing or bad key -> degrade gracefully
        print(f"[llm] Gemini init failed, falling back to rule-based engine: {e}")
        _client = None


def is_available() -> bool:
    return _client is not None


def generate_text(prompt: str, temperature: float = 0.2) -> str:
    """Send a prompt to Gemini and return plain text. Raises if unavailable."""
    if not _client:
        raise RuntimeError("Gemini client not configured")
    response = _client.generate_content(
        prompt,
        generation_config={"temperature": temperature},
    )
    return response.text.strip()


def generate_json(prompt: str) -> dict:
    """Ask Gemini for JSON and parse it, stripping markdown fences if present."""
    raw = generate_text(prompt)
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)
