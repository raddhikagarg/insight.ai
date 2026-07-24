"""
Loads sales_dataset_v2.csv into the 'sales' table.

Works with:
- SQLite (local)
- PostgreSQL (Render/Neon/Supabase)

Usage:

Local:
    python generate_sample_data.py

Render/Postgres:
    DATABASE_URL=<your_database_url> python generate_sample_data.py
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text

CSV_FILE = os.path.join(os.path.dirname(__file__), "sales_dataset_v2.csv")


def load_dataset():
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(f"Dataset not found: {CSV_FILE}")

    df = pd.read_csv(CSV_FILE)

    # Clean column names
    df.columns = (
        df.columns.str.strip()
                  .str.lower()
                  .str.replace(" ", "_")
    )

    # Convert date column if present
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date

    return df


def seed_database(df):
    database_url = os.getenv("DATABASE_URL", "sqlite:///./sales.db")

    is_sqlite = database_url.startswith("sqlite")

    connect_args = {"check_same_thread": False} if is_sqlite else {}

    engine = create_engine(
        database_url,
        connect_args=connect_args
    )

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS sales"))

    df.to_sql(
        "sales",
        con=engine,
        if_exists="replace",
        index=False
    )

    print(f"Successfully loaded {len(df)} rows into 'sales' table.")
    print(f"Database: {database_url}")


if __name__ == "__main__":
    df = load_dataset()

    print(f"Loaded CSV with {len(df)} rows.")
    print(f"Columns: {list(df.columns)}")

    seed_database(df)