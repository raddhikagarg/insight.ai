"""
Converts a natural-language business question into SQL.

Two paths:
1. LLM path (Gemini) -- used automatically when GEMINI_API_KEY is set.
2. Rule-based fallback -- a small pattern-matching engine covering the most
   common business questions (monthly sales, revenue by region, profit by
   category, top products/customers, growth, order counts). This keeps the
   project fully runnable/demoable without any API key, which is ideal for
   a capstone submission and grading.
"""
import re
from pathlib import Path
from . import llm
from .config import settings
from .database import get_schema_description

PROMPT_TEMPLATE = Path(__file__).parent.parent / "prompts" / "sql_prompt.txt"
if not PROMPT_TEMPLATE.exists():
    PROMPT_TEMPLATE = Path("/home/claude/InsightAI/prompts/sql_prompt.txt")


class SQLGenerationError(Exception):
    pass


def _llm_generate(question: str) -> str:
    template = PROMPT_TEMPLATE.read_text()
    prompt = template.format(
        schema=get_schema_description(),
        question=question,
        max_rows=settings.MAX_ROWS_RETURNED,
    )
    return llm.generate_text(prompt)


# ---------------------------------------------------------------------------
# Rule-based fallback engine
# ---------------------------------------------------------------------------
_RULES = [
    (
        re.compile(r"\bmonthly\b.*\bsales\b|\bsales\b.*\bmonth", re.I),
        """SELECT strftime('%Y-%m', date) AS month, SUM(revenue) AS total_revenue
           FROM sales GROUP BY month ORDER BY month;""",
    ),
    (
        re.compile(r"(highest|top).*\bregion\b|\bregion\b.*(highest revenue|top)", re.I),
        """SELECT region, SUM(revenue) AS total_revenue
           FROM sales GROUP BY region ORDER BY total_revenue DESC;""",
    ),
    (
        re.compile(r"\bprofit\b.*\bcategory\b|\bcategory\b.*\bprofit\b", re.I),
        """SELECT category, SUM(profit) AS total_profit
           FROM sales GROUP BY category ORDER BY total_profit DESC;""",
    ),
    (
        re.compile(r"\bcustomer(s)? growth\b|\bnew customers\b", re.I),
        """SELECT strftime('%Y-%m', date) AS month, COUNT(DISTINCT customer) AS customers
           FROM sales GROUP BY month ORDER BY month;""",
    ),
    (
        re.compile(r"\btop\b.*\bproduct", re.I),
        """SELECT product, SUM(revenue) AS total_revenue, SUM(quantity) AS units_sold
           FROM sales GROUP BY product ORDER BY total_revenue DESC LIMIT 10;""",
    ),
    (
        re.compile(r"\btop\b.*\bcustomer", re.I),
        """SELECT customer, SUM(revenue) AS total_revenue
           FROM sales GROUP BY customer ORDER BY total_revenue DESC LIMIT 10;""",
    ),
    (
        re.compile(r"\border(s)? by region\b|\border count", re.I),
        """SELECT region, COUNT(DISTINCT order_id) AS orders
           FROM sales GROUP BY region ORDER BY orders DESC;""",
    ),
    (
        re.compile(r"\brevenue\b.*\bquarter\b|\bquarter(ly)?\b.*\brevenue", re.I),
        """SELECT (CAST(strftime('%m', date) AS INTEGER) - 1) / 3 + 1 AS quarter,
                  strftime('%Y', date) AS year, SUM(revenue) AS total_revenue
           FROM sales GROUP BY year, quarter ORDER BY year, quarter;""",
    ),
    (
        re.compile(r"\btotal\b.*\brevenue\b|\brevenue\b.*\btotal\b", re.I),
        "SELECT SUM(revenue) AS total_revenue FROM sales;",
    ),
    (
        re.compile(r"\btotal\b.*\bprofit\b|\bprofit\b.*\btotal\b", re.I),
        "SELECT SUM(profit) AS total_profit FROM sales;",
    ),
    (
        re.compile(r"\bcategory\b.*\brevenue\b|\brevenue\b.*\bcategory\b", re.I),
        """SELECT category, SUM(revenue) AS total_revenue
           FROM sales GROUP BY category ORDER BY total_revenue DESC;""",
    ),
]

_DEFAULT_FALLBACK_SQL = """
SELECT strftime('%Y-%m', date) AS month, region, category,
       SUM(revenue) AS total_revenue, SUM(profit) AS total_profit
FROM sales GROUP BY month, region, category ORDER BY month LIMIT 200;
"""


def _rule_based_generate(question: str) -> str:
    for pattern, sql in _RULES:
        if pattern.search(question):
            return sql.strip()
    # No rule matched -- return a broad, still-useful default view rather
    # than failing, so the user always gets *something* back.
    return _DEFAULT_FALLBACK_SQL.strip()


def generate_sql(question: str, table_name: str = "sales") -> tuple[str, str]:
    """
    Returns (sql, engine_used) where engine_used is 'gemini' or 'rule_based'.
    Falls back to rule-based automatically if the LLM call fails for any
    reason (missing key, network error, quota, malformed response, etc.)
    """
    if llm.is_available():
        try:
            sql = _llm_generate(question)
            sql = sql.strip().strip(";") + ";"
            return sql, "gemini"
        except Exception as e:
            print(f"[sql_generator] Gemini failed, using rule-based fallback: {e}")

    sql = _rule_based_generate(question)
    if table_name != "sales":
        sql = sql.replace("FROM sales", f"FROM {table_name}")
    return sql, "rule_based"
