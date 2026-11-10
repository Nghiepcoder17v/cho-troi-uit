"""Opt-in SQL Server integration tests for objects SQLite cannot emulate.

Safety guarantees:
- Tests are disabled unless RUN_SQLSERVER_INTEGRATION=1.
- The connection must target a database whose name ends in "_test".
- Every test uses one outer transaction and rolls back all DML before closing.
"""
from __future__ import annotations

import os
import re
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.sqlserver_integration


@pytest.fixture()
def sqlserver_connection():
    if os.getenv("RUN_SQLSERVER_INTEGRATION") != "1":
        pytest.skip("Set RUN_SQLSERVER_INTEGRATION=1 to enable SQL Server integration tests.")

    database_url = os.getenv("SQLSERVER_TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("RUN_SQLSERVER_INTEGRATION=1 but SQLSERVER_TEST_DATABASE_URL is missing.")

    database_name = make_url(database_url).database or ""
    if not database_name.casefold().endswith("_test"):
        pytest.fail(
            "Refusing to run SQL Server integration tests: database name must end in "
            "'_test' (for example ChoTroUIT_Step7_Test)."
        )

    engine = sa.create_engine(database_url, pool_pre_ping=True)
    connection = None
    transaction = None
    try:
        connection = engine.connect()
        transaction = connection.begin()
        yield connection
    finally:
        if transaction is not None and transaction.is_active:
            transaction.rollback()
        if connection is not None:
            connection.close()
        engine.dispose()


def _insert_user(connection: sa.Connection) -> int:
    suffix = uuid.uuid4().hex[:7].upper()
    student_id = f"T{suffix}"
    return connection.execute(
        sa.text(
            """
            INSERT INTO dbo.USERS
                (student_id, email, password_hash, full_name, major)
            OUTPUT INSERTED.user_id
            VALUES
                (:student_id, :email, :password_hash, :full_name, :major)
            """
        ),
        {
            "student_id": student_id,
            "email": f"{student_id.lower()}@gm.uit.edu.vn",
            "password_hash": "integration-test-hash",
            "full_name": "Step 7 SQL Server Test",
            "major": "Kiem thu tich hop",
        },
    ).scalar_one()


def test_sqlserver_schema_has_required_tables_columns_indexes_and_triggers(
    sqlserver_connection: sa.Connection,
):
    connection = sqlserver_connection

    missing_tables = connection.execute(
        sa.text(
            """
            SELECT expected.table_name
            FROM (VALUES
                (N'CATEGORIES'), (N'USERS'), (N'PRODUCTS'),
                (N'TRANSACTIONS'), (N'REVIEWS')
            ) AS expected(table_name)
            WHERE OBJECT_ID(N'dbo.' + expected.table_name, N'U') IS NULL
            """
        )
    ).scalars().all()
    assert not missing_tables, f"Missing dbo tables: {missing_tables}"

    actual_columns = {
        (row.table_name.casefold(), row.column_name.casefold())
        for row in connection.execute(
            sa.text(
                """
                SELECT t.name AS table_name, c.name AS column_name
                FROM sys.tables AS t
                JOIN sys.columns AS c ON c.object_id = t.object_id
                WHERE t.schema_id = SCHEMA_ID(N'dbo')
                """
            )
        )
    }
    required_columns = {
        ("users", "updated_at"),
        ("products", "updated_at"),
        ("transactions", "updated_at"),
        ("transactions", "buyer_confirmed_at"),
        ("transactions", "seller_confirmed_at"),
        ("reviews", "transaction_id"),
        ("reviews", "reviewer_id"),
        ("reviews", "reviewee_id"),
        ("reviews", "rating"),
    }
    assert required_columns <= actual_columns, (
        f"Missing SQL Server columns: {sorted(required_columns - actual_columns)}"
    )

    active_product_index = connection.execute(
        sa.text(
            """
            SELECT is_unique, filter_definition
            FROM sys.indexes
            WHERE object_id = OBJECT_ID(N'dbo.TRANSACTIONS')
              AND name = N'UX_Transactions_ActiveProduct'
            """
        )
    ).first()
    assert active_product_index is not None, "Missing UX_Transactions_ActiveProduct."
    assert active_product_index.is_unique, "UX_Transactions_ActiveProduct must be UNIQUE."
    normalized_filter = re.sub(
        r"[\[\]\s()]", "", active_product_index.filter_definition or ""
    ).casefold()
    assert (
        "status<>'cancelled'" in normalized_filter
        or "status!='cancelled'" in normalized_filter
    ), f"Unexpected active-product index filter: {active_product_index.filter_definition!r}"

    enabled_triggers = {
        row.name
        for row in connection.execute(
            sa.text(
                """
                SELECT name
                FROM sys.triggers
                WHERE is_disabled = 0
                  AND parent_id IN (
                      OBJECT_ID(N'dbo.USERS'),
                      OBJECT_ID(N'dbo.PRODUCTS'),
                      OBJECT_ID(N'dbo.TRANSACTIONS')
                  )
                """
            )
        )
    }
    required_triggers = {
        "TRG_Users_UpdatedAt",
        "TRG_Products_UpdatedAt",
        "TRG_Transactions_UpdatedAt",
    }
    assert required_triggers <= enabled_triggers, (
        f"Missing or disabled updated_at triggers: {sorted(required_triggers - enabled_triggers)}"
    )


def test_sqlserver_updated_at_trigger_changes_timestamp(sqlserver_connection: sa.Connection):
    connection = sqlserver_connection
    user_id = _insert_user(connection)

    old_timestamp = sa.literal_column("CONVERT(DATETIME2(0), '2000-01-01T00:00:00')")
    connection.execute(
        sa.text(
            "UPDATE dbo.USERS SET updated_at = CONVERT(DATETIME2(0), "
            "'2000-01-01T00:00:00') WHERE user_id = :user_id"
        ),
        {"user_id": user_id},
    )
    before = connection.execute(
        sa.text("SELECT updated_at FROM dbo.USERS WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).scalar_one()

    connection.execute(
        sa.text("UPDATE dbo.USERS SET full_name = :name WHERE user_id = :user_id"),
        {"name": "Step 7 Trigger Verified", "user_id": user_id},
    )
    after = connection.execute(
        sa.text("SELECT updated_at FROM dbo.USERS WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).scalar_one()

    assert before.year == 2000
    assert after > before, "TRG_Users_UpdatedAt did not refresh updated_at after an UPDATE."


def test_sqlserver_filtered_unique_index_only_blocks_active_transactions(
    sqlserver_connection: sa.Connection,
):
    connection = sqlserver_connection
    seller_id = _insert_user(connection)
    buyer_id = _insert_user(connection)
    category_id = connection.execute(
        sa.text(
            """
            INSERT INTO dbo.CATEGORIES (category_name)
            OUTPUT INSERTED.category_id
            VALUES (:category_name)
            """
        ),
        {"category_name": f"Step7-{uuid.uuid4().hex[:12]}"},
    ).scalar_one()
    product_id = connection.execute(
        sa.text(
            """
            INSERT INTO dbo.PRODUCTS
                (seller_id, category_id, title, price, condition, status)
            OUTPUT INSERTED.product_id
            VALUES
                (:seller_id, :category_id, :title, 25000, 'Good', 'Reserved')
            """
        ),
        {
            "seller_id": seller_id,
            "category_id": category_id,
            "title": f"Step 7 index test {uuid.uuid4().hex[:8]}",
        },
    ).scalar_one()

    def insert_transaction(status: str) -> None:
        connection.execute(
            sa.text(
                """
                INSERT INTO dbo.TRANSACTIONS (product_id, buyer_id, amount, status)
                VALUES (:product_id, :buyer_id, 25000, :status)
                """
            ),
            {"product_id": product_id, "buyer_id": buyer_id, "status": status},
        )

    # A cancelled row is outside the filtered index and must not block a new request.
    insert_transaction("Cancelled")
    insert_transaction("Pending")

    # A second non-cancelled row for the same product must violate the unique index.
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            insert_transaction("Accepted")

    active_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM dbo.TRANSACTIONS
            WHERE product_id = :product_id AND status <> 'Cancelled'
            """
        ),
        {"product_id": product_id},
    ).scalar_one()
    assert active_count == 1
