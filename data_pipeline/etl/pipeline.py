"""Điều phối ETL: Extract (tăng dần theo watermark) -> Transform -> Load, trong MỘT transaction của DWH."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pandas as pd
import sqlalchemy as sa

from . import dwh_schema as S
from . import extract as E
from . import load as L
from . import transform as T

log = logging.getLogger("etl")
DEFAULT_OVERLAP_MINUTES = 5


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


@dataclass
class RunResult:
    run_id: int
    mode: str
    status: str = "SUCCESS"
    extracted: dict = field(default_factory=dict)
    loaded: dict = field(default_factory=dict)     # {"dim_user": (thêm, cập_nhật), ...}
    rejected: int = 0
    reconciliation: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def init_dwh(dwh: sa.Engine) -> int:
    """Tạo bảng DWH (nếu chưa có) và nạp dim_date. Idempotent."""
    S.metadata.create_all(dwh)
    product_columns = {column["name"] for column in sa.inspect(dwh).get_columns("dim_product")}
    required_columns = {"source_updated_at", "effective_from", "effective_to", "is_current"}
    if missing := required_columns - product_columns:
        raise RuntimeError(
            "DWH dim_product chưa có cột SCD Type 2 "
            f"{sorted(missing)}; hãy áp dụng database_scripts/migrations/20261111_dwh_product_scd2.sql."
        )
    with dwh.begin() as conn:
        return L.ensure_dim_date(conn)


def drop_dwh(dwh: sa.Engine) -> None:
    S.metadata.drop_all(dwh)


def _watermark(conn, table: str) -> datetime | None:
    return conn.scalar(sa.select(S.etl_watermark.c.last_updated_at).where(S.etl_watermark.c.source_table == table))


def _set_watermark(conn, table: str, value: datetime, run_id: int) -> None:
    exists = conn.scalar(sa.select(sa.func.count()).select_from(S.etl_watermark).where(S.etl_watermark.c.source_table == table))
    if exists:
        conn.execute(sa.update(S.etl_watermark).where(S.etl_watermark.c.source_table == table)
                     .values(last_updated_at=value, last_run_id=run_id))
    else:
        conn.execute(sa.insert(S.etl_watermark).values(source_table=table, last_updated_at=value, last_run_id=run_id))


def _since(wm: datetime | None, full: bool, overlap: timedelta) -> datetime | None:
    # Lùi lại `overlap` để không sót các dòng commit trễ / lệch đồng hồ. An toàn vì Load là upsert idempotent.
    return None if (full or wm is None) else wm - overlap


def run_etl(source: sa.Engine, dwh: sa.Engine, *, full_refresh: bool = False,
            overlap_minutes: int = DEFAULT_OVERLAP_MINUTES) -> RunResult:
    if source.url.render_as_string(hide_password=False) == dwh.url.render_as_string(hide_password=False):
        raise ValueError("DWH_DATABASE_URL trùng DATABASE_URL: sẽ ghi đè lên database giao dịch. Dừng lại.")
    init_dwh(dwh)
    with dwh.connect() as c:
        first_run = c.scalar(sa.select(sa.func.count()).select_from(S.etl_watermark)) == 0
    mode = "full" if full_refresh else ("initial" if first_run else "incremental")  # initial = lần đầu, chưa có watermark
    started = utcnow()
    with dwh.begin() as conn:  # log được commit riêng để vẫn còn khi lần chạy chính thất bại
        run_id = conn.execute(sa.insert(S.etl_run_log).values(mode=mode, status="RUNNING", started_at=started)).inserted_primary_key[0]
    result = RunResult(run_id=run_id, mode=mode)
    try:
        _run(source, dwh, result, full_refresh, timedelta(minutes=overlap_minutes))
    except Exception as exc:
        with dwh.begin() as conn:
            conn.execute(sa.update(S.etl_run_log).where(S.etl_run_log.c.run_id == run_id)
                         .values(status="FAILED", finished_at=utcnow(), message=f"{type(exc).__name__}: {exc}"[:4000]))
        log.error("ETL run %s FAILED: %s", run_id, exc)
        raise
    with dwh.begin() as conn:
        conn.execute(sa.update(S.etl_run_log).where(S.etl_run_log.c.run_id == run_id).values(
            status=result.status, finished_at=utcnow(),
            users_extracted=result.extracted["users"], products_extracted=result.extracted["products"],
            transactions_extracted=result.extracted["transactions"], rows_rejected=result.rejected,
            message="; ".join(result.warnings) or None))
    return result


def _run(source, dwh, result: RunResult, full: bool, overlap: timedelta) -> None:
    now = utcnow()
    with dwh.connect() as c:
        since = {t: _since(_watermark(c, t), full, overlap) for t in ("users", "products", "transactions")}

    # ---------------- EXTRACT. THỨ TỰ QUAN TRỌNG: giao dịch TRƯỚC, rồi mới tới user/product.
    # Nhờ vậy mọi user/product mà giao dịch vừa lấy tham chiếu tới chắc chắn đã có mặt trong lần trích xuất sau
    # (nếu làm ngược lại, một sản phẩm đăng ngay giữa hai lần đọc sẽ khiến giao dịch của nó bị coi là mồ côi).
    with source.connect() as src:
        tx_raw = E.extract_transactions(src, since["transactions"])
        users_raw = E.extract_users(src, since["users"])
        products_raw = E.extract_products(src, since["products"])
        categories = E.extract_categories(src)
        src_counts = E.source_counts(src)
    result.extracted = {"users": len(users_raw), "products": len(products_raw), "transactions": len(tx_raw)}
    log.info("Extract: %s (mode=%s)", result.extracted, result.mode)

    # ---------------- TRANSFORM
    dim_users = T.transform_users(users_raw) if len(users_raw) else users_raw.iloc[0:0]
    dim_products = T.transform_products(products_raw, categories) if len(products_raw) else products_raw.iloc[0:0]
    if len(tx_raw):
        facts, rejected = T.transform_transactions(tx_raw)
    else:
        facts, rejected = tx_raw.iloc[0:0], pd.DataFrame(columns=["transaction_id", "reason"])

    # ---------------- LOAD (một transaction: hoặc nạp hết và tiến watermark, hoặc không gì cả)
    with dwh.begin() as conn:
        result.loaded["dim_user"] = L.upsert(conn, S.dim_user, dim_users, "user_id", now)
        added_versions, changed_versions = L.load_product_scd2(conn, dim_products, now)
        category_versions = L.version_category_names(
            conn,
            categories.assign(category_name=categories["category_name"].map(T.clean_text)),
            now,
        )
        result.loaded["dim_product"] = (added_versions, changed_versions + category_versions)
        added, updated, orphans = L.load_facts(conn, facts, now)
        result.loaded["fact_transactions"] = (added, updated)

        all_rejected = pd.concat([rejected, orphans], ignore_index=True)
        result.rejected = len(all_rejected)
        if result.rejected:
            conn.execute(sa.insert(S.etl_rejected_rows), [
                {"run_id": result.run_id, "source_table": "transactions", "source_id": int(r.transaction_id),
                 "reason": r.reason, "rejected_at": now} for r in all_rejected.itertuples()])
            result.warnings.append(f"{result.rejected} giao dịch bị từ chối (xem etl_rejected_rows)")

        for table, raw, col in (("users", users_raw, "updated_at"), ("products", products_raw, "updated_at"),
                                ("transactions", tx_raw, "tx_updated_at")):
            if len(raw):
                _set_watermark(conn, table, T.to_dt(raw[col]).max().to_pydatetime(), result.run_id)

    # ---------------- RECONCILE: đối chiếu số dòng nguồn <-> kho
    with dwh.connect() as c:
        dwh_counts = {"users": c.scalar(sa.select(sa.func.count()).select_from(S.dim_user)),
                      "products": c.scalar(sa.select(sa.func.count(sa.distinct(S.dim_product.c.product_id)))),
                      "transactions": c.scalar(sa.select(sa.func.count()).select_from(S.fact_transactions)),
                      "rejected": c.scalar(sa.select(sa.func.count(sa.distinct(S.etl_rejected_rows.c.source_id)))
                                           .where(S.etl_rejected_rows.c.source_table == "transactions"))}
    result.reconciliation = {"source": src_counts, "dwh": dwh_counts}
    for t in ("users", "products"):
        if src_counts[t] != dwh_counts[t]:
            result.warnings.append(f"Lệch số dòng {t}: nguồn {src_counts[t]} vs kho {dwh_counts[t]}")
    if src_counts["transactions"] != dwh_counts["transactions"] + dwh_counts["rejected"]:
        result.warnings.append(f"Lệch số dòng transactions: nguồn {src_counts['transactions']} vs "
                               f"kho {dwh_counts['transactions']} + từ chối {dwh_counts['rejected']}")
    if result.warnings:
        result.status = "WARNING"
