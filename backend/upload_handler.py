"""
Handles user-uploaded CSV / Excel files: parses them with pandas, cleans
and normalizes the data, loads it into a brand-new SQL table, and registers
it in `uploaded_datasets` so it shows up as a queryable data source next to
the built-in `sales` table.

This is the "Data Cleaning" + "Database Management" step of the pipeline
for user-supplied data (the seeded `sales` table is handled separately by
database/generate_sample_data.py). Once a file lands here, everything
downstream (sql_generator, charts, insights) treats it exactly like any
other table via `table_name`.

Public entrypoints (consumed by routes.py):
    handle_upload(file, raw_bytes, db) -> dict   # POST /upload
    list_datasets(db) -> list[dict]              # GET  /datasets
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from .database import engine, run_raw_query
from .models import UploadedDataset

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB -- generous for a demo, safe for serverless
PREVIEW_ROWS = 10
DATE_HINT_TOKENS = ("date", "time", "created", "updated", "timestamp", "day", "month", "year")


class UploadError(Exception):
    """Raised for any user-facing upload failure (bad file, empty data, parse error, etc.)."""


# ---------------------------------------------------------------------------
# Table / column naming
# ---------------------------------------------------------------------------
def _sanitize_identifier(raw: str, fallback: str = "column") -> str:
    """Turn arbitrary text into a safe, lowercase snake_case SQL identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", str(raw).strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    return cleaned


def _sanitize_table_name(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    name = _sanitize_identifier(stem, fallback="dataset")
    return f"uploaded_{name}"


def _unique_table_name(base_name: str) -> str:
    """Avoids clobbering an existing table (including `sales`) by appending
    a numeric suffix if the sanitized name is already taken."""
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    if base_name not in existing:
        return base_name
    counter = 2
    while f"{base_name}_{counter}" in existing:
        counter += 1
    return f"{base_name}_{counter}"


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------
def _dedupe_columns(columns: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    result = []
    for col in columns:
        clean = _sanitize_identifier(col)
        if clean in seen:
            seen[clean] += 1
            clean = f"{clean}_{seen[clean]}"
        else:
            seen[clean] = 0
        result.append(clean)
    return result


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Applies the "Data Cleaning" step: drop empty rows/cols, normalize
    column names, trim whitespace, coerce obvious numeric/date columns."""
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df.columns = _dedupe_columns(list(df.columns))

    # Trim whitespace on text columns and normalize empty-ish values to NaN.
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"": None, "nan": None, "NaN": None, "None": None, "null": None})

    # Best-effort date parsing for columns whose name hints at a date/time.
    for col in df.columns:
        if df[col].dtype == object and any(token in col for token in DATE_HINT_TOKENS):
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().mean() >= 0.7:
                df[col] = parsed.dt.date

    # Coerce columns that look numeric but got read in as text.
    for col in df.select_dtypes(include="object").columns:
        coerced = pd.to_numeric(df[col], errors="coerce")
        non_null = df[col].notna()
        if non_null.any() and coerced[non_null].notna().mean() >= 0.9:
            df[col] = coerced

    return df.reset_index(drop=True)


def _json_safe_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    safe: List[Dict[str, Any]] = []
    for row in records:
        safe_row: Dict[str, Any] = {}
        for key, value in row.items():
            if value is None:
                safe_row[key] = None
            elif hasattr(value, "isoformat"):
                safe_row[key] = value.isoformat()
            elif isinstance(value, float) and pd.isna(value):
                safe_row[key] = None
            else:
                safe_row[key] = value
        safe.append(safe_row)
    return safe


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def handle_upload(file: UploadFile, raw_bytes: bytes, db: Session) -> Dict[str, Any]:
    """
    Full upload pipeline: validate -> parse -> clean -> load into a new
    SQL table -> register in `uploaded_datasets`. Returns metadata plus a
    small preview so the frontend can render an instant confirmation table.

    Raises UploadError for any user-facing failure; callers should turn
    that into an HTTP 400.
    """
    filename = file.filename or "dataset"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadError(
            f"Unsupported file type '{ext or 'unknown'}'. Please upload a .csv, .xlsx, or .xls file."
        )

    if not raw_bytes:
        raise UploadError("The uploaded file is empty.")
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise UploadError(f"File too large ({len(raw_bytes) / 1_000_000:.1f}MB). Max size is 25MB.")

    buffer = BytesIO(raw_bytes)
    try:
        if ext == ".csv":
            df = pd.read_csv(buffer)
        else:
            df = pd.read_excel(buffer)
    except Exception as e:
        raise UploadError(f"Could not parse file: {e}") from e

    if df.shape[1] == 0:
        raise UploadError("No columns could be detected in the uploaded file.")
    if df.empty:
        raise UploadError("The uploaded file has no data rows.")

    df = _clean_dataframe(df)
    if df.empty:
        raise UploadError("No usable rows remained after cleaning (the file may have been all blank rows).")

    table_name = _unique_table_name(_sanitize_table_name(filename))

    try:
        df.to_sql(table_name, con=engine, if_exists="replace", index=False)
    except Exception as e:
        raise UploadError(f"Failed to load data into the database: {e}") from e

    dataset = UploadedDataset(
        table_name=table_name,
        original_filename=filename,
        n_rows=len(df),
        n_columns=df.shape[1],
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return {
        "table_name": table_name,
        "n_rows": len(df),
        "n_columns": df.shape[1],
        "columns": list(df.columns),
        "preview": _json_safe_records(df.head(PREVIEW_ROWS).to_dict(orient="records")),
    }


def _table_row_count(table_name: str) -> Optional[int]:
    try:
        _, rows = run_raw_query(f"SELECT COUNT(*) AS c FROM {table_name};")
        return int(rows[0]["c"]) if rows else None
    except Exception:
        return None


def _table_column_count(table_name: str) -> Optional[int]:
    try:
        return len(inspect(engine).get_columns(table_name))
    except Exception:
        return None


def list_datasets(db: Session) -> List[Dict[str, Any]]:
    """Returns the built-in `sales` demo table plus every uploaded dataset,
    newest first, for the dataset switcher in the UI (GET /api/datasets)."""
    datasets = [{
        "table_name": "sales",
        "filename": "sample_data.csv (demo dataset)",
        "rows": _table_row_count("sales"),
        "columns": _table_column_count("sales"),
    }]
    for ds in db.query(UploadedDataset).order_by(UploadedDataset.uploaded_at.desc()).all():
        datasets.append({
            "table_name": ds.table_name,
            "filename": ds.original_filename,
            "rows": ds.n_rows,
            "columns": ds.n_columns,
        })
    return datasets
