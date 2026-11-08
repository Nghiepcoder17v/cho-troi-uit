import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

import generate_seed as gs
from validate_seed import CHECKS

END = datetime(2026, 11, 8, 23, 59)
CAT_IDS = {n: i for i, n in enumerate(gs.CATEGORY_NAMES, 1)}


def build(seed=1, users=300, products=1500, tx=600):
    return gs.build_dataset(users, products, tx, END, seed, "hash", CAT_IDS)


@pytest.fixture()
def engine():
    e = sa.create_engine("sqlite://")
    gs.md.create_all(e)
    with e.begin() as c:
        for name, cid in CAT_IDS.items():
            c.execute(sa.insert(gs.categories_t).values(category_id=cid, category_name=name))
    return e


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_generated_data_passes_every_consistency_check(engine, seed):
    users, products, txs = build(seed=seed)
    gs.load(engine, users, products, txs, reset=False)
    with engine.connect() as conn:
        for name, sql in CHECKS.items():
            assert conn.scalar(sa.text(sql)) == 0, name


def test_counts_and_ratios():
    users, products, txs = build()
    assert (len(users), len(products), len(txs)) == (300, 1500, 600)
    assert sum(t["status"] == "Completed" for t in txs) == 420
    assert sum(p["status"] == "Sold" for p in products) == 420


def test_ids_follow_time_order():
    users, products, txs = build()
    for rows, key in ((users, "created_at"), (products, "created_at"), (txs, "transaction_date")):
        times = [r[key] for r in rows]
        assert times == sorted(times)


def test_nothing_in_the_future():
    users, products, txs = build()
    assert max(u["created_at"] for u in users) <= END
    assert max(p["updated_at"] for p in products) <= END
    assert max(t["transaction_date"] for t in txs) <= END


def test_student_ids_and_emails_unique_and_consistent():
    users, _, _ = build()
    assert len({u["student_id"] for u in users}) == len(users)
    assert all(u["email"] == f"{u['student_id']}@gm.uit.edu.vn" and len(u["student_id"]) == 8 for u in users)


def test_amount_never_exceeds_price():
    _, products, txs = build()
    price = {p["product_id"]: p["price"] for p in products}
    assert all(t["amount"] <= price[t["product_id"]] for t in txs)


def test_refuses_to_overwrite_without_reset(engine):
    users, products, txs = build(users=50, products=200, tx=50)
    gs.load(engine, users, products, txs, reset=False)
    with pytest.raises(SystemExit):
        gs.load(engine, users, products, txs, reset=False)
    gs.load(engine, users, products, txs, reset=True)  # có --reset thì được


def test_too_many_completed_transactions_is_rejected():
    with pytest.raises(SystemExit):
        gs.build_dataset(50, 100, 500, END, 1, "hash", CAT_IDS)


def test_same_seed_gives_same_data_across_processes():
    """Bắt lỗi phụ thuộc thứ tự set/dict: chạy 2 tiến trình với PYTHONHASHSEED khác nhau."""
    code = (
        "import hashlib, generate_seed as gs; from datetime import datetime;"
        "u,p,t = gs.build_dataset(200,800,300,datetime(2026,11,8,23,59),5,'h',{n:i for i,n in enumerate(gs.CATEGORY_NAMES,1)});"
        "print(hashlib.md5(repr((u,p,t)).encode()).hexdigest())"
    )
    outs = set()
    for hash_seed in ("1", "99"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        r = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parent.parent, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        outs.add(r.stdout.strip())
    assert len(outs) == 1
