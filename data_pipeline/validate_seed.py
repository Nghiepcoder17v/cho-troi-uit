"""Kiểm tra tính nhất quán của dữ liệu trong OLTP database. Thoát mã 1 nếu có vi phạm.

    python data_pipeline/validate_seed.py
Dùng được cho cả dữ liệu giả lẫn dữ liệu thật (vd: chạy trước mỗi lần ETL).
"""
import os
import sys

import sqlalchemy as sa
from dotenv import load_dotenv

CHECKS = {
    "Sản phẩm đăng TRƯỚC khi người bán đăng ký":
        "SELECT COUNT(*) FROM products p JOIN users u ON u.user_id = p.seller_id WHERE p.created_at < u.created_at",
    "Giao dịch xảy ra TRƯỚC khi sản phẩm được đăng":
        "SELECT COUNT(*) FROM transactions t JOIN products p ON p.product_id = t.product_id WHERE t.transaction_date < p.created_at",
    "Giao dịch xảy ra TRƯỚC khi người mua đăng ký":
        "SELECT COUNT(*) FROM transactions t JOIN users u ON u.user_id = t.buyer_id WHERE t.transaction_date < u.created_at",
    "Người mua trùng người bán":
        "SELECT COUNT(*) FROM transactions t JOIN products p ON p.product_id = t.product_id WHERE t.buyer_id = p.seller_id",
    "Giao dịch Completed nhưng sản phẩm không phải Sold":
        "SELECT COUNT(*) FROM transactions t JOIN products p ON p.product_id = t.product_id WHERE t.status = 'Completed' AND p.status <> 'Sold'",
    "Sản phẩm Sold không có đúng 1 giao dịch Completed":
        "SELECT COUNT(*) FROM products p WHERE p.status = 'Sold' AND (SELECT COUNT(*) FROM transactions t WHERE t.product_id = p.product_id AND t.status = 'Completed') <> 1",
    "Sản phẩm có nhiều hơn 1 giao dịch đang sống (không Cancelled)":
        "SELECT COUNT(*) FROM (SELECT product_id FROM transactions WHERE status <> 'Cancelled' GROUP BY product_id HAVING COUNT(*) > 1) x",
    "Giá chốt cao hơn giá niêm yết":
        "SELECT COUNT(*) FROM transactions t JOIN products p ON p.product_id = t.product_id WHERE t.amount > p.price",
    "updated_at nhỏ hơn created_at (sản phẩm)":
        "SELECT COUNT(*) FROM products WHERE updated_at < created_at",
    "Sản phẩm Sold có updated_at khác ngày giao dịch":
        "SELECT COUNT(*) FROM products p JOIN transactions t ON t.product_id = p.product_id AND t.status = 'Completed' WHERE p.status = 'Sold' AND p.updated_at <> t.transaction_date",
}


def main() -> int:
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        print("Thiếu DATABASE_URL")
        return 2
    engine = sa.create_engine(url)
    bad = 0
    with engine.connect() as conn:
        counts = {t: conn.scalar(sa.text(f"SELECT COUNT(*) FROM {t}")) for t in ("users", "products", "transactions")}
        for t, n in counts.items():
            print(f"{t:<13}: {n:>7} dòng")
        print()
        if not all(counts.values()):  # bảng rỗng thì mọi phép kiểm tra đều "đạt" một cách vô nghĩa
            print("Có bảng rỗng -> chưa có gì để kiểm tra. Hãy chạy generate_seed.py trước.")
            return 2
        for name, sql in CHECKS.items():
            n = conn.scalar(sa.text(sql))
            print(f"[{'OK ' if n == 0 else 'LỖI'}] {name}: {n}")
            bad += n != 0
    print("\nDữ liệu NHẤT QUÁN." if not bad else f"\nCó {bad} nhóm vi phạm.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
