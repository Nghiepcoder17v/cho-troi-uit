"""SQL Server-only DB-6D role-provisioning audit and concurrency tests."""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.sqlserver_integration


@pytest.fixture()
def db6d_engine():
    if os.getenv("RUN_SQLSERVER_INTEGRATION") != "1":
        pytest.skip("Set RUN_SQLSERVER_INTEGRATION=1 to enable SQL Server integration tests.")
    database_url = os.getenv("SQLSERVER_TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("RUN_SQLSERVER_INTEGRATION=1 but SQLSERVER_TEST_DATABASE_URL is missing.")
    if not (make_url(database_url).database or "").casefold().endswith("_test"):
        pytest.fail("Refusing to run DB-6D tests outside a database ending in '_test'.")
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


def _insert_user(connection: sa.Connection, label: str) -> int:
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
            "password_hash": "db6d-integration-test-hash",
            "full_name": f"DB6D {label}",
            "major": "Integration",
        },
    ).scalar_one()


def test_db6d_role_assignment_event_schema(db6d_engine):
    with db6d_engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENT_EVENTS', N'U')")
        ).scalar_one_or_none() is not None
        event_columns = {
            row.name for row in connection.execute(
                sa.text(
                    """
                    SELECT name FROM sys.columns
                    WHERE object_id = OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENT_EVENTS')
                    """
                )
            )
        }
        assert {
            "event_id",
            "assignment_id",
            "target_user_id",
            "role_code",
            "actor_user_id",
            "actor_role_code",
            "event_code",
            "reason",
            "occurred_at",
        } <= event_columns
        check_names = {
            row.name for row in connection.execute(
                sa.text(
                    """
                    SELECT name FROM sys.check_constraints
                    WHERE parent_object_id = OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENT_EVENTS')
                      AND is_disabled = 0 AND is_not_trusted = 0
                    """
                )
            )
        }
        assert {
            "CHK_UserRoleAssignmentEvents_EventCode",
            "CHK_UserRoleAssignmentEvents_Reason",
        } <= check_names


