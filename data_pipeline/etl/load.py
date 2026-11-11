"""Tầng Load: upsert vào Data Warehouse. Upsert viết bằng SQLAlchemy Core thuần (chạy được trên SQL Server và SQLite)."""
from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, timedelta
from decimal import Decimal

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


PRODUCT_ATTRIBUTES = (
    "category_id",
    "category_name",
    "title",
    "condition",
    "list_price",
    "current_status",
)


def _same_product_attribute(name: str, left, right) -> bool:
    if name == "list_price":
        return Decimal(str(left)).quantize(Decimal("0.01")) == Decimal(str(right)).quantize(
            Decimal("0.01")
        )
    return left == right


def load_product_scd2(
    conn, products: pd.DataFrame, now: datetime
) -> tuple[int, int]:
    """Thêm phiên bản sản phẩm khi thuộc tính phân tích thay đổi; giữ một phiên bản hiện hành."""
    if products.empty:
        return 0, 0

    ids = [int(value) for value in products["product_id"].unique()]
    current_rows = conn.execute(
        sa.select(S.dim_product).where(
            S.dim_product.c.is_current.is_(True), S.dim_product.c.product_id.in_(ids)
        )
    ).mappings()
    current_by_id = {int(row["product_id"]): dict(row) for row in current_rows}
    added = changed = 0

    for record in to_records(products):
        product_id = int(record["product_id"])
        current = current_by_id.get(product_id)
        values = {name: record[name] for name in PRODUCT_ATTRIBUTES}
        source_updated_at = record["source_updated_at"]
        if current is None:
            conn.execute(
                sa.insert(S.dim_product).values(
                    product_id=product_id,
                    **values,
                    listed_at=record["listed_at"],
                    source_updated_at=source_updated_at,
                    effective_from=record["listed_at"],
                    effective_to=None,
                    is_current=True,
                    etl_loaded_at=now,
                )
            )
            added += 1
            continue

        if any(
            not _same_product_attribute(name, current[name], values[name])
            for name in PRODUCT_ATTRIBUTES
        ):
            effective_from = source_updated_at
            if effective_from <= current["effective_from"]:
                effective_from = current["effective_from"] + timedelta(seconds=1)
            conn.execute(
                sa.update(S.dim_product)
                .where(S.dim_product.c.product_key == current["product_key"])
                .values(effective_to=effective_from, is_current=False)
            )
            conn.execute(
                sa.insert(S.dim_product).values(
                    product_id=product_id,
                    **values,
                    listed_at=record["listed_at"],
                    source_updated_at=source_updated_at,
                    effective_from=effective_from,
                    effective_to=None,
                    is_current=True,
                    etl_loaded_at=now,
                )
            )
            changed += 1

    return added, changed


def version_category_names(conn, categories: pd.DataFrame, now: datetime) -> int:
    """Category không có updated_at; ghi nhận thay đổi tên tại thời điểm ETL phát hiện."""
    changed = 0
    for cid, name in zip(categories["category_id"], categories["category_name"]):
        current_rows = conn.execute(
            sa.select(S.dim_product)
            .where(
                S.dim_product.c.category_id == int(cid),
                S.dim_product.c.is_current.is_(True),
                S.dim_product.c.category_name != name,
            )
        ).mappings().all()
        for current in current_rows:
            effective_from = max(now, current["effective_from"] + timedelta(seconds=1))
            conn.execute(
                sa.update(S.dim_product)
                .where(S.dim_product.c.product_key == current["product_key"])
                .values(effective_to=effective_from, is_current=False)
            )
            values = {
                column.name: current[column.name]
                for column in S.dim_product.c
                if column.name not in {
                    "product_key", "effective_from", "effective_to", "is_current", "etl_loaded_at"
                }
            }
            values.update(
                category_name=name,
                effective_from=effective_from,
                effective_to=None,
                is_current=True,
                etl_loaded_at=now,
            )
            conn.execute(sa.insert(S.dim_product).values(**values))
            changed += 1
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
    users = key_map(conn, S.dim_user, "user_id", "user_key")
    versions_by_product: dict[int, list[tuple[datetime, datetime | None, int]]] = {}
    for row in conn.execute(
        sa.select(
            S.dim_product.c.product_id,
            S.dim_product.c.product_key,
            S.dim_product.c.effective_from,
            S.dim_product.c.effective_to,
        ).order_by(S.dim_product.c.product_id, S.dim_product.c.effective_from)
    ):
        versions_by_product.setdefault(int(row.product_id), []).append(
            (row.effective_from, row.effective_to, int(row.product_key))
        )
    starts_by_product = {
        product_id: [version[0] for version in versions]
        for product_id, versions in versions_by_product.items()
    }

    product_keys: list[int | None] = []
    for product_id, transaction_at in fact_df[["product_id", "transaction_at"]].itertuples(
        index=False, name=None
    ):
        if isinstance(transaction_at, pd.Timestamp):
            transaction_at = transaction_at.to_pydatetime()
        versions = versions_by_product.get(int(product_id), [])
        index = bisect_right(starts_by_product.get(int(product_id), []), transaction_at) - 1
        if index >= 0 and (
            versions[index][1] is None or transaction_at < versions[index][1]
        ):
            product_keys.append(versions[index][2])
        else:
            product_keys.append(None)
    f = fact_df.assign(
        product_key=pd.Series(product_keys, index=fact_df.index, dtype="Int64"),
        buyer_user_key=fact_df["buyer_id"].map(users),
        seller_user_key=fact_df["seller_id"].map(users),
    )
    missing = f[["product_key", "buyer_user_key", "seller_user_key"]].isna().any(axis=1)
    orphan_rows = f.loc[missing, ["transaction_id", "product_key", "buyer_user_key", "seller_user_key"]].copy()
    orphan_rows["reason"] = "Thiếu dòng dimension người dùng tương ứng"
    orphan_rows.loc[orphan_rows["product_key"].isna(), "reason"] = (
        "Thiếu phiên bản dimension sản phẩm phù hợp với thời điểm giao dịch"
    )
    orphans = orphan_rows[["transaction_id", "reason"]]
    cols = [c.name for c in S.fact_transactions.c if c.name != "etl_loaded_at"]
    good = f.loc[~missing, cols]
    for c in ("product_key", "buyer_user_key", "seller_user_key"):
        good[c] = good[c].astype("int64")
    added, updated = upsert(conn, S.fact_transactions, good, "transaction_id", now)
    return added, updated, orphans
