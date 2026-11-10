"""Tầng Transform: hàm THUẦN (DataFrame vào -> DataFrame ra), không đụng database nên dễ test."""
from __future__ import annotations

import re
import unicodedata
from datetime import date

import numpy as np
import pandas as pd

UNKNOWN_MAJOR = "Chưa xác định"
VALID_TX_STATUS = {"Pending", "Accepted", "Completed", "Cancelled"}

# Danh sách ngành chuẩn + các cách viết tắt / sai khác thường gặp (so khớp không phân biệt hoa thường, dấu, khoảng trắng)
CANONICAL_MAJORS = {
    "Khoa học máy tính": ["khmt", "cs", "computer science"],
    "Kỹ thuật phần mềm": ["ktpm", "se", "software engineering"],
    "Hệ thống thông tin": ["httt", "is", "information systems"],
    "An toàn thông tin": ["attt", "infosec", "cyber security", "cybersecurity"],
    "Mạng máy tính": ["mmt", "mmt&tt", "mang may tinh va truyen thong du lieu"],
    "Khoa học dữ liệu": ["khdl", "ds", "data science"],
    "Trí tuệ nhân tạo": ["ai", "tttt", "artificial intelligence"],
    "Kỹ thuật máy tính": ["ktmt", "ce", "computer engineering"],
    "Thương mại điện tử": ["tmdt", "ecommerce", "e-commerce"],
    "Công nghệ thông tin": ["cntt", "it"],
}

# Lịch học GIẢ ĐỊNH (chỉnh ở đây nếu khác thực tế): HK1 = T9-T1, HK2 = T2-T6, Hè = T7-T8
TERM_BY_MONTH = {9: "HK1", 10: "HK1", 11: "HK1", 12: "HK1", 1: "HK1",
                 2: "HK2", 3: "HK2", 4: "HK2", 5: "HK2", 6: "HK2", 7: "Hè", 8: "Hè"}
DAY_NAMES = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


# ------------------------------------------------------------------ chuẩn hoá chuỗi
def clean_text(value) -> str | None:
    """NFC + bỏ khoảng trắng thừa. Rỗng/NULL -> None."""
    if value is None or (isinstance(value, float) and np.isnan(value)) or value is pd.NA:
        return None
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value))).strip()
    return text or None


def _fold(text: str) -> str:
    """Khoá so khớp: bỏ dấu, hạ chữ thường, bỏ khoảng trắng."""
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", "", text).casefold()


_MAJOR_LOOKUP = {_fold(name): name for name in CANONICAL_MAJORS}
_MAJOR_LOOKUP.update({_fold(alias): name for name, aliases in CANONICAL_MAJORS.items() for alias in aliases})


def canonical_major(raw) -> str:
    text = clean_text(raw)
    if text is None:
        return UNKNOWN_MAJOR
    # Không nằm trong danh sách -> giữ nguyên (đã làm sạch) để KHÔNG làm mất thông tin.
    return _MAJOR_LOOKUP.get(_fold(text), text)


def to_dt(series: pd.Series) -> pd.Series:
    """Chuỗi ISO-8601 (có/không phần giây lẻ) hoặc datetime -> datetime64. Không suy luận định dạng từ phần tử đầu."""
    return pd.to_datetime(series, format="ISO8601")


def date_key(ts: pd.Series) -> pd.Series:
    return (ts.dt.year * 10000 + ts.dt.month * 100 + ts.dt.day).astype("int64")


