import sqlalchemy as sa
from fastapi.testclient import TestClient

import models
from conftest import register_and_login
from main import app


def _user_id(client, headers):
    response = client.get("/api/users/me", headers=headers)
    assert response.status_code == 200
    return response.json()["data"]["user_id"]


def _assign_role(session_factory, user_id, role_code):
    with session_factory() as session:
        if session.get(models.Role, role_code) is None:
            session.add(models.Role(role_code=role_code, description=f"Test {role_code}"))
            session.flush()
        session.add(
            models.UserRoleAssignment(
                user_id=user_id,
                role_code=role_code,
                grant_reason="Approved test fixture role",
            )
        )
        session.commit()


def test_admin_role_endpoints_require_active_admin(client):
    user_headers = register_and_login(client, "25520031")
    admin_id = _user_id(client, user_headers)
    assert client.get("/api/admin/users", params={"q": "2552"}).status_code == 401
    assert client.get(
        "/api/admin/users", params={"q": "2552"}, headers=user_headers
    ).status_code == 403
    assert client.get("/api/admin/role-assignments", headers=user_headers).status_code == 403
    assert client.get("/api/admin/role-events", headers=user_headers).status_code == 403

    assert admin_id > 0


def test_admin_can_grant_revoke_and_review_role_history(
    client, session_factory
):
    admin_headers = register_and_login(client, "25520032")
    target_headers = register_and_login(client, "25520033")
    admin_id = _user_id(client, admin_headers)
    target_id = _user_id(client, target_headers)
    _assign_role(session_factory, admin_id, "ADMIN")

    search = client.get(
        "/api/admin/users",
        headers=admin_headers,
        params={"q": "25520033"},
    )
    assert search.status_code == 200, search.text
    assert search.json()["data"][0]["user_id"] == target_id
    assert "password_hash" not in search.json()["data"][0]

    self_grant = client.post(
        f"/api/admin/users/{admin_id}/roles",
        headers=admin_headers,
        json={"role_code": "ADMIN", "reason": "Attempted self grant"},
    )
    assert self_grant.status_code == 400

    grant = client.post(
        f"/api/admin/users/{target_id}/roles",
        headers=admin_headers,
        json={"role_code": "MODERATOR", "reason": "Approved moderation duty"},
    )
    assert grant.status_code == 201, grant.text
    assignment = grant.json()["data"]
    assert assignment["user"]["user_id"] == target_id
    assert assignment["role_code"] == "MODERATOR"
    assignment_id = assignment["assignment_id"]

    permissions = client.get("/api/users/me/permissions", headers=target_headers)
    assert permissions.status_code == 200
    assert permissions.json()["data"]["role_codes"] == ["MODERATOR"]
    assert client.get("/api/moderation/reports", headers=target_headers).status_code == 200

    duplicate = client.post(
        f"/api/admin/users/{target_id}/roles",
        headers=admin_headers,
        json={"role_code": "MODERATOR", "reason": "Duplicate assignment"},
    )
    assert duplicate.status_code == 409

    revoke = client.post(
        f"/api/admin/role-assignments/{assignment_id}/revoke",
        headers=admin_headers,
        json={"reason": "Moderator duty has ended"},
    )
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["data"]["revoked_at"] is not None
    assert client.get("/api/moderation/reports", headers=target_headers).status_code == 403
    assert client.get("/api/users/me/permissions", headers=target_headers).json()["data"]["role_codes"] == []

    admin_grant = client.post(
        f"/api/admin/users/{target_id}/roles",
        headers=admin_headers,
        json={"role_code": "ADMIN", "reason": "Approved admin responsibility"},
    )
    assert admin_grant.status_code == 201, admin_grant.text
    admin_assignment_id = admin_grant.json()["data"]["assignment_id"]
    assert client.get("/api/admin/role-events", headers=target_headers).status_code == 200
    assert client.post(
        f"/api/admin/role-assignments/{admin_assignment_id}/revoke",
        headers=target_headers,
        json={"reason": "Attempted self revoke"},
    ).status_code == 400

    admin_revoke = client.post(
        f"/api/admin/role-assignments/{admin_assignment_id}/revoke",
        headers=admin_headers,
        json={"reason": "Administrator assignment ended"},
    )
    assert admin_revoke.status_code == 200, admin_revoke.text
    assert client.get("/api/admin/role-events", headers=target_headers).status_code == 403

    assignments = client.get(
        "/api/admin/role-assignments",
        headers=admin_headers,
        params={"user_id": target_id, "include_revoked": "true"},
    )
    assert assignments.status_code == 200
    assert len(assignments.json()["data"]) == 1
    assert assignments.json()["data"][0]["revoke_reason"] == "Moderator duty has ended"

    events = client.get(
        "/api/admin/role-events",
        headers=admin_headers,
        params={"user_id": target_id},
    )
    assert events.status_code == 200
    assert [event["event_code"] for event in reversed(events.json()["data"])] == [
        "GRANTED",
        "REVOKED",
        "GRANTED",
        "REVOKED",
    ]
    assert all(event["actor_role_code"] == "ADMIN" for event in events.json()["data"])


def test_admin_cannot_change_own_assignment_or_revoke_last_admin(client, session_factory):
    admin_headers = register_and_login(client, "25520034")
    admin_id = _user_id(client, admin_headers)
    _assign_role(session_factory, admin_id, "ADMIN")

    assignments = client.get(
        "/api/admin/role-assignments",
        headers=admin_headers,
        params={"user_id": admin_id},
    )
    assignment_id = assignments.json()["data"][0]["assignment_id"]

    self_revoke = client.post(
        f"/api/admin/role-assignments/{assignment_id}/revoke",
        headers=admin_headers,
        json={"reason": "Attempted self revoke"},
    )
    assert self_revoke.status_code == 400

    # The external first-admin bootstrap remains operational-only. The admin UI
    # cannot revoke its own last ADMIN assignment.
    assert client.get("/api/admin/role-assignments", headers=admin_headers).status_code == 200


def test_role_grant_and_audit_event_commit_atomically_on_sqlite(
    client, session_factory
):
    admin_headers = register_and_login(client, "25520035")
    target_headers = register_and_login(client, "25520036")
    admin_id = _user_id(client, admin_headers)
    target_id = _user_id(client, target_headers)
    _assign_role(session_factory, admin_id, "ADMIN")

    with session_factory() as session:
        session.execute(
            sa.text(
                """
                CREATE TRIGGER fail_db6d_role_event
                BEFORE INSERT ON user_role_assignment_events
                BEGIN
                    SELECT RAISE(ABORT, 'DB6D injected audit failure');
                END
                """
            )
        )
        session.commit()

    try:
        with TestClient(
            app,
            base_url="https://testserver",
            raise_server_exceptions=False,
        ) as isolated_client:
            response = isolated_client.post(
                f"/api/admin/users/{target_id}/roles",
                headers=admin_headers,
                json={"role_code": "MODERATOR", "reason": "Approved moderation duty"},
            )
        assert response.status_code == 500
        with session_factory() as session:
            assignment_count = session.query(models.UserRoleAssignment).filter_by(
                user_id=target_id, role_code="MODERATOR"
            ).count()
            event_count = session.query(models.UserRoleAssignmentEvent).filter_by(
                target_user_id=target_id
            ).count()
        assert assignment_count == 0
        assert event_count == 0
    finally:
        with session_factory() as session:
            session.execute(sa.text("DROP TRIGGER IF EXISTS fail_db6d_role_event"))
            session.commit()
