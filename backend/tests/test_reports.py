from datetime import timedelta

import models
from conftest import register_and_login


def _submit_report(client, headers, product_id, reason_code="OTHER", description=None):
    return client.post(
        "/api/reports",
        headers=headers,
        json={
            "target_product_id": product_id,
            "reason_code": reason_code,
            "description": description,
        },
    )


def _create_product(client, seller_headers, title):
    response = client.post(
        "/api/products",
        headers=seller_headers,
        json={
            "category_id": 1,
            "title": title,
            "price": 50000,
            "condition": "Good",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["product_id"]


def test_product_reports_require_authentication(client, product_id):
    response = client.post(
        "/api/reports",
        json={"target_product_id": product_id, "reason_code": "OTHER"},
    )
    assert response.status_code == 401


def test_product_report_validates_reason_description_and_forbids_authority_fields(
    client, buyer_headers, product_id
):
    assert _submit_report(
        client, buyer_headers, product_id, reason_code="MADE_UP"
    ).status_code == 422
    assert _submit_report(
        client, buyer_headers, product_id, description="x" * 501
    ).status_code == 422

    response = client.post(
        "/api/reports",
        headers=buyer_headers,
        json={
            "target_product_id": product_id,
            "reason_code": "OTHER",
            "reporter_user_id": 999999,
            "status": "Actioned",
        },
    )
    assert response.status_code == 422


def test_product_report_receipt_is_private_and_submission_does_not_change_listing(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    buyer_id = client.get("/api/users/me", headers=buyer_headers).json()["data"]["user_id"]
    response = _submit_report(
        client,
        buyer_headers,
        product_id,
        reason_code="MISLEADING_LISTING",
        description="  Mô tả và hình ảnh không khớp.  ",
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["data"]["target_product_id"] == product_id
    assert body["data"]["reason_code"] == "MISLEADING_LISTING"
    assert body["data"]["status"] == "Submitted"
    assert "reporter_user_id" not in body["data"]
    assert "description" not in body["data"]

    with session_factory() as session:
        report = session.get(models.ProductReport, body["data"]["report_id"])
        assert report is not None
        assert report.reporter_user_id == buyer_id
        assert report.description == "Mô tả và hình ảnh không khớp."
        assert session.get(models.Product, product_id).status == "Available"

    assert _submit_report(client, seller_headers, product_id).status_code == 400

    outsider_headers = register_and_login(client, "25520003")
    outsider = _submit_report(client, outsider_headers, product_id)
    assert outsider.status_code == 201, outsider.text

    duplicate = _submit_report(client, buyer_headers, product_id)
    assert duplicate.status_code == 409


def test_product_report_accepts_sold_but_rejects_hidden_reserved_and_missing_targets(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    with session_factory() as session:
        session.get(models.Product, product_id).status = "Sold"
        session.commit()
    sold_response = _submit_report(client, buyer_headers, product_id)
    assert sold_response.status_code == 201, sold_response.text

    hidden_id = _create_product(client, seller_headers, "Tin ẩn")
    with session_factory() as session:
        session.get(models.Product, hidden_id).status = "Hidden"
        session.commit()
    assert _submit_report(client, buyer_headers, hidden_id).status_code == 404

    reserved_id = _create_product(client, seller_headers, "Tin đang giữ chỗ")
    with session_factory() as session:
        session.get(models.Product, reserved_id).status = "Reserved"
        session.commit()
    assert _submit_report(client, buyer_headers, reserved_id).status_code == 404
    assert _submit_report(client, buyer_headers, 99999999).status_code == 404


def test_product_report_limit_is_five_per_rolling_24_hours(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    product_ids = [product_id]
    product_ids.extend(
        _create_product(client, seller_headers, f"Tin báo cáo giới hạn {index}")
        for index in range(1, 6)
    )

    for reportable_id in product_ids[:5]:
        response = _submit_report(client, buyer_headers, reportable_id)
        assert response.status_code == 201, response.text

    limited = _submit_report(client, buyer_headers, product_ids[5])
    assert limited.status_code == 429

    with session_factory() as session:
        first_report = (
            session.query(models.ProductReport)
            .filter_by(target_product_id=product_ids[0])
            .one()
        )
        first_report.submitted_at = models.utcnow() - timedelta(hours=24, seconds=1)
        session.commit()

    after_window = _submit_report(client, buyer_headers, product_ids[5])
    assert after_window.status_code == 201, after_window.text
