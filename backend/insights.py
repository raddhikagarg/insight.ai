"""
Writes the natural-language insight for a query result.

Public entrypoint: generate_insight(question, columns, rows) -> str

If llm.is_available() is True, sends the data to Gemini using the template
in prompts/insights_prompt.txt. If the LLM is unavailable OR the call fails
for any reason (bad key, rate limit, network), falls back to
statistical_insight(), a rule-based summary that never raises -- so /ask
always returns *something* for the frontend to render.
"""
import json
import os
from datetime import date, datetime
from statistics import mean
from typing import Any, Dict, List

from . import llm

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "insights_prompt.txt")

with open(_PROMPT_PATH, "r") as f:
    _INSIGHT_TEMPLATE = f.read()

_MAX_ROWS_FOR_PROMPT = 50


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def generate_insight(question: str, columns: List[str], rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "That query didn't return any rows, so there's nothing to summarize yet."

    if llm.is_available():
        try:
            sample = rows[:_MAX_ROWS_FOR_PROMPT]
            prompt = _INSIGHT_TEMPLATE.format(
                question=question,
                data=json.dumps(sample, default=_json_default, indent=2),
            )
            return llm.generate_text(prompt)
        except Exception as e:
            print(f"[insights] Gemini call failed, using statistical fallback: {e}")

    return statistical_insight(question, columns, rows)


def _numeric_columns(columns: List[str], rows: List[Dict[str, Any]]) -> List[str]:
    numeric = []
    for col in columns:
        if all(isinstance(r.get(col), (int, float)) and not isinstance(r.get(col), bool) for r in rows):
            numeric.append(col)
    return numeric


def _categorical_columns(columns: List[str], rows: List[Dict[str, Any]], numeric: List[str]) -> List[str]:
    return [c for c in columns if c not in numeric]


def statistical_insight(question: str, columns: List[str], rows: List[Dict[str, Any]]) -> str:
    numeric_cols = _numeric_columns(columns, rows)
    cat_cols = _categorical_columns(columns, rows, numeric_cols)
    bullets: List[str] = []

    primary_metric = numeric_cols[0] if numeric_cols else None

    if primary_metric:
        total = sum(r[primary_metric] for r in rows)
        avg = mean(r[primary_metric] for r in rows)
        bullets.append(
            f"**{primary_metric.replace('_', ' ').title()}** totals {total:,.2f} "
            f"across {len(rows)} rows (avg {avg:,.2f})."
        )
    else:
        bullets.append(f"Returned {len(rows)} rows across {len(columns)} columns.")

    date_col = next((c for c in cat_cols if "date" in c.lower()), None)
    if date_col and primary_metric and len(rows) > 1:
        try:
            sorted_rows = sorted(rows, key=lambda r: str(r[date_col]))
            first_val = sorted_rows[0][primary_metric]
            last_val = sorted_rows[-1][primary_metric]
            if first_val:
                pct_change = ((last_val - first_val) / abs(first_val)) * 100
                direction = "up" if pct_change >= 0 else "down"
                bullets.append(
                    f"{primary_metric.replace('_', ' ').title()} moved {direction} "
                    f"{abs(pct_change):.1f}% from the first to the last period shown."
                )
        except (TypeError, ZeroDivisionError, KeyError):
            pass

    comparison_cols = [c for c in cat_cols if c != date_col]
    if comparison_cols and primary_metric and len(rows) > 1:
        group_col = comparison_cols[0]
        best = max(rows, key=lambda r: r[primary_metric])
        worst = min(rows, key=lambda r: r[primary_metric])
        if best[group_col] != worst[group_col]:
            bullets.append(
                f"**{best[group_col]}** leads on {primary_metric.replace('_', ' ')} "
                f"({best[primary_metric]:,.2f}), while **{worst[group_col]}** trails "
                f"({worst[primary_metric]:,.2f})."
            )

    if primary_metric and comparison_cols:
        bullets.append(
            f"Consider digging into why {comparison_cols[0].replace('_', ' ')} groups vary this much "
            f"on {primary_metric.replace('_', ' ')} before next period's planning."
        )
    elif primary_metric and date_col:
        bullets.append(
            f"Ask a follow-up question to break this {primary_metric.replace('_', ' ')} trend down "
            f"by region, category, or another dimension."
        )
    else:
        bullets.append("Ask a follow-up question to break this down further, e.g. by region or category.")

    return "\n".join(f"- {b}" for b in bullets)