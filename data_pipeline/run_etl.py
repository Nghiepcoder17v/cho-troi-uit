"""Chạy ETL: OLTP (DATABASE_URL) -> Data Warehouse (DWH_DATABASE_URL).

    python data_pipeline/run_etl.py                    # lần đầu: nạp toàn bộ (initial); các lần sau: tăng dần
    python data_pipeline/run_etl.py --full-refresh     # nạp lại toàn bộ (vẫn là upsert, không xoá)
    python data_pipeline/run_etl.py --drop-dwh         # XOÁ toàn bộ bảng DWH rồi nạp lại từ đầu
Mã thoát: 0 = OK, 1 = có cảnh báo (từ chối dòng / lệch số dòng), 2 = cấu hình sai, 3 = lỗi.
"""
import argparse
import logging
import os
import sys

import sqlalchemy as sa
from dotenv import load_dotenv

from etl.pipeline import DEFAULT_OVERLAP_MINUTES, drop_dwh, run_etl


def make_engine(url: str) -> sa.Engine:
    return sa.create_engine(url, fast_executemany=True) if url.startswith("mssql") else sa.create_engine(url)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full-refresh", action="store_true", help="bỏ qua watermark, nạp lại tất cả")
    ap.add_argument("--drop-dwh", action="store_true", help="xoá mọi bảng DWH rồi nạp lại (huỷ lịch sử watermark/log)")
    ap.add_argument("--overlap-minutes", type=int, default=DEFAULT_OVERLAP_MINUTES,
                    help="lùi watermark chừng này phút để không sót dòng commit trễ")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()
    src_url, dwh_url = os.getenv("DATABASE_URL"), os.getenv("DWH_DATABASE_URL")
    if not src_url or not dwh_url:
        print("Thiếu DATABASE_URL hoặc DWH_DATABASE_URL trong .env (xem .env.example).")
        return 2
    source, dwh = make_engine(src_url), make_engine(dwh_url)
    try:
        if args.drop_dwh:
            drop_dwh(dwh)
        r = run_etl(source, dwh, full_refresh=args.full_refresh or args.drop_dwh, overlap_minutes=args.overlap_minutes)
    except ValueError as exc:
        print(exc)
        return 2
    except Exception as exc:  # noqa: BLE001 - chi tiết đã nằm trong etl_run_log
        print(f"ETL thất bại: {type(exc).__name__}: {exc}")
        return 3

    print(f"\nRun #{r.run_id} [{r.mode}] -> {r.status}")
    print(f"  Trích xuất : {r.extracted}")
    for table, (added, updated) in r.loaded.items():
        print(f"  {table:<18}: +{added} mới, ~{updated} cập nhật")
    print(f"  Từ chối    : {r.rejected}")
    print(f"  Đối chiếu  : nguồn {r.reconciliation['source']}  |  kho {r.reconciliation['dwh']}")
    for w in r.warnings:
        print(f"  ⚠ {w}")
    return 1 if r.status == "WARNING" else 0


if __name__ == "__main__":
    sys.exit(main())
