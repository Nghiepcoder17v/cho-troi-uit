"""Opt-in SQL Server integration tests for DB-6B product reports.

The database URL must point to an isolated *_test database. The schema test rolls
back its fixture transaction; the HTTP test explicitly removes only its own rows.
"""
from __future__ import annotations

import os
import re
import uuid

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.db6b_sqlserver_integration


@pytest.fixture()
def sqlserver_connection():
    if os.getenv("RUN_SQLSERVER_INTEGRATION") != "1":
        pytest.skip("Set RUN_SQLSERVER_INTEGRATION=1 to enable SQL Server integration tests.")

    database_url = os.getenv("SQLSERVER_TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("RUN_SQLSERVER_INTEGRATION=1 but SQLSERVER_TEST_DATABASE_URL is missing.")

    database_name = make_url(database_url).database or ""
    if not database_name.casefold().endswith("_test"):
        pytest.fail("Refusing to run report integration tests outside a database ending in '_test'.")

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
    student_id = f"8{suffix:07d}"
    return connection.execute(
        sa.text(
            """
            INSERT INTO dbo.USERS
                (student_id, email, password_hash, full_name, major)
            OUTPUT INSERTED.user_id
            VALUES (:student_id, :email, :password_hash, :full_name, :major)
            """
        ),
        {
            "student_id": student_id,
            "email": f"{student_id}@gm.uit.edu.vn",
            "password_hash": "report-integration-test-hash",
            "full_name": "DB6B SQL Server Test",
            "major": "Integration",
        },
    ).scalar_one()


def test_sqlserver_product_reports_schema_constraints_and_unique_open_index(
    sqlserver_connection: sa.Connection,
):
    connection = sqlserver_connection
    table_id = connection.execute(
        sa.text("SELECT OBJECT_ID(N'dbo.PRODUCT_REPORTS', N'U')")
    ).scalar_one_or_none()
    assert table_id is not None, "Apply 20261113_product_reports.sql before this test."

    columns = {
        row.name: (row.is_nullable, row.type_name, row.scale)
        for row in connection.execute(
            sa.text(
                """
                SELECT c.name, c.is_nullable, ty.name AS type_name, c.scale
                FROM sys.columns c
                JOIN sys.types ty ON c.user_type_id = ty.user_type_id
                WHERE c.object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
                """
            )
        )
    }
    assert columns == {
        "report_id": (False, "bigint", 0),
        "reporter_user_id": (False, "int", 0),
        "target_product_id": (False, "int", 0),
        "reason_code": (False, "varchar", 0),
        "description": (True, "nvarchar", 0),
        "status": (False, "varchar", 0),
        "submitted_at": (False, "datetime2", 0),
        "updated_at": (False, "datetime2", 0),
    }

    foreign_keys = {
        row.parent_column: (row.referenced_table, row.delete_action)
        for row in connection.execute(
            sa.text(
                """
                SELECT pc.name AS parent_column, rt.name AS referenced_table,
                       fk.delete_referential_action_desc AS delete_action
                FROM sys.foreign_keys fk
                JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id
                    AND pc.column_id = fkc.parent_column_id
                JOIN sys.tables rt ON rt.object_id = fkc.referenced_object_id
                WHERE fk.parent_object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
                """
            )
        )
    }
    assert foreign_keys == {
        "reporter_user_id": ("USERS", "NO_ACTION"),
        "target_product_id": ("PRODUCTS", "NO_ACTION"),
    }

    checks = {
        row.name
        for row in connection.execute(
            sa.text(
                """
                SELECT name FROM sys.check_constraints
                WHERE parent_object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
                  AND is_disabled = 0 AND is_not_trusted = 0
                """
            )
        )
    }
    assert {
        "CHK_ProductReports_ReasonCode",
        "CHK_ProductReports_Description",
        "CHK_ProductReports_Status",
    } <= checks

    open_index = connection.execute(
        sa.text(
            """
            SELECT is_unique, filter_definition
            FROM sys.indexes
            WHERE object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
              AND name = N'UX_ProductReports_ReporterTargetOpen'
            """
        )
    ).first()
    assert open_index is not None and open_index.is_unique
    normalized_filter = re.sub(r"[\[\]\s()]", "", open_index.filter_definition or "").casefold()
    assert "status='submitted'" in normalized_filter, open_index.filter_definition

    reporter_id = _insert_user(connection)
    seller_id = _insert_user(connection)
    category_id = connection.execute(
        sa.text(
            """
            INSERT INTO dbo.CATEGORIES (category_name)
            OUTPUT INSERTED.category_id VALUES (:name)
            """
        ),
        {"name": f"DB6B-{uuid.uuid4().hex[:10]}"},
    ).scalar_one()
    product_id = connection.execute(
        sa.text(
            """
            INSERT INTO dbo.PRODUCTS
                (seller_id, category_id, title, price, condition, status)
            OUTPUT INSERTED.product_id
            VALUES (:seller, :category, :title, 50000, 'Good', 'Available')
            """
        ),
        {
            "seller": seller_id,
            "category": category_id,
            "title": f"DB6B report target {uuid.uuid4().hex[:8]}",
        },
    ).scalar_one()

    report_id, status, submitted_at = connection.execute(
        sa.text(
            """
            INSERT INTO dbo.PRODUCT_REPORTS
                (reporter_user_id, target_product_id, reason_code, description)
            OUTPUT INSERTED.report_id, INSERTED.status, INSERTED.submitted_at
            VALUES (:reporter, :product, 'OTHER', :description)
            """
        ),
        {
            "reporter": reporter_id,
            "product": product_id,
            "description": "Plain text integration report",
        },
    ).one()
    assert report_id > 0 and status == "Submitted" and submitted_at is not None

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                sa.text(
                    """
                    INSERT INTO dbo.PRODUCT_REPORTS
                        (reporter_user_id, target_product_id, reason_code)
                    VALUES (:reporter, :product, 'OTHER')
                    """
                ),
                {"reporter": reporter_id, "product": product_id},
            )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                sa.text(
                    """
                    INSERT INTO dbo.PRODUCT_REPORTS
                        (reporter_user_id, target_product_id, reason_code)
                    VALUES (:reporter, :product, 'INVALID')
                    """
                ),
                {"reporter": seller_id, "product": product_id},
            )


