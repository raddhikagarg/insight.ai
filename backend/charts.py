"""
Turns a SQL result set into a chart.

Public entrypoints:
  pick_chart_type(columns, rows) -> "line" | "bar" | "pie" | "scatter" | "kpi"
  build_figure(chart_type, columns, rows) -> dict shaped like a Plotly figure:
      {"data": [...], "layout": {...}}

No LLM involved here -- purely structural heuristics based on column count,
data types, and cardinality. Colors/typography are deliberately minimal:
the frontend (ResultChart.tsx) overrides paper_bgcolor/font/margin on
render, so this module only needs to set the data-relevant parts
(trace type, x/y, titles).
"""
from datetime import date, datetime
from typing import Any, Dict, List

ChartType = str  # "line" | "bar" | "pie" | "scatter" | "kpi"

_PIE_MAX_CATEGORIES = 6


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_dateish(col_name: str, rows: List[Dict[str, Any]], col: str) -> bool:
    if "date" in col_name.lower() or "month" in col_name.lower() or "year" in col_name.lower():
        return True
    return all(isinstance(r.get(col), (date, datetime)) for r in rows) if rows else False


def _numeric_columns(columns: List[str], rows: List[Dict[str, Any]]) -> List[str]:
    return [c for c in columns if rows and all(_is_numeric(r.get(c)) for r in rows)]


def _date_columns(columns: List[str], rows: List[Dict[str, Any]]) -> List[str]:
    return [c for c in columns if _is_dateish(c, rows, c)]


def pick_chart_type(columns: List[str], rows: List[Dict[str, Any]]) -> ChartType:
    if not rows or not columns:
        return "bar"  # nothing to show; caller should handle empty state separately

    numeric_cols = _numeric_columns(columns, rows)
    date_cols = _date_columns(columns, rows)
    categorical_cols = [c for c in columns if c not in numeric_cols and c not in date_cols]

    # Single value -> headline KPI
    if len(rows) == 1 and len(numeric_cols) >= 1:
        return "kpi"

    # A date/time axis with a numeric measure -> trend line
    if date_cols and numeric_cols and len(rows) > 1:
        return "line"

    # One category + one numeric, few distinct categories -> pie (share of whole)
    if categorical_cols and numeric_cols and not date_cols:
        distinct = len({r[categorical_cols[0]] for r in rows})
        if distinct <= _PIE_MAX_CATEGORIES and distinct == len(rows):
            return "pie"
        return "bar"

    # Two numeric columns, no category -> scatter (correlation-style question)
    if len(numeric_cols) >= 2 and not categorical_cols and not date_cols:
        return "scatter"

    return "bar"


def build_figure(chart_type: ChartType, columns: List[str], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    numeric_cols = _numeric_columns(columns, rows)
    date_cols = _date_columns(columns, rows)
    categorical_cols = [c for c in columns if c not in numeric_cols and c not in date_cols]

    if chart_type == "kpi":
        value_col = numeric_cols[0]
        return {
            "data": [{
                "type": "indicator",
                "mode": "number",
                "value": rows[0][value_col],
                "title": {"text": value_col.replace("_", " ").title()},
            }],
            "layout": {},
        }

    if chart_type == "line":
        x_col = date_cols[0]
        y_col = numeric_cols[0]
        sorted_rows = sorted(rows, key=lambda r: str(r[x_col]))
        return {
            "data": [{
                "type": "scatter",
                "mode": "lines+markers",
                "x": [str(r[x_col]) for r in sorted_rows],
                "y": [r[y_col] for r in sorted_rows],
                "name": y_col.replace("_", " ").title(),
            }],
            "layout": {
                "xaxis": {"title": x_col.replace("_", " ").title()},
                "yaxis": {"title": y_col.replace("_", " ").title()},
            },
        }

    if chart_type == "pie":
        label_col = categorical_cols[0]
        value_col = numeric_cols[0]
        return {
            "data": [{
                "type": "pie",
                "labels": [r[label_col] for r in rows],
                "values": [r[value_col] for r in rows],
                "hole": 0.5,
            }],
            "layout": {},
        }

    if chart_type == "scatter":
        x_col, y_col = numeric_cols[0], numeric_cols[1]
        return {
            "data": [{
                "type": "scatter",
                "mode": "markers",
                "x": [r[x_col] for r in rows],
                "y": [r[y_col] for r in rows],
            }],
            "layout": {
                "xaxis": {"title": x_col.replace("_", " ").title()},
                "yaxis": {"title": y_col.replace("_", " ").title()},
            },
        }

    # Default: bar chart, category vs first numeric measure
    label_col = categorical_cols[0] if categorical_cols else columns[0]
    value_col = numeric_cols[0] if numeric_cols else columns[-1]
    sorted_rows = sorted(rows, key=lambda r: r.get(value_col, 0), reverse=True)
    return {
        "data": [{
            "type": "bar",
            "x": [r[label_col] for r in sorted_rows],
            "y": [r[value_col] for r in sorted_rows],
        }],
        "layout": {
            "xaxis": {"title": label_col.replace("_", " ").title()},
            "yaxis": {"title": value_col.replace("_", " ").title()},
        },
    }
