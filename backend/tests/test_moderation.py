import models
from conftest import register_and_login


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
                grant_reason="Automated test fixture",
            )
        )
        session.commit()


def _report(client, headers, product_id):
    response = client.post(
        "/api/reports",
        headers=headers,
        json={
            "target_product_id": product_id,
            "reason_code": "MISLEADING_LISTING",
            "description": "Thông tin sản phẩm cần được kiểm tra.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["report_id"]


def test_moderator_routes_require_fresh_database_role(client, buyer_headers, session_factory):
    moderator_headers = register_and_login(client, "25520011")
    moderator_id = _user_id(client, moderator_headers)
    assert client.get("/api/moderation/reports").status_code == 401
    assert client.get("/api/moderation/reports", headers=buyer_headers).status_code == 403

    _assign_role(session_factory, moderator_id, "MODERATOR")
    assert client.get("/api/moderation/reports", headers=moderator_headers).status_code == 200

    with session_factory() as session:
        assignment = session.query(models.UserRoleAssignment).filter_by(
            user_id=moderator_id, role_code="MODERATOR", revoked_at=None
        ).one()
        assignment.revoked_at = models.utcnow()
        assignment.revoke_reason = "Revoked during test"
        session.commit()

    # Role revocation is checked against SQL for each protected request.
    assert client.get("/api/moderation/reports", headers=moderator_headers).status_code == 403


def test_claim_escalation_and_admin_review_are_audited(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    moderator_headers = register_and_login(client, "25520012")
    admin_headers = register_and_login(client, "25520013")
    _assign_role(session_factory, _user_id(client, moderator_headers), "MODERATOR")
    _assign_role(session_factory, _user_id(client, admin_headers), "ADMIN")
    report_id = _report(client, buyer_headers, product_id)

    queue = client.get("/api/moderation/reports", headers=moderator_headers)
    assert queue.status_code == 200
    queue_item = next(item for item in queue.json()["data"] if item["report_id"] == report_id)
    assert queue_item["status"] == "Submitted"
    assert "reporter_user_id" not in queue_item
    assert "reporter_email" not in queue_item
    assert queue_item["description"] == "Thông tin sản phẩm cần được kiểm tra."

    claimed = client.post(
        f"/api/moderation/reports/{report_id}/claim",
        headers=moderator_headers,
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["data"]["status"] == "InReview"

    escalated = client.post(
        f"/api/moderation/reports/{report_id}/decision",
        headers=moderator_headers,
        json={
            "decision": "Escalated",
            "resolution_code": "NEEDS_ADMIN_REVIEW",
            "internal_note": "Cần cấp quản trị xem xét độc lập.",
        },
    )
    assert escalated.status_code == 200, escalated.text
    assert escalated.json()["data"]["status"] == "Escalated"
    assert escalated.json()["data"]["assigned_moderator_user_id"] is None

    forbidden_claim = client.post(
        f"/api/moderation/reports/{report_id}/claim",
        headers=moderator_headers,
    )
    assert forbidden_claim.status_code == 403

    admin_claim = client.post(
        f"/api/moderation/reports/{report_id}/claim",
        headers=admin_headers,
    )
    assert admin_claim.status_code == 200, admin_claim.text
    assert admin_claim.json()["data"]["status"] == "InReview"

    dismissed = client.post(
        f"/api/moderation/reports/{report_id}/decision",
        headers=admin_headers,
        json={
            "decision": "Dismissed",
            "resolution_code": "INSUFFICIENT_EVIDENCE",
            "internal_note": "Không đủ căn cứ để xử lý tin đăng.",
        },
    )
    assert dismissed.status_code == 200, dismissed.text
    detail = client.get(
        f"/api/moderation/reports/{report_id}",
        headers=admin_headers,
    )
    assert detail.status_code == 200
    assert [event["action_code"] for event in detail.json()["data"]["actions"]] == [
        "CLAIMED",
        "ESCALATED",
        "CLAIMED",
        "DISMISSED",
    ]
    assert "reporter_user_id" not in detail.json()["data"]


def test_action_places_independent_hold_until_explicit_release(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    moderator_headers = register_and_login(client, "25520014")
    moderator_id = _user_id(client, moderator_headers)
    _assign_role(session_factory, moderator_id, "MODERATOR")
    report_id = _report(client, buyer_headers, product_id)

    assert client.put(
        f"/api/users/me/favorites/{product_id}", headers=buyer_headers
    ).status_code == 200

    assert client.post(
        f"/api/moderation/reports/{report_id}/claim", headers=moderator_headers
    ).status_code == 200
    actioned = client.post(
        f"/api/moderation/reports/{report_id}/decision",
        headers=moderator_headers,
        json={
            "decision": "Actioned",
            "resolution_code": "TEMPORARY_LISTING_HOLD",
            "internal_note": "Tạm ẩn công khai trong khi xử lý theo chính sách.",
        },
    )
    assert actioned.status_code == 200, actioned.text
    assert actioned.json()["data"]["status"] == "Actioned"

    assert client.get(f"/api/products/{product_id}").status_code == 404
    public_products = client.get("/api/products")
    assert product_id not in {row["product_id"] for row in public_products.json()["data"]}
    public_seller_products = client.get(
        f"/api/users/{_user_id(client, seller_headers)}/products"
    )
    assert product_id not in {
        row["product_id"] for row in public_seller_products.json()["data"]
    }
    seller_products = client.get("/api/products/mine", headers=seller_headers)
    mine = next(row for row in seller_products.json()["data"] if row["product_id"] == product_id)
    assert mine["moderation_status"] == "Held"
    assert client.patch(
        f"/api/products/{product_id}",
        headers=seller_headers,
        json={"status": "Available"},
    ).status_code == 409
    assert client.post(
        "/api/transactions",
        headers=buyer_headers,
        json={"product_id": product_id, "amount": 40000},
    ).status_code == 404

    favorites = client.get("/api/users/me/favorites", headers=buyer_headers)
    saved = next(row for row in favorites.json()["data"] if row["product_id"] == product_id)
    assert saved["status"] == "Hidden"
    assert saved["product"] is None

    released = client.post(
        f"/api/moderation/products/{product_id}/release-hold",
        headers=moderator_headers,
        json={"internal_note": "Đã hoàn tất kiểm tra; cho phép hiển thị lại."},
    )
    assert released.status_code == 200, released.text
    assert client.get(f"/api/products/{product_id}").status_code == 200
    with session_factory() as session:
        hold = session.get(models.ProductModeration, product_id)
        assert hold is not None and not hold.is_held
        events = session.query(models.ModerationAction).filter_by(report_id=report_id).all()
        assert [event.action_code for event in events] == [
            "CLAIMED",
            "ACTIONED",
            "HOLD_PLACED",
            "HOLD_RELEASED",
        ]


def test_actioned_hold_does_not_cancel_an_existing_reserved_transaction(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    moderator_headers = register_and_login(client, "25520015")
    _assign_role(session_factory, _user_id(client, moderator_headers), "MODERATOR")
    report_id = _report(client, buyer_headers, product_id)

    transaction = client.post(
        "/api/transactions",
        headers=seller_headers if False else buyer_headers,
        json={"product_id": product_id, "amount": 40000},
    )
    assert transaction.status_code == 201, transaction.text
    transaction_id = transaction.json()["data"]["transaction_id"]

    assert client.post(
        f"/api/moderation/reports/{report_id}/claim", headers=moderator_headers
    ).status_code == 200
    response = client.post(
        f"/api/moderation/reports/{report_id}/decision",
        headers=moderator_headers,
        json={
            "decision": "Actioned",
            "resolution_code": "TEMPORARY_LISTING_HOLD",
            "internal_note": "Giữ ẩn tin đăng; không tác động giao dịch đã phát sinh.",
        },
    )
    assert response.status_code == 200, response.text
    with session_factory() as session:
        assert session.get(models.Product, product_id).status == "Reserved"
        assert session.get(models.Transaction, transaction_id).status == "Pending"