def test_sqlserver_product_report_api_enforces_privacy_duplicate_and_rate_limit(
    sqlserver_connection: sa.Connection,
):
    from database import get_db
    from main import app
    from security import create_access_token

    database_url = os.environ["SQLSERVER_TEST_DATABASE_URL"]
    database_name = sqlserver_connection.execute(sa.text("SELECT DB_NAME()")).scalar_one()
    assert database_name.casefold().endswith("_test")

    engine = sa.create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    created_user_ids: list[int] = []
    created_product_ids: list[int] = []
    category_id: int | None = None

    try:
        with engine.begin() as setup:
            seller_id = _insert_user(setup)
            reporter_id = _insert_user(setup)
            outsider_id = _insert_user(setup)
            created_user_ids.extend([seller_id, reporter_id, outsider_id])
            category_id = setup.execute(
                sa.text(
                    """
                    INSERT INTO dbo.CATEGORIES (category_name)
                    OUTPUT INSERTED.category_id VALUES (:name)
                    """
                ),
                {"name": f"DB6BAPI-{uuid.uuid4().hex[:10]}"},
            ).scalar_one()

            for index in range(7):
                product_id = setup.execute(
                    sa.text(
                        """
                        INSERT INTO dbo.PRODUCTS
                            (seller_id, category_id, title, price, condition, status)
                        OUTPUT INSERTED.product_id
                        VALUES (:seller, :category, :title, 50000, 'Good', 'Available')
                        """
                    ),
                    {
                        "seller": seller_id,
                        "category": category_id,
                        "title": f"DB6B API target {index}-{uuid.uuid4().hex[:6]}",
                    },
                ).scalar_one()
                created_product_ids.append(product_id)

        def override_get_db():
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        origin = "http://localhost:5173"
        reporter_headers = {
            "Cookie": f"access_token={create_access_token(reporter_id)}",
            "Origin": origin,
        }
        outsider_headers = {
            "Cookie": f"access_token={create_access_token(outsider_id)}",
            "Origin": origin,
        }
        seller_headers = {
            "Cookie": f"access_token={create_access_token(seller_id)}",
            "Origin": origin,
        }

        with TestClient(app, base_url="https://testserver", headers={"Origin": origin}) as client:
            assert client.post(
                "/api/reports",
                json={"target_product_id": created_product_ids[0], "reason_code": "OTHER"},
            ).status_code == 401

            first = client.post(
                "/api/reports",
                headers=reporter_headers,
                json={
                    "target_product_id": created_product_ids[0],
                    "reason_code": "MISLEADING_LISTING",
                    "description": "A plain-text description.",
                },
            )
            assert first.status_code == 201, first.text
            receipt = first.json()["data"]
            assert receipt["status"] == "Submitted"
            assert "reporter_user_id" not in receipt
            assert "description" not in receipt

            duplicate = client.post(
                "/api/reports",
                headers=reporter_headers,
                json={"target_product_id": created_product_ids[0], "reason_code": "OTHER"},
            )
            assert duplicate.status_code == 409

            same_target_other_reporter = client.post(
                "/api/reports",
                headers=outsider_headers,
                json={"target_product_id": created_product_ids[0], "reason_code": "OTHER"},
            )
            assert same_target_other_reporter.status_code == 201

            for product_id in created_product_ids[1:5]:
                response = client.post(
                    "/api/reports",
                    headers=reporter_headers,
                    json={"target_product_id": product_id, "reason_code": "OTHER"},
                )
                assert response.status_code == 201, response.text

            over_limit = client.post(
                "/api/reports",
                headers=reporter_headers,
                json={"target_product_id": created_product_ids[5], "reason_code": "OTHER"},
            )
            assert over_limit.status_code == 429

            own_listing = client.post(
                "/api/reports",
                headers=seller_headers,
                json={"target_product_id": created_product_ids[0], "reason_code": "OTHER"},
            )
            assert own_listing.status_code == 400

            with engine.begin() as control:
                control.execute(
                    sa.text("UPDATE dbo.PRODUCTS SET status = 'Hidden' WHERE product_id = :id"),
                    {"id": created_product_ids[5]},
                )
                control.execute(
                    sa.text("UPDATE dbo.PRODUCTS SET status = 'Reserved' WHERE product_id = :id"),
                    {"id": created_product_ids[6]},
                )

            for product_id in created_product_ids[5:7]:
                rejected = client.post(
                    "/api/reports",
                    headers=outsider_headers,
                    json={"target_product_id": product_id, "reason_code": "OTHER"},
                )
                assert rejected.status_code == 404

            with engine.connect() as read_connection:
                reporter_count = read_connection.execute(
                    sa.text(
                        """
                        SELECT COUNT(*) FROM dbo.PRODUCT_REPORTS
                        WHERE reporter_user_id = :reporter
                        """
                    ),
                    {"reporter": reporter_id},
                ).scalar_one()
                unchanged_status = read_connection.execute(
                    sa.text("SELECT status FROM dbo.PRODUCTS WHERE product_id = :id"),
                    {"id": created_product_ids[0]},
                ).scalar_one()
            assert reporter_count == 5
            assert unchanged_status == "Available"
    finally:
        app.dependency_overrides.pop(get_db, None)
        with engine.begin() as cleanup:
            cleanup.execute(
                sa.text(
                    """
                    DELETE FROM dbo.PRODUCT_REPORTS
                    WHERE reporter_user_id IN :user_ids
                       OR target_product_id IN :product_ids
                    """
                ).bindparams(
                    sa.bindparam("user_ids", expanding=True),
                    sa.bindparam("product_ids", expanding=True),
                ),
                {
                    "user_ids": created_user_ids or [-1],
                    "product_ids": created_product_ids or [-1],
                },
            )
            if created_product_ids:
                cleanup.execute(
                    sa.text(
                        "DELETE FROM dbo.PRODUCTS WHERE product_id IN :product_ids"
                    ).bindparams(sa.bindparam("product_ids", expanding=True)),
                    {"product_ids": created_product_ids},
                )
            for user_id in created_user_ids:
                cleanup.execute(
                    sa.text("DELETE FROM dbo.USERS WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )
            if category_id is not None:
                cleanup.execute(
                    sa.text("DELETE FROM dbo.CATEGORIES WHERE category_id = :id"),
                    {"id": category_id},
                )
        engine.dispose()
