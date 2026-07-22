"""
Generates 12 months of realistic, seasonal sales data for the InsightAI demo
and loads it into whichever database DATABASE_URL points at.

- No DATABASE_URL set -> writes a local sales.db (SQLite), good for testing
  the backend with `uvicorn app:app` before you deploy.
- DATABASE_URL set to a Postgres connection string -> seeds your hosted
  Neon/Supabase/Vercel Postgres database directly. Run this once after
  creating the database, before your first deploy.

Usage:
    # local SQLite:
    python generate_sample_data.py

    # hosted Postgres:
    DATABASE_URL="postgresql+psycopg2://user:pass@host/db" python generate_sample_data.py
"""
import os
import random
from datetime import date, timedelta
import csv

random.seed(42)

REGIONS = ["North", "South", "East", "West", "Central"]
CATEGORIES = {
    "Electronics": ["Laptop", "Smartphone", "Headphones", "Smartwatch", "Tablet"],
    "Furniture": ["Office Chair", "Standing Desk", "Bookshelf", "Sofa"],
    "Apparel": ["T-Shirt", "Jeans", "Jacket", "Sneakers"],
    "Groceries": ["Coffee Beans", "Snack Box", "Organic Tea"],
}
CUSTOMERS = [f"Customer_{i:03d}" for i in range(1, 121)]

PRICE_RANGES = {
    "Laptop": (700, 1500), "Smartphone": (300, 1200), "Headphones": (50, 300),
    "Smartwatch": (100, 400), "Tablet": (200, 900),
    "Office Chair": (80, 400), "Standing Desk": (150, 600),
    "Bookshelf": (40, 200), "Sofa": (300, 1200),
    "T-Shirt": (10, 40), "Jeans": (30, 90), "Jacket": (50, 200), "Sneakers": (40, 180),
    "Coffee Beans": (8, 25), "Snack Box": (5, 20), "Organic Tea": (6, 22),
}

START_DATE = date(2025, 7, 1)
N_DAYS = 365


def generate_rows() -> list[dict]:
    rows = []
    order_id = 1000
    for day_offset in range(N_DAYS):
        current_date = START_DATE + timedelta(days=day_offset)
        month = current_date.month
        seasonal_multiplier = 1.6 if month in (11, 12) else (0.7 if month == 2 else 1.0)
        daily_orders = max(1, int(random.gauss(8 * seasonal_multiplier, 3)))

        for _ in range(daily_orders):
            category = random.choice(list(CATEGORIES.keys()))
            product = random.choice(CATEGORIES[category])
            low, high = PRICE_RANGES[product]
            price = round(random.uniform(low, high), 2)
            quantity = random.randint(1, 5)
            revenue = round(price * quantity, 2)
            cost = round(revenue * random.uniform(0.55, 0.8), 2)
            profit = round(revenue - cost, 2)

            rows.append({
                "order_id": f"ORD{order_id}",
                "date": current_date.isoformat(),
                "region": random.choice(REGIONS),
                "category": category,
                "product": product,
                "customer": random.choice(CUSTOMERS),
                "quantity": quantity,
                "price": price,
                "revenue": revenue,
                "cost": cost,
                "profit": profit,
            })
            order_id += 1
    return rows


def write_csv(rows: list[dict], path: str = "sample_data.csv"):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {path}")


def seed_database(rows: list[dict]):
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "sqlite:///./sales.db")
    is_sqlite = "sqlite" in database_url
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine = create_engine(database_url, connect_args=connect_args)

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS sales"))
        id_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
        conn.execute(text(f"""
            CREATE TABLE sales (
                id {id_type},
                order_id VARCHAR(50), date DATE, region VARCHAR(50), category VARCHAR(50),
                product VARCHAR(100), customer VARCHAR(50), quantity INTEGER,
                price FLOAT, revenue FLOAT, cost FLOAT, profit FLOAT
            )
        """))
        conn.execute(
            text("""INSERT INTO sales (order_id, date, region, category, product, customer,
                                        quantity, price, revenue, cost, profit)
                     VALUES (:order_id, :date, :region, :category, :product, :customer,
                             :quantity, :price, :revenue, :cost, :profit)"""),
            rows,
        )
    print(f"Seeded '{database_url.split('@')[-1] if '@' in database_url else database_url}' with {len(rows)} rows in 'sales' table.")


if __name__ == "__main__":
    rows = generate_rows()
    print(f"Generated {len(rows)} sales records.")
    write_csv(rows)
    seed_database(rows)
