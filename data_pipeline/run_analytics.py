"""Chạy các truy vấn phân tích (analytics/*.sql) trên Data Warehouse.

    python data_pipeline/run_analytics.py            # chạy tất cả
    python data_pipeline/run_analytics.py top3_majors_it books_peak_month
    python data_pipeline/run_analytics.py --list
Truy vấn dùng tham số (:cat_...) thay vì viết thẳng tiếng Việt trong SQL, để SQL Server không làm hỏng dấu.
"""
import argparse
import os
import re
import sys
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
from dotenv import load_dotenv

QUERY_DIR = Path(__file__).parent / "analytics"
PARAMS = {  # định nghĩa nghiệp vụ, chỉnh tại đây
    "cat_it_1": "Linh kiện IT",
    "cat_it_2": "Bàn phím & Chuột",
    "cat_books": "Giáo trình",
}


def list_queries() -> list[str]:
    return sorted(p.stem for p in QUERY_DIR.glob("*.sql"))


def run_query(conn, name: str) -> pd.DataFrame:
    raw = (QUERY_DIR / f"{name}.sql").read_text(encoding="utf-8")
    # SQLAlchemy coi mọi ":tên" là tham số, kể cả trong chú thích -> bỏ các dòng chú thích trước khi chạy
    sql = "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("--"))
    used = set(re.findall(r"(?<!:):([A-Za-z_]\w*)", sql))
    result = conn.execute(sa.text(sql), {k: v for k, v in PARAMS.items() if k in used})
    return pd.DataFrame(result.fetchall(), columns=list(result.keys()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("queries", nargs="*", help="tên truy vấn (bỏ trống = chạy tất cả)")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        print("\n".join(list_queries()))
        return 0
    load_dotenv()
    url = os.getenv("DWH_DATABASE_URL")
    if not url:
        print("Thiếu DWH_DATABASE_URL trong .env")
        return 2
    names = args.queries or list_queries()
    unknown = [n for n in names if n not in list_queries()]
    if unknown:
        print(f"Không có truy vấn: {unknown}. Hiện có: {list_queries()}")
        return 2
    with sa.create_engine(url).connect() as conn:
        for name in names:
            print(f"\n=== {name} ===")
            print(run_query(conn, name).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
