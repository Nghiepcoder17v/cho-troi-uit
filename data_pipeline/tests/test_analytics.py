import pytest
import sqlalchemy as sa

import run_analytics as ra
from etl import pipeline
from etl.extract import query_df


@pytest.fixture()
def loaded(oltp, dwh):
    pipeline.run_etl(oltp, dwh)
    return oltp, dwh


@pytest.mark.parametrize("name", ra.list_queries())
def test_every_query_runs_and_returns_rows(loaded, name):
    _, dwh = loaded
    with dwh.connect() as c:
        assert not ra.run_query(c, name).empty


def test_top3_majors_matches_an_independent_calculation_from_oltp(loaded):
    oltp, dwh = loaded
    with oltp.connect() as c:
        ref = query_df(c, """
            SELECT u.major AS major, COUNT(*) AS purchases
            FROM transactions t JOIN products p ON p.product_id = t.product_id
                 JOIN categories c ON c.category_id = p.category_id JOIN users u ON u.user_id = t.buyer_id
            WHERE t.status = 'Completed' AND c.category_name IN ('Linh kiện IT', 'Bàn phím & Chuột')
            GROUP BY u.major""")
    ref["rnk"] = ref["purchases"].rank(method="min", ascending=False).astype(int)
    expected = dict(zip(ref[ref.rnk <= 3]["major"], ref[ref.rnk <= 3]["purchases"]))
    with dwh.connect() as c:
        got = ra.run_query(c, "top3_majors_it")
    assert dict(zip(got["major"], got["purchases"])) == expected
    assert got["rnk"].min() == 1 and got["rnk"].max() <= 3


def test_books_peak_month_matches_oltp_and_flags_the_peak(loaded):
    oltp, dwh = loaded
    with oltp.connect() as c:
        ref = query_df(c, """
            SELECT substr(t.transaction_date, 1, 7) AS ym, COUNT(*) AS n
            FROM transactions t JOIN products p ON p.product_id = t.product_id
                 JOIN categories c ON c.category_id = p.category_id
            WHERE t.status = 'Completed' AND c.category_name = 'Giáo trình' GROUP BY 1""")
    with dwh.connect() as c:
        got = ra.run_query(c, "books_peak_month")
    assert dict(zip(got["year_month"], got["completed_sales"])) == dict(zip(ref["ym"], ref["n"]))
    assert got.loc[got["peak_rank"] == 1, "year_month"].tolist() == [ref.loc[ref["n"].idxmax(), "ym"]]


def test_seller_pareto_is_cumulative_and_monotonic(loaded):
    _, dwh = loaded
    with dwh.connect() as c:
        got = ra.run_query(c, "seller_pareto")
    cum = got["cumulative_pct_of_revenue"].tolist()
    assert cum == sorted(cum) and 0 < cum[-1] <= 100
    assert got["revenue"].is_monotonic_decreasing


def test_comment_lines_cannot_break_parameter_binding(loaded, tmp_path, monkeypatch):
    _, dwh = loaded
    (tmp_path / "q.sql").write_text("-- ví dụ :cat_books trong chú thích\nSELECT 1 AS x;", encoding="utf-8")
    monkeypatch.setattr(ra, "QUERY_DIR", tmp_path)
    with dwh.connect() as c:
        assert ra.run_query(c, "q")["x"].tolist() == [1]
