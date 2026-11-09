"""Tầng Extract: đọc từ OLTP. Chỉ ĐỌC, không ghi gì vào nguồn."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import sqlalchemy as sa


def query_df(conn, sql: str, **params) -> pd.DataFrame:
    """Chạy SQL -> DataFrame (không dùng pandas.read_sql để khỏi phụ thuộc phiên bản pandas/SQLAlchemy)."""
    result = conn.execute(sa.text(sql), params)
    return pd.DataFrame(result.fetchall(), columns=list(result.keys()))


def _where(since: datetime | None, column: str) -> str:
    return f" WHERE {column} > :since" if since is not None else ""


def extract_transactions(conn, since: datetime | None) -> pd.DataFrame:
    # LEFT JOIN: giao dịch mồ côi (sản phẩm không còn) vẫn được đưa lên để tầng Transform ghi nhận & từ chối.
    return query_df(conn, f"""
        SELECT t.transaction_id, t.product_id, t.buyer_id, p.seller_id, t.amount, t.status,
               t.transaction_date, t.updated_at AS tx_updated_at,
               p.price AS list_price, p.created_at AS listed_at
        FROM transactions t LEFT JOIN products p ON p.product_id = t.product_id
        {_where(since, 't.updated_at')}""", **({"since": since} if since else {}))


def extract_users(conn, since: datetime | None) -> pd.DataFrame:
    # Không lấy email / password_hash: không cần cho phân tích.
    return query_df(conn, f"""
        SELECT user_id, student_id, full_name, major, created_at, updated_at FROM users
        {_where(since, 'updated_at')}""", **({"since": since} if since else {}))


def extract_products(conn, since: datetime | None) -> pd.DataFrame:
    return query_df(conn, f"""
        SELECT product_id, category_id, title, condition, price, status, created_at, updated_at FROM products
        {_where(since, 'updated_at')}""", **({"since": since} if since else {}))


def extract_categories(conn) -> pd.DataFrame:
    """Bảng nhỏ và không có updated_at -> đọc toàn bộ mỗi lần."""
    return query_df(conn, "SELECT category_id, category_name FROM categories")


def source_counts(conn) -> dict[str, int]:
    return {t: conn.scalar(sa.text(f"SELECT COUNT(*) FROM {t}")) for t in ("users", "products", "transactions")}
