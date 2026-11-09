from datetime import datetime

import pandas as pd
import pytest
import sqlalchemy as sa

import generate_seed as gs
from etl.extract import query_df

END = datetime(2026, 11, 8, 23, 59)


@pytest.fixture()
def oltp(tmp_path):
    """OLTP SQLite nhỏ (300 user / 1200 sản phẩm / 500 giao dịch) sinh bởi chính generate_seed."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'oltp.db'}")
    gs.md.create_all(engine)
    cat_ids = gs.ensure_categories(engine)
    users, products, txs = gs.build_dataset(300, 1200, 500, END, 3, "hash", cat_ids)
    gs.load(engine, users, products, txs, reset=False)
    yield engine
    engine.dispose()


@pytest.fixture()
def dwh(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'dwh.db'}")
    yield engine
    engine.dispose()


def make_dwh(tmp_path, name: str) -> sa.Engine:
    return sa.create_engine(f"sqlite:///{tmp_path / name}")


def snapshot(dwh: sa.Engine) -> dict[str, pd.DataFrame]:
    """Nội dung kho theo KHOÁ TỰ NHIÊN (bỏ surrogate key và etl_loaded_at) để so sánh hai kho với nhau."""
    with dwh.connect() as c:
        return {
            "users": query_df(c, "SELECT user_id, cohort_year, full_name, major, user_created_at FROM dim_user ORDER BY user_id"),
            "products": query_df(c, "SELECT product_id, category_id, category_name, title, condition, list_price, "
                                    "current_status, listed_at FROM dim_product ORDER BY product_id"),
            "facts": query_df(c, """
                SELECT f.transaction_id, p.product_id, b.user_id AS buyer_id, s.user_id AS seller_id,
                       f.transaction_date_key, f.listed_date_key, f.transaction_status, f.is_completed,
                       f.list_price, f.amount, f.discount_amount, f.discount_pct, f.days_to_sell,
                       f.transaction_at, f.source_updated_at
                FROM fact_transactions f
                JOIN dim_product p ON p.product_key = f.product_key
                JOIN dim_user b ON b.user_key = f.buyer_user_key
                JOIN dim_user s ON s.user_key = f.seller_user_key
                ORDER BY f.transaction_id"""),
        }


def assert_same_snapshot(a: dict, b: dict) -> None:
    for name in a:
        pd.testing.assert_frame_equal(a[name], b[name], check_dtype=False, obj=name)


def scalar(engine: sa.Engine, sql: str):
    with engine.connect() as c:
        return c.scalar(sa.text(sql))
