"""SQL Server-only DB-6C schema, filtered-index and audit-atomicity tests.

The tests are opt-in and refuse any database whose name does not end in _test.
They create and clean only rows belonging to this test.
"""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.sqlserver_integration


@pytest.fixture()
def db6c_engine():
    if os.getenv("RUN_SQLSERVER_INTEGRATION") != "1":
        pytest.skip("Set RUN_SQLSERVER_INTEGRATION=1 to enable SQL Server integration tests.")
    database_url = os.getenv("SQLSERVER_TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("RUN_SQLSERVER_INTEGRATION=1 but SQLSERVER_TEST_DATABASE_URL is missing.")
    database_name = make_url(database_url).database or ""
    if not database_name.casefold().endswith("_test"):
        pytest.fail("Refusing to run DB-6C tests outside a database ending in '_test'.")
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


def _insert_user(connection: sa.Connection, label: str) -> int:
    suffix = uuid.uuid4().hex[:7]
    student_id = f"8{suffix}"
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
            "password_hash": "db6c-integration-test-hash",
            "full_name": f"DB6C {label}",
            "major": "Integration",
        },
    ).scalar_one()


def _insert_product(connection: sa.Connection, seller_id: int) -> tuple[int, int]:
    category_id = connection.execute(
        sa.text(
            """
            INSERT INTO dbo.CATEGORIES (category_name)
            OUTPUT INSERTED.category_id VALUES (:name)
            """
        ),
        {"name": f"DB6C-{uuid.uuid4().hex[:10]}"},
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
            "title": f"DB6C moderation target {uuid.uuid4().hex[:8]}",
        },
    ).scalar_one()
    return category_id, product_id


def test_db6c_schema_and_open_report_index_cover_all_nonterminal_states(db6c_engine):
    with db6c_engine.begin() as connection:
        assert connection.execute(
            sa.text("SELECT OBJECT_ID(N'dbo.MODERATION_ACTIONS', N'U')")
        ).scalar_one_or_none() is not None
        assert connection.execute(
            sa.text("SELECT OBJECT_ID(N'dbo.PRODUCT_MODERATION', N'U')")
        ).scalar_one_or_none() is not None
        assert connection.execute(
            sa.text("SELECT OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENTS', N'U')")
        ).scalar_one_or_none() is not None

        roles = set(
            connection.execute(sa.text("SELECT role_code FROM dbo.ROLES")).scalars()
        )
        assert {"MODERATOR", "ADMIN"} <= roles

        index = connection.execute(
            sa.text(
                """
                SELECT is_unique, filter_definition
                FROM sys.indexes
                WHERE object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
                  AND name = N'UX_ProductReports_ReporterTargetOpen'
                """
            )
        ).one()
        assert index.is_unique
        normalized_filter = (
            (index.filter_definition or "")
            .replace("[", "")
            .replace("]", "")
            .replace(" ", "")
            .replace("(", "")
            .replace(")", "")
            .casefold()
        )
        assert "status<>'dismissed'" in normalized_filter
        assert "status<>'actioned'" in normalized_filter

        reporter_id = _insert_user(connection, "Index Reporter")
        seller_id = _insert_user(connection, "Index Seller")
        _category_id, product_id = _insert_product(connection, seller_id)

        report_id = connection.execute(
            sa.text(
                """
                INSERT INTO dbo.PRODUCT_REPORTS
                    (reporter_user_id, target_product_id, reason_code)
                OUTPUT INSERTED.report_id
                VALUES (:reporter, :product, 'OTHER')
                """
            ),
            {"reporter": reporter_id, "product": product_id},
        ).scalar_one()

        for state in ("InReview", "Escalated"):
            connection.execute(
                sa.text("UPDATE dbo.PRODUCT_REPORTS SET status = :status WHERE report_id = :id"),
                {"status": state, "id": report_id},
            )
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

        connection.execute(
            sa.text("UPDATE dbo.PRODUCT_REPORTS SET status = 'Dismissed' WHERE report_id = :id"),
            {"id": report_id},
        )
        second_report_id = connection.execute(
            sa.text(
                """
                INSERT INTO dbo.PRODUCT_REPORTS
                    (reporter_user_id, target_product_id, reason_code, status)
                OUTPUT INSERTED.report_id
                VALUES (:reporter, :product, 'OTHER', 'Actioned')
                """
            ),
            {"reporter": reporter_id, "product": product_id},
        ).scalar_one()
        assert second_report_id != report_id

        # This schema/index test commits only after deleting all of its own rows.
        connection.execute(
            sa.text("DELETE FROM dbo.PRODUCT_REPORTS WHERE reporter_user_id = :reporter"),
            {"reporter": reporter_id},
        )
        connection.execute(
            sa.text("DELETE FROM dbo.PRODUCTS WHERE product_id = :product"),
            {"product": product_id},
        )
        connection.execute(
            sa.text("DELETE FROM dbo.USERS WHERE user_id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": [reporter_id, seller_id]},
        )
        connection.execute(
            sa.text("DELETE FROM dbo.CATEGORIES WHERE category_id = :id"),
            {"id": _category_id},
        )


