"""
Central API router for InsightAI. Mounted at /api in app.py.

Pipeline for POST /ask (the core feature):
    question --intent + NL->SQL--> sql_generator
             --safety check-------> sql_validator
             --execute------------> database.run_raw_query
             --pick + build--------> charts
             --summarize-----------> _generate_insight (this file, LLM + rule-based fallback)
             --log------------------> QueryHistory

POST /upload and POST /report delegate their heavy lifting to
upload_handler.py and report_export.py respectively, keeping this file
focused on HTTP concerns (validation, status codes, response shaping).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from . import charts
from . import llm
from . import report_export
from . import sql_generator
from . import sql_validator
from . import upload_handler
from .config import settings
from .database import engine, get_db, run_raw_query
from .models import QueryHistory

router = APIRouter()

INSIGHTS_PROMPT_TEMPLATE = Path(__file__).parent.parent / "prompts" / "insights_prompt.txt"
MAX_ROWS_SENT_TO_LLM = 50


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str
    table_name: str = "sales"


class AskResponse(BaseModel):
    question: str
    sql: str
    sql_engine: Literal["gemini", "rule_based"]
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    chart_type: str
    chart_json: Optional[str] = None
    insight_text: str
    insight_engine: Literal["gemini", "rule_based"]


class HistoryItem(BaseModel):
    id: int
    question: str
    sql: str
    row_count: int
    created_at: str


class DatasetInfo(BaseModel):
    table_name: str
    filename: Optional[str] = None
    rows: Optional[int] = None
    columns: Optional[int] = None


class Kpis(BaseModel):
    total_revenue: float
    total_profit: float
    total_orders: int
    total_customers: int


class UploadResponse(BaseModel):
    table_name: str
    n_rows: int
    n_columns: int
    columns: List[str]
    preview: List[Dict[str, Any]]


class ReportRequest(BaseModel):
    question: str = ""
    sql: str = ""
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    columns: Optional[List[str]] = None
    insight_text: str = ""
    format: Literal["pdf", "csv"] = "pdf"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _known_tables() -> set:
    return set(inspect(engine).get_table_names())


def _require_table(table_name: str) -> str:
    """Validates table_name against real tables in the DB. Doing this before
    any f-string SQL interpolation (here and in sql_generator's fallback
    engine) is what keeps table_name safe from injection -- it must exactly
    match an existing table, not arbitrary user text."""
    table_name = (table_name or "sales").strip()
    if table_name not in _known_tables():
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' was not found.")
    return table_name


def _table_columns(table_name: str) -> set:
    return {c["name"] for c in inspect(engine).get_columns(table_name)}


# ---------------------------------------------------------------------------
# Insight generation (LLM with rule-based fallback -- mirrors sql_generator.py)
# ---------------------------------------------------------------------------
def _generate_insight(question: str, columns: List[str], rows: List[Dict[str, Any]]) -> tuple[str, str]:
    if llm.is_available():
        try:
            return _llm_insight(question, columns, rows), "gemini"
        except Exception as e:
            print(f"[routes] Gemini insight generation failed, using rule-based fallback: {e}")
    return _rule_based_insight(columns, rows), "rule_based"


def _llm_insight(question: str, columns: List[str], rows: List[Dict[str, Any]]) -> str:
    template = INSIGHTS_PROMPT_TEMPLATE.read_text()
    sample = rows[:MAX_ROWS_SENT_TO_LLM]
    prompt = template.format(question=question, data=json.dumps(sample, default=str))
    return llm.generate_text(prompt)


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _rule_based_insight(columns: List[str], rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "- No data was returned for this question. Try a different date range or rephrasing."

    numeric_cols = [c for c in columns if all(_is_numeric(r.get(c)) for r in rows if r.get(c) is not None)]
    numeric_cols = [c for c in numeric_cols if any(r.get(c) is not None for r in rows)]
    date_cols = [c for c in columns if any(t in c.lower() for t in ("date", "month", "year"))]
    categorical_cols = [c for c in columns if c not in numeric_cols and c not in date_cols]

    bullets = [f"- The query returned {len(rows)} row{'s' if len(rows) != 1 else ''} across {len(columns)} columns."]

    if numeric_cols:
        primary = numeric_cols[0]
        values = [r.get(primary) or 0 for r in rows]
        total = sum(values)
        avg = total / len(values)
        bullets.append(
            f"- Total {primary.replace('_', ' ')}: {total:,.2f}, averaging {avg:,.2f} per row."
        )

    if categorical_cols and numeric_cols:
        cat, metric = categorical_cols[0], numeric_cols[0]
        ranked = sorted(rows, key=lambda r: r.get(metric) or 0, reverse=True)
        best, worst = ranked[0], ranked[-1]
        if best is not worst:
            bullets.append(
                f"- {best.get(cat)} leads on {metric.replace('_', ' ')} at {best.get(metric):,.2f}, "
                f"while {worst.get(cat)} trails at {worst.get(metric):,.2f}."
            )

    if date_cols and numeric_cols and len(rows) > 1:
        metric = numeric_cols[0]
        ordered = sorted(rows, key=lambda r: str(r.get(date_cols[0])))
        first_val, last_val = ordered[0].get(metric) or 0, ordered[-1].get(metric) or 0
        if first_val:
            pct = (last_val - first_val) / abs(first_val) * 100
            direction = "increased" if pct >= 0 else "decreased"
            bullets.append(
                f"- {metric.replace('_', ' ').title()} {direction} {abs(pct):.1f}% from the first to the last period shown."
            )

    bullets.append("- Recommendation: dig into the top and bottom performers above to replicate what's working and fix what isn't.")
    return "\n".join(bullets)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@router.get("/health")
def health():
    try:
        run_raw_query("SELECT 1;")
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "llm_available": llm.is_available()}


# ---------------------------------------------------------------------------
# Core NL -> SQL -> chart -> insight pipeline
# ---------------------------------------------------------------------------
@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, db: Session = Depends(get_db)):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    table_name = _require_table(payload.table_name)

    try:
        raw_sql, sql_engine_used = sql_generator.generate_sql(question, table_name=table_name)
        safe_sql = sql_validator.validate_sql(raw_sql)
    except sql_validator.UnsafeSQLError as e:
        raise HTTPException(status_code=400, detail=f"Generated SQL failed the safety check: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate SQL: {e}")

    try:
        columns, rows = run_raw_query(safe_sql)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {e}")

    chart_type = charts.pick_chart_type(columns, rows)
    chart_json = None
    if rows:
        try:
            chart_json = json.dumps(charts.build_figure(chart_type, columns, rows), default=str)
        except Exception as e:
            print(f"[routes] Chart build failed, returning without a chart: {e}")

    insight_text, insight_engine = _generate_insight(question, columns, rows)

    try:
        db.add(QueryHistory(question=question, generated_sql=safe_sql, row_count=len(rows)))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[routes] Failed to write query history (non-fatal): {e}")

    return AskResponse(
        question=question,
        sql=safe_sql,
        sql_engine=sql_engine_used,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        chart_type=chart_type,
        chart_json=chart_json,
        insight_text=insight_text,
        insight_engine=insight_engine,
    )


# ---------------------------------------------------------------------------
# History / datasets / KPIs
# ---------------------------------------------------------------------------
@router.get("/history", response_model=List[HistoryItem])
def history(limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    entries = (
        db.query(QueryHistory)
        .order_by(QueryHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        HistoryItem(
            id=e.id,
            question=e.question,
            sql=e.generated_sql,
            row_count=e.row_count or 0,
            created_at=e.created_at.isoformat() if e.created_at else "",
        )
        for e in entries
    ]


@router.get("/datasets", response_model=List[DatasetInfo])
def datasets(db: Session = Depends(get_db)):
    return upload_handler.list_datasets(db)


@router.get("/kpis", response_model=Kpis)
def kpis(table_name: str = "sales"):
    table_name = _require_table(table_name)
    available = _table_columns(table_name)

    metric_exprs = {
        "total_revenue": ("SUM(revenue)", "revenue"),
        "total_profit": ("SUM(profit)", "profit"),
        "total_orders": ("COUNT(DISTINCT order_id)", "order_id"),
        "total_customers": ("COUNT(DISTINCT customer)", "customer"),
    }
    select_clause = ", ".join(
        f"{expr} AS {alias}" if needed_col in available else f"0 AS {alias}"
        for alias, (expr, needed_col) in metric_exprs.items()
    )

    try:
        _, rows = run_raw_query(f"SELECT {select_clause} FROM {table_name};")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute KPIs: {e}")

    result = rows[0] if rows else {}
    return Kpis(**{alias: result.get(alias) or 0 for alias in metric_exprs})


# ---------------------------------------------------------------------------
# Upload (delegates to upload_handler.py)
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw_bytes = await file.read()
    try:
        result = upload_handler.handle_upload(file, raw_bytes, db)
    except upload_handler.UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error processing upload: {e}")
    return UploadResponse(**result)


# ---------------------------------------------------------------------------
# Report export (delegates to report_export.py)
# ---------------------------------------------------------------------------
@router.post("/report")
def report(payload: ReportRequest):
    columns = payload.columns or (list(payload.rows[0].keys()) if payload.rows else [])

    try:
        if payload.format == "csv":
            content = report_export.generate_csv(columns, payload.rows)
            media_type = "text/csv"
        else:
            content = report_export.generate_pdf(
                question=payload.question,
                sql=payload.sql,
                columns=columns,
                rows=payload.rows,
                insight_text=payload.insight_text,
            )
            media_type = "application/pdf"
    except report_export.ReportExportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    report_export.save_report_copy(content, payload.format)  # best-effort archive, never raises
    filename = report_export.safe_download_filename(payload.question, payload.format)

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