# ------------------------------------------------------------------ dimensions
def transform_users(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({"user_id": df["user_id"].astype("int64")})
    sid = df["student_id"].astype("string")
    # MSSV dạng YYxxxxxx: 2 chữ số đầu = năm nhập học (vd 25 -> 2025)
    yy = pd.to_numeric(sid.str[:2], errors="coerce")
    out["cohort_year"] = (2000 + yy).astype("Int64")
    out["full_name"] = df["full_name"].map(clean_text).fillna("Không rõ")
    out["major"] = df["major"].map(canonical_major)
    out["user_created_at"] = to_dt(df["created_at"])
    return out


def transform_products(df: pd.DataFrame, categories: pd.DataFrame) -> pd.DataFrame:
    cats = categories.assign(category_name=categories["category_name"].map(clean_text))
    merged = df.merge(cats, on="category_id", how="left")
    out = pd.DataFrame({
        "product_id": merged["product_id"].astype("int64"),
        "category_id": merged["category_id"].astype("int64"),
        "category_name": merged["category_name"].fillna("Không rõ"),
        "title": merged["title"].map(clean_text).fillna("Không rõ"),
        "condition": merged["condition"],
        "list_price": merged["price"].astype("float64").round(2),
        "current_status": merged["status"],
        "listed_at": to_dt(merged["created_at"]),
    })
    return out


# ------------------------------------------------------------------ fact
def transform_transactions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trả về (fact_hợp_lệ, dòng_bị_từ_chối). Dòng bị từ chối có cột `reason`.

    `df` cần: transaction_id, product_id, buyer_id, seller_id, amount, status, transaction_date,
              tx_updated_at, list_price, listed_at   (seller_id/list_price/listed_at là NULL nếu sản phẩm không tồn tại).
    Với `Completed`, `tx_updated_at` là thời điểm xác nhận cuối (thời điểm hoàn tất);
    giao dịch cũ giữ nguyên vì updated_at và transaction_date ban đầu trùng nhau.
    """
    requested_at = to_dt(df["transaction_date"])
    source_updated_at = to_dt(df["tx_updated_at"])
    transaction_status = df["status"]
    # Trong luồng mới, updated_at chính là lúc xác nhận thứ hai làm giao dịch Completed.
    # Giao dịch cũ vẫn có updated_at bằng transaction_date, nên tương thích ngược.
    # Với trạng thái chưa hoàn tất, giữ ngày gửi yêu cầu làm ngày sự kiện.
    transaction_at = source_updated_at.where(transaction_status == "Completed", requested_at)

    d = pd.DataFrame({
        "transaction_id": df["transaction_id"].astype("int64"),
        "product_id": df["product_id"].astype("int64"),
        "buyer_id": df["buyer_id"].astype("int64"),
        "seller_id": pd.to_numeric(df["seller_id"], errors="coerce"),
        "transaction_status": transaction_status,
        "amount": pd.to_numeric(df["amount"], errors="coerce").astype("float64").round(2),
        "list_price": pd.to_numeric(df["list_price"], errors="coerce").astype("float64").round(2),
        "transaction_at": transaction_at,
        "listed_at": to_dt(df["listed_at"]),
        "source_updated_at": source_updated_at,
    })

    # ---- kiểm tra chất lượng: lý do đầu tiên khớp sẽ được ghi nhận
    rules = [
        ("Sản phẩm không tồn tại trong nguồn", d["seller_id"].isna()),
        ("Trạng thái giao dịch không hợp lệ", ~d["transaction_status"].isin(VALID_TX_STATUS)),
        ("Giá chốt thiếu hoặc âm", d["amount"].isna() | (d["amount"] < 0)),
        ("Người mua trùng người bán", d["buyer_id"] == d["seller_id"]),
        ("Giá chốt cao hơn giá niêm yết", d["amount"] > d["list_price"]),
        ("Giao dịch xảy ra trước khi sản phẩm được đăng", requested_at < d["listed_at"]),
    ]
    reason = pd.Series(pd.NA, index=d.index, dtype="object")
    for text, bad in rules:
        reason = reason.mask(reason.isna() & bad.fillna(False), text)
    rejected = d.loc[reason.notna(), ["transaction_id"]].assign(reason=reason[reason.notna()])
    ok = d.loc[reason.isna()].copy()

    # ---- cột phái sinh
    ok["seller_id"] = ok["seller_id"].astype("int64")
    ok["is_completed"] = (ok["transaction_status"] == "Completed").astype("int64")
    ok["discount_amount"] = (ok["list_price"] - ok["amount"]).round(2)
    ok["discount_pct"] = (ok["discount_amount"] / ok["list_price"].where(ok["list_price"] > 0) * 100).round(2)
    days = (ok["transaction_at"] - ok["listed_at"]).dt.total_seconds() / 86400
    ok["days_to_sell"] = days.where(ok["is_completed"] == 1).round(2)  # chỉ có nghĩa khi đã bán xong
    ok["transaction_date_key"] = date_key(ok["transaction_at"])
    ok["listed_date_key"] = date_key(ok["listed_at"])
    return ok.drop(columns=["listed_at"]), rejected


# ------------------------------------------------------------------ dim_date
def build_dim_date(start: date, end: date) -> pd.DataFrame:
    days = pd.date_range(start, end, freq="D")
    s = pd.Series(days)
    return pd.DataFrame({
        "date_key": date_key(s),
        "full_date": s.dt.date,
        "calendar_year": s.dt.year.astype("int64"),
        "calendar_quarter": s.dt.quarter.astype("int64"),
        "calendar_month": s.dt.month.astype("int64"),
        "year_month": s.dt.strftime("%Y-%m"),
        "month_name": "Tháng " + s.dt.month.astype(str),
        "day_of_month": s.dt.day.astype("int64"),
        "day_of_week": (s.dt.day_of_week + 1).astype("int64"),
        "day_name": s.dt.day_of_week.map(lambda i: DAY_NAMES[i]),
        "week_of_year": s.dt.isocalendar().week.astype("int64"),
        "is_weekend": (s.dt.day_of_week >= 5).astype("int64"),
        "academic_term": s.dt.month.map(TERM_BY_MONTH),
    })