def test_db6d_admin_role_changes_audit_atomically_and_prevent_admin_lockout(db6d_engine):
    from database import get_db
    from main import app
    from security import create_access_token

    session_factory = sessionmaker(bind=db6d_engine, autoflush=False, autocommit=False)
    created_user_ids: list[int] = []
    created_assignment_ids: list[int] = []
    trigger_name = "TR_DB6D_RejectRoleEvent_Test"
    origin = "http://localhost:5173"
    app.dependency_overrides.pop(get_db, None)

    try:
        with db6d_engine.begin() as setup:
            admin_one_id = _insert_user(setup, "Admin One")
            admin_two_id = _insert_user(setup, "Admin Two")
            target_id = _insert_user(setup, "Role Target")
            created_user_ids.extend([admin_one_id, admin_two_id, target_id])
            assignments = setup.execute(
                sa.text(
                    """
                    INSERT INTO dbo.USER_ROLE_ASSIGNMENTS
                        (user_id, role_code, grant_reason)
                    OUTPUT INSERTED.assignment_id, INSERTED.user_id
                    VALUES
                        (:admin_one, 'ADMIN', N'DB6D integration fixture admin'),
                        (:admin_two, 'ADMIN', N'DB6D integration fixture admin')
                    """
                ),
                {"admin_one": admin_one_id, "admin_two": admin_two_id},
            ).all()
            admin_assignment_ids = {
                row.user_id: row.assignment_id for row in assignments
            }
            created_assignment_ids.extend(admin_assignment_ids.values())

        def override_get_db():
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        admin_one_headers = {
            "Cookie": f"access_token={create_access_token(admin_one_id)}",
            "Origin": origin,
        }
        admin_two_headers = {
            "Cookie": f"access_token={create_access_token(admin_two_id)}",
            "Origin": origin,
        }
        target_headers = {
            "Cookie": f"access_token={create_access_token(target_id)}",
            "Origin": origin,
        }

        with db6d_engine.begin() as setup:
            setup.exec_driver_sql(
                f"IF OBJECT_ID(N'dbo.{trigger_name}', N'TR') IS NOT NULL DROP TRIGGER dbo.{trigger_name}"
            )
            setup.exec_driver_sql(
                f"""
                CREATE TRIGGER dbo.{trigger_name}
                ON dbo.USER_ROLE_ASSIGNMENT_EVENTS
                AFTER INSERT
                AS
                BEGIN
                    SET NOCOUNT ON;
                    THROW 51080, 'DB6D test-only forced role audit failure.', 1;
                END;
                """
            )

        with TestClient(
            app,
            base_url="https://testserver",
            headers={"Origin": origin},
            raise_server_exceptions=False,
        ) as client:
            failed_grant = client.post(
                f"/api/admin/users/{target_id}/roles",
                headers=admin_one_headers,
                json={"role_code": "MODERATOR", "reason": "Approved moderator assignment"},
            )
            assert failed_grant.status_code == 500

            with db6d_engine.connect() as check:
                assignment_count = check.execute(
                    sa.text(
                        """
                        SELECT COUNT(*) FROM dbo.USER_ROLE_ASSIGNMENTS
                        WHERE user_id = :user_id AND role_code = 'MODERATOR'
                          AND revoked_at IS NULL
                        """
                    ),
                    {"user_id": target_id},
                ).scalar_one()
                event_count = check.execute(
                    sa.text(
                        """
                        SELECT COUNT(*) FROM dbo.USER_ROLE_ASSIGNMENT_EVENTS
                        WHERE target_user_id = :user_id
                        """
                    ),
                    {"user_id": target_id},
                ).scalar_one()
            assert assignment_count == 0
            assert event_count == 0

            with db6d_engine.begin() as drop_trigger:
                drop_trigger.exec_driver_sql(f"DROP TRIGGER dbo.{trigger_name}")

            grant = client.post(
                f"/api/admin/users/{target_id}/roles",
                headers=admin_one_headers,
                json={"role_code": "MODERATOR", "reason": "Approved moderator assignment"},
            )
            assert grant.status_code == 201, grant.text
            moderator_assignment_id = grant.json()["data"]["assignment_id"]
            created_assignment_ids.append(moderator_assignment_id)
            assert client.get(
                "/api/moderation/reports",
                headers=target_headers,
            ).status_code == 200

            self_grant = client.post(
                f"/api/admin/users/{admin_one_id}/roles",
                headers=admin_one_headers,
                json={"role_code": "ADMIN", "reason": "Attempted self grant"},
            )
            assert self_grant.status_code == 400
            self_revoke = client.post(
                f"/api/admin/role-assignments/{admin_assignment_ids[admin_one_id]}/revoke",
                headers=admin_one_headers,
                json={"reason": "Attempted self revoke"},
            )
            assert self_revoke.status_code == 400

            revoke = client.post(
                f"/api/admin/role-assignments/{moderator_assignment_id}/revoke",
                headers=admin_one_headers,
                json={"reason": "Moderator duty completed"},
            )
            assert revoke.status_code == 200, revoke.text
            assert client.get(
                "/api/moderation/reports",
                headers=target_headers,
            ).status_code == 403

            # Both admins issue a revocation at the same time against each other's
            # assignment. The ADMIN role-row lock serializes them; exactly one survives.
            def revoke_other(actor_headers, assignment_id):
                with TestClient(app, base_url="https://testserver") as concurrent_client:
                    return concurrent_client.post(
                        f"/api/admin/role-assignments/{assignment_id}/revoke",
                        headers=actor_headers,
                        json={"reason": "Concurrent administrator rotation"},
                    )

            with ThreadPoolExecutor(max_workers=2) as pool:
                race = list(
                    pool.map(
                        lambda args: revoke_other(*args),
                        [
                            (admin_one_headers, admin_assignment_ids[admin_two_id]),
                            (admin_two_headers, admin_assignment_ids[admin_one_id]),
                        ],
                    )
                )
            statuses = sorted(response.status_code for response in race)
            assert statuses == [200, 403], [(r.status_code, r.text) for r in race]

            with db6d_engine.connect() as check:
                active_admins = check.execute(
                    sa.text(
                        """
                        SELECT COUNT(*) FROM dbo.USER_ROLE_ASSIGNMENTS
                        WHERE role_code = 'ADMIN' AND revoked_at IS NULL
                        """
                    )
                ).scalar_one()
                target_events = check.execute(
                    sa.text(
                        """
                        SELECT event_code FROM dbo.USER_ROLE_ASSIGNMENT_EVENTS
                        WHERE target_user_id = :target AND role_code = 'MODERATOR'
                        ORDER BY event_id
                        """
                    ),
                    {"target": target_id},
                ).scalars().all()
            assert active_admins == 1
            assert list(target_events) == ["GRANTED", "REVOKED"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        with db6d_engine.begin() as cleanup:
            cleanup.exec_driver_sql(
                f"IF OBJECT_ID(N'dbo.{trigger_name}', N'TR') IS NOT NULL DROP TRIGGER dbo.{trigger_name}"
            )
            if created_user_ids:
                cleanup.execute(
                    sa.text(
                        "DELETE FROM dbo.USER_ROLE_ASSIGNMENT_EVENTS WHERE target_user_id IN :ids OR actor_user_id IN :ids"
                    ).bindparams(sa.bindparam("ids", expanding=True)),
                    {"ids": created_user_ids},
                )
                cleanup.execute(
                    sa.text(
                        "DELETE FROM dbo.USER_ROLE_ASSIGNMENTS WHERE user_id IN :ids OR granted_by_user_id IN :ids OR revoked_by_user_id IN :ids"
                    ).bindparams(sa.bindparam("ids", expanding=True)),
                    {"ids": created_user_ids},
                )
                cleanup.execute(
                    sa.text("DELETE FROM dbo.USERS WHERE user_id IN :ids").bindparams(
                        sa.bindparam("ids", expanding=True)
                    ),
                    {"ids": created_user_ids},
                )
