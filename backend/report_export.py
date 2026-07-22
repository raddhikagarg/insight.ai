"""
Turns one Q&A result (question + SQL + rows + AI insight) into a
downloadable executive report -- either a formatted PDF or a plain CSV.

This is the "Report Automation" step of the pipeline: everything upstream
(sql_generator -> sql_validator -> database -> charts -> insights) already
happened by the time this module is called; it only has to package the
result nicely.

Public entrypoints (consumed by routes.py):
    generate_pdf(question, sql, columns, rows, insight_text) -> bytes
    generate_csv(columns, rows) -> bytes
    save_report_copy(content, extension) -> str | None   # best-effort archive
"""
from __future__ import annotations

import csv
import io
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .config import settings

MAX_TABLE_ROWS_IN_PDF = 100  # keeps the PDF readable; full data is in the CSV export
PAGE_WIDTH, PAGE_HEIGHT = letter
CONTENT_WIDTH = PAGE_WIDTH - 1.2 * inch  # matches the 0.6in margins set below


class ReportExportError(Exception):
    """Raised for any user-facing report generation failure."""


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------
def generate_csv(columns: List[str], rows: List[Dict[str, Any]]) -> bytes:
    if not columns:
        raise ReportExportError("No columns to export.")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: _flatten(row.get(c)) for c in columns})
    return buffer.getvalue().encode("utf-8")


def _flatten(value: Any) -> Any:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------
def generate_pdf(
    question: str,
    sql: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    insight_text: str,
) -> bytes:
    if not columns:
        raise ReportExportError("No columns to export.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="InsightAI Business Report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Heading1"], spaceAfter=2)
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"], textColor=colors.grey, spaceAfter=14)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], spaceBefore=16, spaceAfter=6, textColor=colors.HexColor("#1f2937"))
    body_style = ParagraphStyle("Body", parent=styles["Normal"], leading=14)
    bullet_style = ParagraphStyle("Bullet", parent=body_style, leftIndent=14, spaceAfter=4)
    code_style = ParagraphStyle(
        "Code",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11,
        backColor=colors.HexColor("#f3f4f6"),
        borderPadding=8,
    )

    story: List[Any] = []
    story.append(Paragraph("InsightAI Business Report", title_style))
    story.append(Paragraph(
        f"Generated {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}", meta_style
    ))

    story.append(Paragraph("Question", h2_style))
    story.append(Paragraph(_escape(question) or "(no question provided)", body_style))

    story.append(Paragraph("AI-Generated Insight", h2_style))
    for line in _insight_lines(insight_text):
        story.append(Paragraph(f"&bull;&nbsp;&nbsp;{_escape(line)}", bullet_style))

    story.append(Paragraph("Generated SQL", h2_style))
    story.append(Paragraph(_escape(sql).replace("\n", "<br/>") or "(no SQL provided)", code_style))

    row_count = len(rows)
    shown_note = f", showing first {MAX_TABLE_ROWS_IN_PDF}" if row_count > MAX_TABLE_ROWS_IN_PDF else ""
    story.append(Paragraph(f"Data ({row_count} row{'s' if row_count != 1 else ''}{shown_note})", h2_style))

    if row_count:
        story.append(_build_table(columns, rows[:MAX_TABLE_ROWS_IN_PDF]))
    else:
        story.append(Paragraph("No rows were returned for this query.", body_style))

    story.append(Spacer(1, 18))
    story.append(Paragraph(
        f"{settings.APP_NAME} &mdash; AI-generated report. Verify figures against source systems before external distribution.",
        meta_style,
    ))

    try:
        doc.build(story)
    except Exception as e:
        raise ReportExportError(f"Failed to render PDF: {e}") from e

    return buffer.getvalue()


def _insight_lines(insight_text: str) -> List[str]:
    lines = [line.strip(" -*\u2022\t") for line in (insight_text or "").splitlines() if line.strip()]
    return lines or ["No insight was generated for this query."]


def _escape(text: Optional[str]) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_table(columns: List[str], rows: List[Dict[str, Any]]) -> Table:
    header = [str(c).replace("_", " ").title() for c in columns]
    data: List[List[str]] = [header]
    for row in rows:
        data.append([_format_cell(row.get(c)) for c in columns])

    col_width = max(CONTENT_WIDTH / max(len(columns), 1), 0.55 * inch)
    col_widths = [col_width] * len(columns)

    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


# ---------------------------------------------------------------------------
# Optional best-effort archive to disk (REPORTS_DIR). Never raises -- on
# read-only serverless filesystems (e.g. Vercel) this silently no-ops so it
# never breaks the actual download response.
# ---------------------------------------------------------------------------
def save_report_copy(content: bytes, extension: str) -> Optional[str]:
    try:
        os.makedirs(settings.REPORTS_DIR, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}_{uuid.uuid4().hex[:8]}.{extension}"
        path = os.path.join(settings.REPORTS_DIR, filename)
        with open(path, "wb") as f:
            f.write(content)
        return path
    except Exception:
        return None


def safe_download_filename(question: str, extension: str) -> str:
    """Builds a short, filesystem-safe filename from the question, for the
    Content-Disposition header (e.g. 'top_products_this_quarter.pdf')."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", (question or "insightai_report").strip().lower())
    slug = slug.strip("_")[:60] or "insightai_report"
    return f"{slug}.{extension}"
