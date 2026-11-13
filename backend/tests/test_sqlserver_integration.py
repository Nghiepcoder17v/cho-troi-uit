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
    suffix = int(uuid.uuid4().hex[:7], 16) % 10_000_000
    student_id = f"9{suffix:07d}"
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

    student_id_check = connection.execute(
        sa.text(
            """
            SELECT is_disabled, is_not_trusted
            FROM sys.check_constraints
            WHERE parent_object_id = OBJECT_ID(N'dbo.USERS')
              AND name = N'CK_Users_StudentIdFormat'
            """
        )
    ).first()
    assert student_id_check is not None, "Missing CK_Users_StudentIdFormat."
    assert not student_id_check.is_disabled and not student_id_check.is_not_trusted

    student_id_unique = connection.execute(
        sa.text(
            """
            SELECT type_desc
            FROM sys.key_constraints
            WHERE parent_object_id = OBJECT_ID(N'dbo.USERS')
              AND name = N'UQ_Users_StudentId'
            """
        )
    ).scalar_one_or_none()
    assert student_id_unique == "UNIQUE_CONSTRAINT", "Student ID uniqueness must remain enforced."

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


def test_sqlserver_rejects_student_ids_that_are_not_eight_digits(
    sqlserver_connection: sa.Connection,
):
    with pytest.raises(IntegrityError):
        sqlserver_connection.execute(
            sa.text(
                """
                INSERT INTO dbo.USERS
                    (student_id, email, password_hash, full_name, major)
                VALUES
                    (:student_id, :email, :password_hash, :full_name, :major)
                """
            ),
            {
                "student_id": "1234567",
                "email": "1234567@gm.uit.edu.vn",
                "password_hash": "integration-test-hash",
                "full_name": "Invalid Student ID Test",
                "major": "Kiem thu tich hop",
            },
        )


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


def test_sqlserver_user_favorites_schema_composite_key_and_foreign_keys(
    sqlserver_connection: sa.Connection,
):
    connection = sqlserver_connection
    table_id = connection.execute(
        sa.text("SELECT OBJECT_ID(N'dbo.USER_FAVORITES', N'U')")
    ).scalar_one_or_none()
    assert table_id is not None, "Apply 20261113_user_favorites.sql before this test."

    columns = {
        row.name: (row.is_nullable, row.type_name, row.scale)
        for row in connection.execute(
            sa.text(
                """
                SELECT c.name, c.is_nullable, ty.name AS type_name, c.scale
                FROM sys.columns c
                JOIN sys.types ty ON c.user_type_id = ty.user_type_id
                WHERE c.object_id = OBJECT_ID(N'dbo.USER_FAVORITES')
                """
            )
        )
    }
    assert columns == {
        "user_id": (False, "int", 0),
        "product_id": (False, "int", 0),
        "created_at": (False, "datetime2", 0),
    }

    primary_key = connection.execute(
        sa.text(
            """
            SELECT c.name
            FROM sys.key_constraints kc
            JOIN sys.index_columns ic
              ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
            JOIN sys.columns c
              ON c.object_id = ic.object_id AND c.column_id = ic.column_id
            WHERE kc.parent_object_id = OBJECT_ID(N'dbo.USER_FAVORITES')
              AND kc.type = 'PK'
            ORDER BY ic.key_ordinal
            """
        )
    ).scalars().all()
    assert primary_key == ["user_id", "product_id"]

    foreign_keys = {
        row.parent_column: (row.referenced_table, row.referenced_column, row.delete_action)
        for row in connection.execute(
            sa.text(
                """
                SELECT pc.name AS parent_column, rt.name AS referenced_table,
                       rc.name AS referenced_column, fk.delete_referential_action_desc AS delete_action
                FROM sys.foreign_keys fk
                JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
                JOIN sys.tables rt ON rt.object_id = fkc.referenced_object_id
                JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
                WHERE fk.parent_object_id = OBJECT_ID(N'dbo.USER_FAVORITES')
                """
            )
        )
    }
    assert foreign_keys["user_id"] == ("USERS", "user_id", "NO_ACTION")
    assert foreign_keys["product_id"] == ("PRODUCTS", "product_id", "NO_ACTION")

    index_rows = connection.execute(
        sa.text(
            """
            SELECT c.name, ic.is_descending_key
            FROM sys.indexes i
            JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
            WHERE i.object_id = OBJECT_ID(N'dbo.USER_FAVORITES')
              AND i.name = N'IX_UserFavorites_UserCreated'
              AND ic.key_ordinal > 0
            ORDER BY ic.key_ordinal
            """
        )
    ).all()
    assert [(row.name, row.is_descending_key) for row in index_rows] == [
        ("user_id", False), ("created_at", True), ("product_id", True)
    ]

    default_definition = connection.execute(
        sa.text(
            """
            SELECT dc.definition
            FROM sys.default_constraints dc
            JOIN sys.columns c ON c.object_id = dc.parent_object_id AND c.column_id = dc.parent_column_id
            WHERE dc.parent_object_id = OBJECT_ID(N'dbo.USER_FAVORITES')
              AND c.name = N'created_at'
            """
        )
    ).scalar_one()
    assert "SYSUTCDATETIME" in default_definition.upper()

    user_id = _insert_user(connection)
    category_id = connection.execute(
        sa.text(
            """
            INSERT INTO dbo.CATEGORIES (category_name)
            OUTPUT INSERTED.category_id
            VALUES (:category_name)
            """
        ),
        {"category_name": f"Favorites-{uuid.uuid4().hex[:10]}"},
    ).scalar_one()
    product_id = connection.execute(
        sa.text(
            """
            INSERT INTO dbo.PRODUCTS
                (seller_id, category_id, title, price, condition, status)
            OUTPUT INSERTED.product_id
            VALUES (:seller_id, :category_id, :title, 30000, 'Good', 'Available')
            """
        ),
        {
            "seller_id": user_id,
            "category_id": category_id,
            "title": f"Favorite integration {uuid.uuid4().hex[:8]}",
        },
    ).scalar_one()

    created_at = connection.execute(
        sa.text(
            """
            INSERT INTO dbo.USER_FAVORITES (user_id, product_id)
            OUTPUT INSERTED.created_at
            VALUES (:user_id, :product_id)
            """
        ),
        {"user_id": user_id, "product_id": product_id},
    ).scalar_one()
    assert created_at is not None

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                sa.text(
                    "INSERT INTO dbo.USER_FAVORITES (user_id, product_id) VALUES (:user_id, :product_id)"
                ),
                {"user_id": user_id, "product_id": product_id},
            )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                sa.text(
                    "INSERT INTO dbo.USER_FAVORITES (user_id, product_id) VALUES (:user_id, :product_id)"
                ),
                {"user_id": user_id, "product_id": -999999},
            )


