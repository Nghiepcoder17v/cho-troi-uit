"""Tầng Load: upsert vào Data Warehouse. Upsert viết bằng SQLAlchemy Core thuần (chạy được trên SQL Server và SQLite)."""
from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
import sqlalchemy as sa

from . import dwh_schema as S
from .transform import build_dim_date


def to_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list dict toàn kiểu Python gốc (NaN/NaT -> None) để driver nhận được."""
    obj = df.astype(object)
    obj = obj.where(pd.notna(obj), None)
    records = obj.to_dict("records")
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, pd.Timestamp):
                rec[k] = v.to_pydatetime()
            elif isinstance(v, np.integer):
                rec[k] = int(v)
            elif isinstance(v, np.floating):
                rec[k] = float(v)
            elif isinstance(v, np.bool_):
                rec[k] = bool(v)
    return records


def _chunks(items: list, size: int = 5000):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def upsert(conn, table: sa.Table, df: pd.DataFrame, key: str, now: datetime) -> tuple[int, int]:
    """Thêm dòng mới, cập nhật dòng đã có (theo khoá tự nhiên `key`). Trả về (số_thêm, số_cập_nhật).

    Idempotent: chạy lại với cùng dữ liệu cho cùng kết quả. Cập nhật CHỈ khi thuộc tính thực sự khác
    sẽ chính xác hơn, nhưng ghi đè toàn bộ thuộc tính cho đơn giản (khối lượng cập nhật nhỏ).
    """
    if df.empty:
        return 0, 0
    if "etl_loaded_at" in table.c:
        df = df.assign(etl_loaded_at=now)
    existing = {r[0] for r in conn.execute(sa.select(table.c[key]))}
    is_new = ~df[key].isin(existing)
    new_rows, old_rows = to_records(df[is_new]), to_records(df[~is_new])

    for part in _chunks(new_rows):
        conn.execute(sa.insert(table), part)
    if old_rows:
        value_cols = [c for c in old_rows[0] if c != key]
        stmt = (sa.update(table).where(table.c[key] == sa.bindparam("b_key"))
                .values({c: sa.bindparam(f"b_{c}") for c in value_cols}))
        payload = [{"b_key": r[key], **{f"b_{c}": r[c] for c in value_cols}} for r in old_rows]
        for part in _chunks(payload):
            conn.execute(stmt, part)
    return len(new_rows), len(old_rows)


def key_map(conn, table: sa.Table, natural: str, surrogate: str) -> dict[int, int]:
    return {r[0]: r[1] for r in conn.execute(sa.select(table.c[natural], table.c[surrogate]))}


def refresh_category_names(conn, categories: pd.DataFrame) -> int:
    """Danh mục không có updated_at: nếu đổi tên thì đồng bộ lại cho dim_product (ít dòng, rẻ)."""
    changed = 0
    for cid, name in zip(categories["category_id"], categories["category_name"]):
        res = conn.execute(
            sa.update(S.dim_product)
            .where(S.dim_product.c.category_id == int(cid), S.dim_product.c.category_name != name)
            .values(category_name=name))
        changed += res.rowcount or 0
    return changed


def ensure_dim_date(conn, start: date = date(2020, 1, 1), end: date = date(2030, 12, 31)) -> int:
    existing = {r[0] for r in conn.execute(sa.select(S.dim_date.c.date_key))}
    df = build_dim_date(start, end)
    df = df[~df["date_key"].isin(existing)]
    for part in _chunks(to_records(df), 2000):
        conn.execute(sa.insert(S.dim_date), part)
    return len(df)


def load_facts(conn, fact_df: pd.DataFrame, now: datetime) -> tuple[int, int, pd.DataFrame]:
    """Gắn khoá thay thế rồi upsert fact. Trả về (thêm, cập_nhật, dòng_thiếu_dimension)."""
    if fact_df.empty:
        return 0, 0, pd.DataFrame(columns=["transaction_id", "reason"])
    products = key_map(conn, S.dim_product, "product_id", "product_key")
    users = key_map(conn, S.dim_user, "user_id", "user_key")
    f = fact_df.assign(
        product_key=fact_df["product_id"].map(products),
        buyer_user_key=fact_df["buyer_id"].map(users),
        seller_user_key=fact_df["seller_id"].map(users),
    )
    missing = f[["product_key", "buyer_user_key", "seller_user_key"]].isna().any(axis=1)
    orphans = f.loc[missing, ["transaction_id"]].assign(reason="Thiếu dòng dimension tương ứng (sản phẩm/người dùng)")
    cols = [c.name for c in S.fact_transactions.c if c.name != "etl_loaded_at"]
    good = f.loc[~missing, cols]
    for c in ("product_key", "buyer_user_key", "seller_user_key"):
        good[c] = good[c].astype("int64")
    added, updated = upsert(conn, S.fact_transactions, good, "transaction_id", now)
    return added, updated, orphans
