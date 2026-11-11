"""Schema của Data Warehouse (Star Schema) - nguồn sự thật duy nhất, tạo bằng metadata.create_all().

        dim_date ──┐                 ┌── dim_user  (người mua)
                   ├── fact_transactions ──┤
        dim_product┘                 └── dim_user  (người bán)   <- cùng một dimension, hai vai trò

Quy ước: dimension có khoá thay thế (surrogate key, IDENTITY); dim_user và dim_date là SCD loại 1,
dim_product là SCD loại 2; fact dùng transaction_id làm "degenerate dimension".
"""
import sqlalchemy as sa

metadata = sa.MetaData()

dim_date = sa.Table(
    "dim_date", metadata,
    sa.Column("date_key", sa.Integer, primary_key=True, autoincrement=False),  # YYYYMMDD
    sa.Column("full_date", sa.Date, nullable=False, unique=True),
    sa.Column("calendar_year", sa.SmallInteger, nullable=False),
    sa.Column("calendar_quarter", sa.SmallInteger, nullable=False),
    sa.Column("calendar_month", sa.SmallInteger, nullable=False),
    sa.Column("year_month", sa.String(7), nullable=False),            # 'YYYY-MM'
    sa.Column("month_name", sa.Unicode(20), nullable=False),
    sa.Column("day_of_month", sa.SmallInteger, nullable=False),
    sa.Column("day_of_week", sa.SmallInteger, nullable=False),        # 1 = Thứ Hai ... 7 = Chủ Nhật
    sa.Column("day_name", sa.Unicode(20), nullable=False),
    sa.Column("week_of_year", sa.SmallInteger, nullable=False),       # tuần ISO
    sa.Column("is_weekend", sa.SmallInteger, nullable=False),
    sa.Column("academic_term", sa.Unicode(10), nullable=False),       # HK1 / HK2 / Hè (giả định, xem transform.py)
)

dim_user = sa.Table(
    "dim_user", metadata,
    sa.Column("user_key", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, nullable=False, unique=True),    # khoá tự nhiên (OLTP)
    sa.Column("cohort_year", sa.SmallInteger),                        # khoá sinh viên, suy ra từ MSSV
    sa.Column("full_name", sa.Unicode(100), nullable=False),
    sa.Column("major", sa.Unicode(50), nullable=False),               # đã chuẩn hoá
    sa.Column("user_created_at", sa.DateTime, nullable=False),
    sa.Column("etl_loaded_at", sa.DateTime, nullable=False),
    # Cố ý KHÔNG đưa email / MSSV / password_hash vào kho phân tích (tối thiểu hoá dữ liệu cá nhân).
)

dim_product = sa.Table(
    "dim_product", metadata,
    sa.Column("product_key", sa.Integer, primary_key=True),
    sa.Column("product_id", sa.Integer, nullable=False),
    sa.Column("category_id", sa.Integer, nullable=False),
    sa.Column("category_name", sa.Unicode(50), nullable=False),       # gộp danh mục vào đây (star, không snowflake)
    sa.Column("title", sa.Unicode(200), nullable=False),
    sa.Column("condition", sa.String(20), nullable=False),
    sa.Column("list_price", sa.Numeric(10, 2), nullable=False),
    sa.Column("current_status", sa.String(20), nullable=False),       # trạng thái tại phiên bản này (SCD2)
    sa.Column("listed_at", sa.DateTime, nullable=False),
    sa.Column("source_updated_at", sa.DateTime, nullable=False),
    sa.Column("effective_from", sa.DateTime, nullable=False),
    sa.Column("effective_to", sa.DateTime),
    sa.Column("is_current", sa.Boolean, nullable=False),
    sa.Column("etl_loaded_at", sa.DateTime, nullable=False),
    sa.CheckConstraint(
        "effective_to IS NULL OR effective_to > effective_from",
        name="CHK_dim_product_effective_window",
    ),
    sa.CheckConstraint(
        "(is_current = 1 AND effective_to IS NULL) OR "
        "(is_current = 0 AND effective_to IS NOT NULL)",
        name="CHK_dim_product_current_window",
    ),
    sa.Index(
        "UX_dim_product_current",
        "product_id",
        unique=True,
        mssql_where=sa.text("is_current = 1"),
        sqlite_where=sa.text("is_current = 1"),
    ),
    sa.Index("IX_dim_product_natural_effective", "product_id", "effective_from"),
)

