"""
SQLAlchemy ORM models.

`Sale` is the demo business table (seeded from database/sample_data.csv).
`QueryHistory` stores every natural-language question asked, its generated
SQL, and a timestamp -- powers the "Query History" sidebar feature.
`UploadedDataset` tracks CSV/Excel uploads that get turned into their own
SQLite tables at runtime.
"""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text
from datetime import datetime
from .database import Base


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, index=True)
    date = Column(Date, index=True)
    region = Column(String, index=True)
    category = Column(String, index=True)
    product = Column(String, index=True)
    customer = Column(String, index=True)
    quantity = Column(Integer)
    price = Column(Float)
    revenue = Column(Float)
    cost = Column(Float)
    profit = Column(Float)


class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text)
    generated_sql = Column(Text)
    row_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class UploadedDataset(Base):
    __tablename__ = "uploaded_datasets"

    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String, unique=True)
    original_filename = Column(String)
    n_rows = Column(Integer)
    n_columns = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
