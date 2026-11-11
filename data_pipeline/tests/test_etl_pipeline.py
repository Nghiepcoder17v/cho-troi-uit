from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa

import generate_seed as gs
from etl import load as load_mod
from etl import pipeline
from etl.extract import query_df
from conftest import assert_same_snapshot, make_dwh, scalar, snapshot

LATER = datetime(2026, 11, 9, 10, 0, 0)  # sau mọi updated_at của dữ liệu seed


def add_activity(oltp, when=LATER):
    """1 user mới + 1 sản phẩm mới (đã bán) + giao dịch Completed; và ẩn 1 sản phẩm cũ."""
    with oltp.begin() as c:
        uid = c.scalar(sa.select(sa.func.max(gs.users_t.c.user_id))) + 1
        pid = c.scalar(sa.select(sa.func.max(gs.products_t.c.product_id))) + 1
        tid = c.scalar(sa.select(sa.func.max(gs.transactions_t.c.transaction_id))) + 1
        old = c.scalar(sa.select(gs.products_t.c.product_id).where(gs.products_t.c.status == "Available").limit(1))
        c.execute(sa.insert(gs.users_t).values(user_id=uid, student_id="25529999", email="25529999@gm.uit.edu.vn",
                  password_hash="h", full_name="  Trần   Văn  Mới ", major="khmt", created_at=when, updated_at=when))
        c.execute(sa.insert(gs.products_t).values(product_id=pid, seller_id=1, category_id=1, title="Sách mới đăng",
                  description=None, price=50000, condition="Good", status="Sold", created_at=when,
                  updated_at=when + timedelta(hours=3)))
        c.execute(sa.insert(gs.transactions_t).values(transaction_id=tid, product_id=pid, buyer_id=uid, amount=45000,
                  status="Completed", transaction_date=when + timedelta(hours=3), updated_at=when + timedelta(hours=3)))
        c.execute(sa.update(gs.products_t).where(gs.products_t.c.product_id == old)
                  .values(status="Hidden", updated_at=when + timedelta(hours=4)))
    return uid, pid, tid, old


# ---------------------------------------------------------------- nạp lần đầu
def test_initial_load_is_complete_and_consistent(oltp, dwh):
    r = pipeline.run_etl(oltp, dwh)
    assert r.status == "SUCCESS" and r.rejected == 0 and not r.warnings
    assert r.extracted == {"users": 300, "products": 1200, "transactions": 500}
    assert r.reconciliation["source"] == {"users": 300, "products": 1200, "transactions": 500}
    assert scalar(dwh, "SELECT COUNT(*) FROM dim_user") == 300
    assert scalar(dwh, "SELECT COUNT(*) FROM dim_product") == 1200
    assert scalar(dwh, "SELECT COUNT(*) FROM fact_transactions") == 500