def test_db6c_api_checks_live_role_and_rolls_back_when_audit_insert_fails(db6c_engine):
    from database import get_db
    from main import app
    from security import create_access_token

    session_factory = sessionmaker(bind=db6c_engine, autoflush=False, autocommit=False)
    created_user_ids: list[int] = []
    created_product_ids: list[int] = []
    created_report_ids: list[int] = []
    category_ids: list[int] = []
    trigger_name = "TR_DB6C_RejectAudit_Test"
    origin = "http://localhost:5173"
    app.dependency_overrides.pop(get_db, None)

    try:
        with db6c_engine.begin() as setup:
            seller_id = _insert_user(setup, "API Seller")
            moderator_one_id = _insert_user(setup, "Moderator One")
            moderator_two_id = _insert_user(setup, "Moderator Two")
            reporter_id = _insert_user(setup, "Reporter")
            created_user_ids.extend([seller_id, moderator_one_id, moderator_two_id, reporter_id])
            category_and_product = _insert_product(setup, seller_id)
            category_id, product_id = category_and_product
            category_ids.append(category_id)
            created_product_ids.append(product_id)

            setup.execute(
                sa.text(
                    """
                    INSERT INTO dbo.USER_ROLE_ASSIGNMENTS (user_id, role_code, grant_reason)
                    VALUES (:user_id, 'MODERATOR', 'DB6C isolated integration fixture')
                    """
                ),
                [{"user_id": moderator_one_id}, {"user_id": moderator_two_id}],
            )
            report_id = setup.execute(
                sa.text(
                    """
                    INSERT INTO dbo.PRODUCT_REPORTS
                        (reporter_user_id, target_product_id, reason_code, description)
                    OUTPUT INSERTED.report_id
                    VALUES (:reporter, :product, 'OTHER', N'Private review note')
                    """
                ),
                {"reporter": reporter_id, "product": product_id},
            ).scalar_one()
            created_report_ids.append(report_id)

        def override_get_db():
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        moderator_one_headers = {
            "Cookie": f"access_token={create_access_token(moderator_one_id)}",
            "Origin": origin,
        }
        moderator_two_headers = {
            "Cookie": f"access_token={create_access_token(moderator_two_id)}",
            "Origin": origin,
        }

        with db6c_engine.begin() as setup:
            setup.execute(sa.text(f"IF OBJECT_ID(N'dbo.{trigger_name}', N'TR') IS NOT NULL DROP TRIGGER dbo.{trigger_name}"))
            setup.execute(
                sa.text(
                    f"""
                    CREATE TRIGGER dbo.{trigger_name}
                    ON dbo.MODERATION_ACTIONS
                    AFTER INSERT
                    AS
                    BEGIN
                        SET NOCOUNT ON;
                        THROW 51070, 'DB6C test-only forced audit failure.', 1;
                    END;
                    """
                )
            )

        with TestClient(
            app,
            base_url="https://testserver",
            headers={"Origin": origin},
            raise_server_exceptions=False,
        ) as client:
            failed_claim = client.post(
                f"/api/moderation/reports/{report_id}/claim",
                headers=moderator_one_headers,
            )
            assert failed_claim.status_code == 500

            with db6c_engine.connect() as check:
                state_after_failure = check.execute(
                    sa.text("SELECT status FROM dbo.PRODUCT_REPORTS WHERE report_id = :id"),
                    {"id": report_id},
                ).scalar_one()
                audit_count_after_failure = check.execute(
                    sa.text("SELECT COUNT(*) FROM dbo.MODERATION_ACTIONS WHERE report_id = :id"),
                    {"id": report_id},
                ).scalar_one()
            assert state_after_failure == "Submitted"
            assert audit_count_after_failure == 0

            with db6c_engine.begin() as cleanup_trigger:
                cleanup_trigger.execute(sa.text(f"DROP TRIGGER dbo.{trigger_name}"))

            # Start two independent requests together; a single report can have one winner.
            def claim(headers):
                with TestClient(app, base_url="https://testserver") as client:
                    return client.post(
                        f"/api/moderation/reports/{report_id}/claim",
                        headers=headers,
                    )

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(claim, [moderator_one_headers, moderator_two_headers]))
            assert sorted(response.status_code for response in results) == [200, 409]

            successful_user = (
                moderator_one_id
                if results[0].status_code == 200
                else moderator_two_id
            )
            detail_response = client.get(
                f"/api/moderation/reports/{report_id}",
                headers=moderator_one_headers
                if successful_user == moderator_one_id
                else moderator_two_headers,
            )
            assert detail_response.status_code == 200
            assert "reporter_user_id" not in detail_response.json()["data"]
            assert "reporter_email" not in detail_response.json()["data"]

            with db6c_engine.begin() as revoke:
                revoke.execute(
                    sa.text(
                        """
                        UPDATE dbo.USER_ROLE_ASSIGNMENTS
                        SET revoked_at = SYSUTCDATETIME(),
                            revoke_reason = N'Revoked by DB6C integration test'
                        WHERE user_id = :user_id
                          AND role_code = 'MODERATOR'
                          AND revoked_at IS NULL
                        """
                    ),
                    {"user_id": successful_user},
                )
            revoked_headers = (
                moderator_one_headers
                if successful_user == moderator_one_id
                else moderator_two_headers
            )
            assert client.get(
                "/api/moderation/reports",
                headers=revoked_headers,
            ).status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        with db6c_engine.begin() as cleanup:
            cleanup.execute(sa.text(f"IF OBJECT_ID(N'dbo.{trigger_name}', N'TR') IS NOT NULL DROP TRIGGER dbo.{trigger_name}"))
            if created_product_ids:
                cleanup.execute(
                    sa.text(
                        "DELETE FROM dbo.PRODUCT_MODERATION WHERE product_id IN :ids"
                    ).bindparams(sa.bindparam("ids", expanding=True)),
                    {"ids": created_product_ids},
                )
            if created_report_ids:
                cleanup.execute(
                    sa.text(
                        "DELETE FROM dbo.MODERATION_ACTIONS WHERE report_id IN :ids"
                    ).bindparams(sa.bindparam("ids", expanding=True)),
                    {"ids": created_report_ids},
                )
                cleanup.execute(
                    sa.text(
                        "DELETE FROM dbo.PRODUCT_REPORTS WHERE report_id IN :ids"
                    ).bindparams(sa.bindparam("ids", expanding=True)),
                    {"ids": created_report_ids},
                )
            if created_user_ids:
                cleanup.execute(
                    sa.text(
                        "DELETE FROM dbo.USER_ROLE_ASSIGNMENTS WHERE user_id IN :ids"
                    ).bindparams(sa.bindparam("ids", expanding=True)),
                    {"ids": created_user_ids},
                )
                cleanup.execute(
                    sa.text("DELETE FROM dbo.PRODUCTS WHERE product_id IN :ids").bindparams(
                        sa.bindparam("ids", expanding=True)
                    ),
                    {"ids": created_product_ids or [-1]},
                )
                cleanup.execute(
                    sa.text("DELETE FROM dbo.USERS WHERE user_id IN :ids").bindparams(
                        sa.bindparam("ids", expanding=True)
                    ),
                    {"ids": created_user_ids},
                )
            if category_ids:
                cleanup.execute(
                    sa.text("DELETE FROM dbo.CATEGORIES WHERE category_id IN :ids").bindparams(
                        sa.bindparam("ids", expanding=True)
                    ),
                    {"ids": category_ids},
                )
