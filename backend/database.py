"""
Database engine + session handling using SQLAlchemy.
Defaults to SQLite (database/sales.db) for local dev/demo; swap
DATABASE_URL in .env to a Postgres URL for production.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_raw_query(sql: str, params: dict | None = None):
    """Execute a read-only SQL string and return (columns, rows)."""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return columns, rows


def get_schema_description() -> str:
    """Introspect the DB and build a human-readable schema summary for the
    LLM prompt (table names + columns + types)."""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    lines = []
    for table_name in inspector.get_table_names():
        cols = inspector.get_columns(table_name)
        col_desc = ", ".join(f"{c['name']} ({c['type']})" for c in cols)
        lines.append(f"Table `{table_name}`: {col_desc}")
    return "\n".join(lines) if lines else "No tables found."