def test_sqlserver_favorites_api_round_trip_uses_real_sqlserver_session(
    sqlserver_connection: sa.Connection,
):
    """Exercise Favorites HTTP routes against an independent SQL Server pool.

    FastAPI runs synchronous routes in worker threads. The HTTP test therefore
    uses an Engine pool instead of sharing the fixture's pyodbc connection
    across threads. Test rows are explicitly removed in finally.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from database import get_db
    from main import app
    from security import create_access_token

    database_name = sqlserver_connection.execute(sa.text("SELECT DB_NAME()")).scalar_one()
    assert database_name.casefold().endswith("_test")

    engine = sa.create_engine(
        os.environ["SQLSERVER_TEST_DATABASE_URL"],
        pool_pre_ping=True,
    )
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    created_user_ids: list[int] = []
    category_id: int | None = None
    product_id: int | None = None

    try:
        with engine.begin() as setup:
            seller_id = _insert_user(setup)
            buyer_id = _insert_user(setup)
            outsider_id = _insert_user(setup)
            created_user_ids.extend([seller_id, buyer_id, outsider_id])

            category_id = setup.execute(
                sa.text(
                    """
                    INSERT INTO dbo.CATEGORIES (category_name)
                    OUTPUT INSERTED.category_id
                    VALUES (:category_name)
                    """
                ),
                {"category_name": f"FavoritesAPI-{uuid.uuid4().hex[:10]}"},
            ).scalar_one()
            product_id = setup.execute(
                sa.text(
                    """
                    INSERT INTO dbo.PRODUCTS
                        (seller_id, category_id, title, description, price, condition, status)
                    OUTPUT INSERTED.product_id
                    VALUES
                        (:seller_id, :category_id, :title, :description, 42000, 'Good', 'Available')
                    """
                ),
                {
                    "seller_id": seller_id,
                    "category_id": category_id,
                    "title": f"Favorites SQL API {uuid.uuid4().hex[:8]}",
                    "description": "Private description must not be returned by Favorites.",
                },
            ).scalar_one()

        def override_get_db():
            db = SessionFactory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        origin = "http://localhost:5173"
        buyer_headers = {
            "Cookie": f"access_token={create_access_token(buyer_id)}",
            "Origin": origin,
        }
        seller_headers = {
            "Cookie": f"access_token={create_access_token(seller_id)}",
            "Origin": origin,
        }
        outsider_headers = {
            "Cookie": f"access_token={create_access_token(outsider_id)}",
            "Origin": origin,
        }

        with TestClient(app, base_url="https://testserver", headers={"Origin": origin}) as client:
            assert client.get("/api/users/me/favorites").status_code == 401

            first_add = client.put(
                f"/api/users/me/favorites/{product_id}",
                headers=buyer_headers,
            )
            assert first_add.status_code == 200, first_add.text

            with engine.connect() as read_connection:
                first_created_at = read_connection.execute(
                    sa.text(
                        """
                        SELECT created_at
                        FROM dbo.USER_FAVORITES
                        WHERE user_id = :user_id AND product_id = :product_id
                        """
                    ),
                    {"user_id": buyer_id, "product_id": product_id},
                ).scalar_one()

            duplicate_add = client.put(
                f"/api/users/me/favorites/{product_id}",
                headers=buyer_headers,
            )
            assert duplicate_add.status_code == 200, duplicate_add.text

            with engine.connect() as read_connection:
                second_created_at = read_connection.execute(
                    sa.text(
                        """
                        SELECT created_at
                        FROM dbo.USER_FAVORITES
                        WHERE user_id = :user_id AND product_id = :product_id
                        """
                    ),
                    {"user_id": buyer_id, "product_id": product_id},
                ).scalar_one()
            assert second_created_at == first_created_at

            buyer_list = client.get(
                "/api/users/me/favorites?page=1&page_size=10",
                headers=buyer_headers,
            )
            assert buyer_list.status_code == 200, buyer_list.text
            item = buyer_list.json()["data"][0]
            assert item["product_id"] == product_id
            assert item["status"] == "Available"
            assert item["product"]["seller"]["user_id"] == seller_id
            assert "description" not in item["product"]
            assert "email" not in item["product"]["seller"]
            assert "student_id" not in item["product"]["seller"]

            outsider_add = client.put(
                f"/api/users/me/favorites/{product_id}",
                headers=outsider_headers,
            )
            assert outsider_add.status_code == 200, outsider_add.text

            outsider_list = client.get(
                "/api/users/me/favorites",
                headers=outsider_headers,
            )
            seller_list = client.get(
                "/api/users/me/favorites",
                headers=seller_headers,
            )
            assert outsider_list.status_code == seller_list.status_code == 200
            assert outsider_list.json()["data"][0]["product_id"] == product_id
            assert seller_list.json()["data"] == []

            with engine.begin() as control:
                hidden_update = control.execute(
                    sa.text("UPDATE dbo.PRODUCTS SET status = 'Hidden' WHERE product_id = :product_id"),
                    {"product_id": product_id},
                )
                assert hidden_update.rowcount == 1

            hidden_list = client.get(
                "/api/users/me/favorites",
                headers=buyer_headers,
            )
            assert hidden_list.status_code == 200, hidden_list.text
            hidden_item = hidden_list.json()["data"][0]
            assert hidden_item["status"] == "Hidden"
            assert hidden_item["product"] is None

            hidden_add = client.put(
                f"/api/users/me/favorites/{product_id}",
                headers=outsider_headers,
            )
            assert hidden_add.status_code == 404

            delete_response = client.delete(
                f"/api/users/me/favorites/{product_id}",
                headers=buyer_headers,
            )
            assert delete_response.status_code == 204
            repeated_delete = client.delete(
                f"/api/users/me/favorites/{product_id}",
                headers=buyer_headers,
            )
            assert repeated_delete.status_code == 204

            empty_list = client.get(
                "/api/users/me/favorites",
                headers=buyer_headers,
            )
            assert empty_list.status_code == 200
            assert empty_list.json()["data"] == []

            outsider_after_buyer_delete = client.get(
                "/api/users/me/favorites",
                headers=outsider_headers,
            )
            assert outsider_after_buyer_delete.status_code == 200
            assert outsider_after_buyer_delete.json()["data"][0]["product_id"] == product_id
            assert outsider_after_buyer_delete.json()["data"][0]["product"] is None

            with engine.connect() as read_connection:
                transaction_count = read_connection.execute(
                    sa.text(
                        "SELECT COUNT(*) FROM dbo.TRANSACTIONS WHERE product_id = :product_id"
                    ),
                    {"product_id": product_id},
                ).scalar_one()
            assert transaction_count == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        with engine.begin() as cleanup:
            if product_id is not None:
                cleanup.execute(
                    sa.text(
                        """
                        DELETE FROM dbo.TRANSACTION_EVENTS
                        WHERE transaction_id IN (
                            SELECT transaction_id FROM dbo.TRANSACTIONS WHERE product_id = :product_id
                        )
                        """
                    ),
                    {"product_id": product_id},
                )
                cleanup.execute(
                    sa.text("DELETE FROM dbo.REVIEWS WHERE transaction_id IN (SELECT transaction_id FROM dbo.TRANSACTIONS WHERE product_id = :product_id)"),
                    {"product_id": product_id},
                )
                cleanup.execute(
                    sa.text("DELETE FROM dbo.TRANSACTIONS WHERE product_id = :product_id"),
                    {"product_id": product_id},
                )
                cleanup.execute(
                    sa.text("DELETE FROM dbo.USER_FAVORITES WHERE product_id = :product_id"),
                    {"product_id": product_id},
                )
                cleanup.execute(
                    sa.text("DELETE FROM dbo.PRODUCTS WHERE product_id = :product_id"),
                    {"product_id": product_id},
                )
            for created_user_id in created_user_ids:
                cleanup.execute(
                    sa.text("DELETE FROM dbo.USER_FAVORITES WHERE user_id = :user_id"),
                    {"user_id": created_user_id},
                )
                cleanup.execute(
                    sa.text("DELETE FROM dbo.USERS WHERE user_id = :user_id"),
                    {"user_id": created_user_id},
                )
            if category_id is not None:
                cleanup.execute(
                    sa.text("DELETE FROM dbo.CATEGORIES WHERE category_id = :category_id"),
                    {"category_id": category_id},
                )
        engine.dispose()