fact_transactions = sa.Table(
    "fact_transactions", metadata,
    sa.Column("transaction_id", sa.Integer, primary_key=True, autoincrement=False),   # degenerate dimension
    sa.Column("product_key", sa.Integer, sa.ForeignKey("dim_product.product_key"), nullable=False),
    sa.Column("buyer_user_key", sa.Integer, sa.ForeignKey("dim_user.user_key"), nullable=False),
    sa.Column("seller_user_key", sa.Integer, sa.ForeignKey("dim_user.user_key"), nullable=False),
    sa.Column("transaction_date_key", sa.Integer, sa.ForeignKey("dim_date.date_key"), nullable=False),
    sa.Column("listed_date_key", sa.Integer, sa.ForeignKey("dim_date.date_key"), nullable=False),
    sa.Column("transaction_status", sa.String(20), nullable=False),
    sa.Column("is_completed", sa.SmallInteger, nullable=False),       # 1/0 để SUM() trực tiếp
    sa.Column("list_price", sa.Numeric(10, 2), nullable=False),
    sa.Column("amount", sa.Numeric(10, 2), nullable=False),           # giá chốt
    sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False),  # list_price - amount
    sa.Column("discount_pct", sa.Numeric(5, 2)),                      # NULL nếu list_price = 0
    sa.Column("days_to_sell", sa.Numeric(10, 2)),                     # chỉ có với giao dịch Completed
    sa.Column("transaction_at", sa.DateTime, nullable=False),
    sa.Column("source_updated_at", sa.DateTime, nullable=False),
    sa.Column("etl_loaded_at", sa.DateTime, nullable=False),
    sa.Index("IX_fact_tx_date", "transaction_date_key"),
    sa.Index("IX_fact_tx_buyer", "buyer_user_key"),
    sa.Index("IX_fact_tx_seller", "seller_user_key"),
    sa.Index("IX_fact_tx_product", "product_key"),
)

# ---- Bảng điều khiển của pipeline --------------------------------------------------
etl_watermark = sa.Table(
    "etl_watermark", metadata,
    sa.Column("source_table", sa.String(50), primary_key=True),
    sa.Column("last_updated_at", sa.DateTime, nullable=False),        # max(updated_at) đã nạp
    sa.Column("last_run_id", sa.Integer),
)

etl_run_log = sa.Table(
    "etl_run_log", metadata,
    sa.Column("run_id", sa.Integer, primary_key=True),
    sa.Column("mode", sa.String(20), nullable=False),                 # initial | incremental | full
    sa.Column("status", sa.String(30), nullable=False),               # RUNNING | SUCCESS | WARNING | FAILED
    sa.Column("started_at", sa.DateTime, nullable=False),
    sa.Column("finished_at", sa.DateTime),
    sa.Column("users_extracted", sa.Integer),
    sa.Column("products_extracted", sa.Integer),
    sa.Column("transactions_extracted", sa.Integer),
    sa.Column("rows_rejected", sa.Integer),
    sa.Column("message", sa.UnicodeText),
)

etl_rejected_rows = sa.Table(
    "etl_rejected_rows", metadata,
    sa.Column("rejected_id", sa.Integer, primary_key=True),
    sa.Column("run_id", sa.Integer, nullable=False),
    sa.Column("source_table", sa.String(50), nullable=False),
    sa.Column("source_id", sa.Integer, nullable=False),
    sa.Column("reason", sa.Unicode(200), nullable=False),
    sa.Column("rejected_at", sa.DateTime, nullable=False),
)