def test_facts_reconcile_with_source_amounts(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    src = scalar(oltp, "SELECT SUM(amount) FROM transactions WHERE status = 'Completed'")
    assert scalar(dwh, "SELECT SUM(amount) FROM fact_transactions WHERE is_completed = 1") == src
    assert scalar(dwh, "SELECT COUNT(*) FROM fact_transactions WHERE is_completed = 1") == \
        scalar(oltp, "SELECT COUNT(*) FROM transactions WHERE status = 'Completed'")


def test_referential_integrity_and_date_coverage(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    for sql in [
        "SELECT COUNT(*) FROM fact_transactions f LEFT JOIN dim_product p ON p.product_key = f.product_key WHERE p.product_key IS NULL",
        "SELECT COUNT(*) FROM fact_transactions f LEFT JOIN dim_user u ON u.user_key = f.buyer_user_key WHERE u.user_key IS NULL",
        "SELECT COUNT(*) FROM fact_transactions f LEFT JOIN dim_user u ON u.user_key = f.seller_user_key WHERE u.user_key IS NULL",
        "SELECT COUNT(*) FROM fact_transactions f LEFT JOIN dim_date d ON d.date_key = f.transaction_date_key WHERE d.date_key IS NULL",
        "SELECT COUNT(*) FROM fact_transactions f LEFT JOIN dim_date d ON d.date_key = f.listed_date_key WHERE d.date_key IS NULL",
    ]:
        assert scalar(dwh, sql) == 0, sql


def test_days_to_sell_only_on_completed_and_never_negative(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    assert scalar(dwh, "SELECT COUNT(*) FROM fact_transactions WHERE is_completed = 0 AND days_to_sell IS NOT NULL") == 0
    assert scalar(dwh, "SELECT COUNT(*) FROM fact_transactions WHERE is_completed = 1 AND days_to_sell IS NULL") == 0
    assert scalar(dwh, "SELECT COUNT(*) FROM fact_transactions WHERE days_to_sell < 0") == 0


def test_dim_user_holds_no_personal_identifiers(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    cols = {c["name"] for c in sa.inspect(dwh).get_columns("dim_user")}
    assert not cols & {"email", "student_id", "password_hash"}


# ---------------------------------------------------------------- idempotent & incremental
def test_rerun_without_changes_does_not_change_the_warehouse(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    before = snapshot(dwh)
    r = pipeline.run_etl(oltp, dwh)
    assert r.status == "SUCCESS"
    assert r.extracted["transactions"] < 50 and r.loaded["fact_transactions"][0] == 0  # chỉ lấy lại phần chồng lấn, không thêm mới
    assert_same_snapshot(before, snapshot(dwh))


def test_incremental_picks_up_only_the_changes(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    uid, pid, tid, old = add_activity(oltp)
    r = pipeline.run_etl(oltp, dwh)
    assert r.extracted["users"] < 20 and r.extracted["products"] < 20 and r.extracted["transactions"] < 20  # KHÔNG nạp lại 1000+ dòng
    assert scalar(dwh, "SELECT COUNT(*) FROM dim_user") == 301
    assert scalar(dwh, "SELECT COUNT(*) FROM fact_transactions") == 501
    snap = snapshot(dwh)
    new_user = snap["users"].set_index("user_id").loc[uid]
    assert (new_user.full_name, new_user.major, new_user.cohort_year) == ("Trần Văn Mới", "Khoa học máy tính", 2025)  # đã chuẩn hoá
    assert snap["products"].set_index("product_id").loc[old, "current_status"] == "Hidden"   # phiên bản hiện tại được cập nhật
    new_fact = snap["facts"].set_index("transaction_id").loc[tid]
    assert (new_fact.discount_pct, new_fact.is_completed, new_fact.transaction_date_key) == (10.0, 1, 20261109)
    assert scalar(dwh, "SELECT last_updated_at FROM etl_watermark WHERE source_table = 'transactions'") >= str(LATER)[:10]


def test_incremental_result_equals_full_reload(oltp, dwh, tmp_path):
    """Nạp tăng dần và nạp lại nguồn cho cùng trạng thái hiện hành và các fact."""
    pipeline.run_etl(oltp, dwh)
    add_activity(oltp)
    pipeline.run_etl(oltp, dwh)
    fresh = make_dwh(tmp_path, "fresh.db")
    pipeline.run_etl(oltp, fresh)
    assert_same_snapshot(snapshot(dwh), snapshot(fresh))


def test_full_refresh_reextracts_everything_and_changes_nothing(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    before = snapshot(dwh)
    r = pipeline.run_etl(oltp, dwh, full_refresh=True)
    assert r.mode == "full" and r.extracted["transactions"] == 500
    assert_same_snapshot(before, snapshot(dwh))


def test_overlap_window_catches_late_committed_rows(oltp, dwh):
    """Một giao dịch commit trễ, có updated_at NHỎ HƠN watermark vài phút, vẫn phải được nạp."""
    pipeline.run_etl(oltp, dwh)
    wm = datetime.fromisoformat(scalar(dwh, "SELECT last_updated_at FROM etl_watermark WHERE source_table = 'transactions'"))
    with oltp.begin() as c:
        tid = c.scalar(sa.select(sa.func.max(gs.transactions_t.c.transaction_id))) + 1
        prod = c.execute(sa.select(gs.products_t.c.product_id, gs.products_t.c.seller_id, gs.products_t.c.created_at,
                                   gs.products_t.c.price).where(gs.products_t.c.status == "Available").limit(1)).one()
        buyer = 1 if prod.seller_id != 1 else 2
        late = wm - timedelta(minutes=2)
        c.execute(sa.insert(gs.transactions_t).values(transaction_id=tid, product_id=prod.product_id, buyer_id=buyer,
                  amount=prod.price, status="Cancelled", transaction_date=max(late, prod.created_at + timedelta(seconds=1)),
                  updated_at=late))
    assert pipeline.run_etl(oltp, dwh, overlap_minutes=0).loaded["fact_transactions"][0] == 0   # không chồng lấn -> SÓT
    assert pipeline.run_etl(oltp, dwh).loaded["fact_transactions"][0] == 1                       # mặc định 5 phút -> bắt được


def test_category_rename_creates_new_current_product_versions(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    with oltp.begin() as c:
        c.execute(sa.update(gs.categories_t).where(gs.categories_t.c.category_id == 1).values(category_name="Sách giáo trình"))
    pipeline.run_etl(oltp, dwh)
    assert scalar(
        dwh,
        "SELECT COUNT(*) FROM dim_product WHERE category_id = 1 AND is_current = 1 "
        "AND category_name <> 'Sách giáo trình'",
    ) == 0
    assert scalar(
        dwh,
        "SELECT COUNT(*) FROM dim_product WHERE category_id = 1 AND is_current = 0 "
        "AND category_name = 'Sách giáo trình'",
    ) == 0


def test_product_attribute_changes_create_versions_and_facts_use_event_time(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    with oltp.begin() as c:
        prior = c.execute(
            sa.select(gs.transactions_t.c.transaction_id, gs.transactions_t.c.product_id)
            .where(gs.transactions_t.c.transaction_date < LATER)
            .limit(1)
        ).one()
        product = c.execute(
            sa.select(gs.products_t.c.seller_id, gs.products_t.c.price)
            .where(gs.products_t.c.product_id == prior.product_id)
        ).one()
        buyer_id = 1 if product.seller_id != 1 else 2
        c.execute(
            sa.update(gs.products_t)
            .where(gs.products_t.c.product_id == prior.product_id)
            .values(title="Sản phẩm phiên bản mới", updated_at=LATER)
        )
        next_transaction_id = c.scalar(sa.select(sa.func.max(gs.transactions_t.c.transaction_id))) + 1
        c.execute(
            sa.insert(gs.transactions_t).values(
                transaction_id=next_transaction_id,
                product_id=prior.product_id,
                buyer_id=buyer_id,
                amount=product.price,
                status="Cancelled",
                transaction_date=LATER + timedelta(seconds=1),
                updated_at=LATER + timedelta(seconds=1),
            )
        )

    pipeline.run_etl(oltp, dwh)

    with dwh.connect() as c:
        versions = query_df(
            c,
            "SELECT product_key, title, effective_from, effective_to, is_current "
            "FROM dim_product WHERE product_id = :product_id ORDER BY effective_from",
            product_id=prior.product_id,
        )
    assert len(versions) == 2
    assert versions.iloc[0]["title"] != "Sản phẩm phiên bản mới"
    assert versions.iloc[0]["is_current"] in (0, False)
    assert versions.iloc[0]["effective_to"] == versions.iloc[1]["effective_from"]
    assert versions.iloc[1]["title"] == "Sản phẩm phiên bản mới"
    assert versions.iloc[1]["is_current"] in (1, True)

    with dwh.connect() as c:
        fact_keys = dict(
            c.execute(
                sa.text(
                    "SELECT transaction_id, product_key FROM fact_transactions "
                    "WHERE transaction_id IN (:old_id, :new_id)"
                ),
                {"old_id": prior.transaction_id, "new_id": next_transaction_id},
            ).all()
        )
    assert fact_keys[prior.transaction_id] == versions.iloc[0]["product_key"]
    assert fact_keys[next_transaction_id] == versions.iloc[1]["product_key"]


# ---------------------------------------------------------------- dữ liệu xấu & lỗi
def test_bad_rows_are_quarantined_not_loaded(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    with oltp.begin() as c:
        base = c.scalar(sa.select(sa.func.max(gs.transactions_t.c.transaction_id)))
        prod = c.execute(sa.select(gs.products_t.c.product_id, gs.products_t.c.seller_id, gs.products_t.c.created_at,
                                   gs.products_t.c.price).where(gs.products_t.c.status == "Available").limit(1)).one()
        buyer = 1 if prod.seller_id != 1 else 2
        when = LATER
        c.execute(sa.insert(gs.transactions_t).values(transaction_id=base + 1, product_id=999999, buyer_id=1, amount=100,
                  status="Completed", transaction_date=when, updated_at=when))                      # sản phẩm không tồn tại
        c.execute(sa.insert(gs.transactions_t).values(transaction_id=base + 2, product_id=prod.product_id, buyer_id=buyer,
                  amount=prod.price + 5000, status="Cancelled", transaction_date=when, updated_at=when))  # giá chốt > niêm yết
    r = pipeline.run_etl(oltp, dwh)
    assert r.status == "WARNING" and r.rejected == 2
    assert len(r.warnings) == 1                       # chỉ cảnh báo từ chối; đối chiếu số dòng vẫn khớp (nguồn = kho + từ chối)
    assert scalar(dwh, "SELECT COUNT(*) FROM fact_transactions") == 500
    reasons = {row[0] for row in dwh.connect().execute(sa.text("SELECT reason FROM etl_rejected_rows"))}
    assert reasons == {"Sản phẩm không tồn tại trong nguồn", "Giá chốt cao hơn giá niêm yết"}


def test_failure_leaves_no_partial_data_and_does_not_advance_watermark(oltp, dwh, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom giữa chừng")

    monkeypatch.setattr(load_mod, "load_facts", boom)   # dim đã nạp xong, rồi mới lỗi ở fact
    with pytest.raises(RuntimeError):
        pipeline.run_etl(oltp, dwh)
    assert scalar(dwh, "SELECT COUNT(*) FROM dim_user") == 0 and scalar(dwh, "SELECT COUNT(*) FROM dim_product") == 0
    assert scalar(dwh, "SELECT COUNT(*) FROM etl_watermark") == 0
    log = query_df(dwh.connect(), "SELECT status, message FROM etl_run_log").iloc[0]
    assert log.status == "FAILED" and "boom" in log.message

    monkeypatch.undo()                                  # chạy lại sau khi sửa lỗi -> nạp đủ
    assert pipeline.run_etl(oltp, dwh).status == "SUCCESS"
    assert scalar(dwh, "SELECT COUNT(*) FROM fact_transactions") == 500


def test_refuses_to_write_the_warehouse_into_the_source_database(oltp):
    with pytest.raises(ValueError, match="trùng"):
        pipeline.run_etl(oltp, oltp)
    assert "dim_user" not in sa.inspect(oltp).get_table_names()


def test_run_log_records_each_run(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    pipeline.run_etl(oltp, dwh)
    rows = query_df(dwh.connect(), "SELECT run_id, status, transactions_extracted FROM etl_run_log ORDER BY run_id")
    assert rows["status"].tolist() == ["SUCCESS", "SUCCESS"] and rows["transactions_extracted"].iloc[0] == 500


def test_run_mode_is_labelled_initial_then_incremental(oltp, dwh):
    assert pipeline.run_etl(oltp, dwh).mode == "initial"
    assert pipeline.run_etl(oltp, dwh).mode == "incremental"
    assert pipeline.run_etl(oltp, dwh, full_refresh=True).mode == "full"
