from datetime import date

import numpy as np
import pandas as pd
import pytest

from etl import transform as T


# ---------------------------------------------------------------- chuẩn hoá ngành
@pytest.mark.parametrize("raw, expected", [
    ("KHMT", "Khoa học máy tính"),
    ("  khoa   học máy tính ", "Khoa học máy tính"),
    ("Khoa hoc may tinh", "Khoa học máy tính"),      # thiếu dấu
    ("ktpm", "Kỹ thuật phần mềm"),
    ("MMT&TT", "Mạng máy tính"),
    ("cntt", "Công nghệ thông tin"),
    (None, T.UNKNOWN_MAJOR),
    ("", T.UNKNOWN_MAJOR),
    ("   ", T.UNKNOWN_MAJOR),
    (float("nan"), T.UNKNOWN_MAJOR),
    ("Kinh tế", "Kinh tế"),                           # ngoài danh sách: giữ nguyên, không đoán mò
])
def test_canonical_major(raw, expected):
    assert T.canonical_major(raw) == expected


def test_clean_text_normalizes_unicode_forms():
    decomposed = "Nguye\u0302\u0303n"  # chữ "Nguyễn" dạng NFD
    assert T.clean_text(decomposed) == "Nguyễn"


def test_transform_users():
    raw = pd.DataFrame({
        "user_id": [1, 2], "student_id": ["25520001", "21520002"],
        "full_name": ["  Nguyễn   Văn A ", "Lê B"], "major": ["khmt", None],
        "created_at": ["2026-01-01 08:00:00", "2026-02-01 09:30:00.000000"],  # nhiều định dạng thời gian
    })
    out = T.transform_users(raw)
    assert out["cohort_year"].tolist() == [2025, 2021]
    assert out["full_name"].tolist() == ["Nguyễn Văn A", "Lê B"]
    assert out["major"].tolist() == ["Khoa học máy tính", T.UNKNOWN_MAJOR]
    assert out["user_created_at"].iloc[1] == pd.Timestamp("2026-02-01 09:30")
    assert "student_id" not in out.columns and "email" not in out.columns  # không đưa PII vào kho


def test_transform_products_joins_clean_category_and_handles_unknown():
    products = pd.DataFrame({"product_id": [1, 2], "category_id": [1, 99], "title": [" Sách  A ", "B"],
                             "condition": ["Good", "Fair"], "price": [50000, 20000], "status": ["Sold", "Available"],
                             "created_at": ["2026-01-01 00:00:00", "2026-01-02 00:00:00"],
                             "updated_at": ["2026-01-03 00:00:00", "2026-01-04 00:00:00"]})
    cats = pd.DataFrame({"category_id": [1], "category_name": [" Giáo   trình "]})
    out = T.transform_products(products, cats)
    assert out["category_name"].tolist() == ["Giáo trình", "Không rõ"]
    assert out["title"].tolist() == ["Sách A", "B"]
    assert out["source_updated_at"].tolist() == [pd.Timestamp("2026-01-03"), pd.Timestamp("2026-01-04")]


# ---------------------------------------------------------------- fact
def tx(**over):
    base = dict(transaction_id=1, product_id=10, buyer_id=2, seller_id=1, amount=90.0, status="Completed",
                transaction_date="2026-03-02 12:00:00", tx_updated_at="2026-03-02 12:00:00",
                list_price=100.0, listed_at="2026-03-01 00:00:00")
    base.update(over)
    return base


def run(*rows):
    return T.transform_transactions(pd.DataFrame(list(rows)))


def test_derived_columns_for_completed_sale():
    ok, rej = run(tx())
    assert rej.empty
    r = ok.iloc[0]
    assert (r.discount_amount, r.discount_pct, r.days_to_sell) == (10.0, 10.0, 1.5)
    assert (r.transaction_date_key, r.listed_date_key, r.is_completed) == (20260302, 20260301, 1)


def test_completed_sale_uses_final_update_time_not_request_time():
    ok, rejected = run(tx(
        transaction_date="2026-03-02 12:00:00",
        tx_updated_at="2026-03-03 09:00:00",
    ))
    assert rejected.empty
    row = ok.iloc[0]
    assert row.transaction_at == pd.Timestamp("2026-03-03 09:00:00")
    assert row.transaction_date_key == 20260303
    # The DWH column is decimal(10,2), so the transform stores two decimals.
    assert row.days_to_sell == 2.38


def test_days_to_sell_only_for_completed():
    ok, _ = run(
        tx(transaction_id=1),
        tx(transaction_id=2, status="Cancelled"),
        tx(transaction_id=3, status="Accepted"),
    )
    by_id = ok.set_index("transaction_id")
    assert by_id.loc[1, "days_to_sell"] == 1.5
    assert np.isnan(by_id.loc[2, "days_to_sell"]) and by_id.loc[2, "is_completed"] == 0
    assert np.isnan(by_id.loc[3, "days_to_sell"]) and by_id.loc[3, "is_completed"] == 0


def test_zero_list_price_gives_null_discount_pct_not_division_error():
    ok, rej = run(tx(list_price=0.0, amount=0.0))
    assert rej.empty and np.isnan(ok.iloc[0]["discount_pct"])


@pytest.mark.parametrize("over, reason", [
    (dict(seller_id=None, list_price=None, listed_at=None), "Sản phẩm không tồn tại trong nguồn"),
    (dict(status="Refunded"), "Trạng thái giao dịch không hợp lệ"),
    (dict(amount=-1.0), "Giá chốt thiếu hoặc âm"),
    (dict(amount=None), "Giá chốt thiếu hoặc âm"),
    (dict(buyer_id=1), "Người mua trùng người bán"),
    (dict(amount=150.0), "Giá chốt cao hơn giá niêm yết"),
    (dict(transaction_date="2026-02-28 00:00:00"), "Giao dịch xảy ra trước khi sản phẩm được đăng"),
])
def test_each_data_quality_rule_rejects_with_its_reason(over, reason):
    good = tx(transaction_id=1)
    bad = tx(transaction_id=2, **over)
    ok, rej = run(good, bad)
    assert ok["transaction_id"].tolist() == [1]            # dòng tốt vẫn đi tiếp
    assert rej["transaction_id"].tolist() == [2] and rej["reason"].tolist() == [reason]


# ---------------------------------------------------------------- dim_date
def test_dim_date_is_complete_and_correct():
    d = T.build_dim_date(date(2026, 1, 1), date(2026, 12, 31))
    assert len(d) == 365 and d["date_key"].is_unique
    assert (d["date_key"] == pd.to_datetime(d["full_date"]).dt.strftime("%Y%m%d").astype(int)).all()
    row = d[d["date_key"] == 20261108].iloc[0]          # Chủ Nhật
    assert (row.day_of_week, row.is_weekend, row.day_name, row.academic_term) == (7, 1, "Chủ Nhật", "HK1")
    assert d[d["date_key"] == 20260209].iloc[0].academic_term == "HK2"
    assert d[d["date_key"] == 20260715].iloc[0].academic_term == "Hè"
