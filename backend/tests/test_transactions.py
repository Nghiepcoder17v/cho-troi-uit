import models


def buy(client, headers, product_id, amount=45000):
    return client.post("/api/transactions", headers=headers, json={"product_id": product_id, "amount": amount})


def accept(client, headers, transaction_id):
    return client.post(f"/api/transactions/{transaction_id}/accept", headers=headers)


def confirm(client, headers, transaction_id):
    return client.post(f"/api/transactions/{transaction_id}/confirm-completion", headers=headers)


def test_buy_requires_auth(client, product_id):
    assert buy(client, {}, product_id).status_code == 401


def test_request_reserves_product_and_starts_pending(client, buyer_headers, product_id, session_factory):
    response = buy(client, buyer_headers, product_id, amount=40000)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "Pending" and data["amount"] == 40000
    with session_factory() as session:
        assert session.get(models.Product, product_id).status == "Reserved"
        assert session.get(models.Transaction, data["transaction_id"]).status == "Pending"


def test_only_one_buyer_can_reserve_product(client, buyer_headers, product_id, session_factory):
    from conftest import register_and_login

    other = register_and_login(client, "25520003")
    assert buy(client, buyer_headers, product_id).status_code == 201
    assert buy(client, other, product_id).status_code == 409
    with session_factory() as session:
        assert session.query(models.Transaction).filter_by(product_id=product_id).count() == 1


def test_seller_cannot_buy_own_product(client, seller_headers, product_id):
    assert buy(client, seller_headers, product_id).status_code == 400


def test_amount_cannot_exceed_listed_price(client, buyer_headers, product_id):
    assert buy(client, buyer_headers, product_id, amount=45001).status_code == 400


def test_negative_amount_rejected(client, buyer_headers, product_id):
    assert buy(client, buyer_headers, product_id, amount=-5).status_code == 422


def test_unknown_product_404(client, buyer_headers):
    assert buy(client, buyer_headers, 99999).status_code == 404


def test_seller_accepts_pending_request(client, buyer_headers, seller_headers, product_id):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    response = accept(client, seller_headers, transaction_id)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "Accepted"


def test_only_seller_can_accept_or_reject(client, buyer_headers, seller_headers, product_id):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert accept(client, buyer_headers, transaction_id).status_code == 403
    response = client.post(f"/api/transactions/{transaction_id}/reject", headers=seller_headers)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "Cancelled"


def test_rejection_releases_product_for_another_buyer(client, buyer_headers, seller_headers, product_id, session_factory):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    response = client.post(f"/api/transactions/{transaction_id}/reject", headers=seller_headers)
    assert response.status_code == 200
    with session_factory() as session:
        assert session.get(models.Product, product_id).status == "Available"

    from conftest import register_and_login
    other = register_and_login(client, "25520003")
    assert buy(client, other, product_id).status_code == 201


def test_cannot_reject_after_acceptance(client, buyer_headers, seller_headers, product_id):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert accept(client, seller_headers, transaction_id).status_code == 200
    assert client.post(f"/api/transactions/{transaction_id}/reject", headers=seller_headers).status_code == 409


def test_participant_can_cancel_pending_request(client, buyer_headers, product_id, session_factory):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    response = client.post(f"/api/transactions/{transaction_id}/cancel", headers=buyer_headers)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "Cancelled"
    with session_factory() as session:
        assert session.get(models.Product, product_id).status == "Available"


def test_cancellation_after_one_confirmation_voids_that_confirmation(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert accept(client, seller_headers, transaction_id).status_code == 200
    first = confirm(client, buyer_headers, transaction_id)
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "Accepted"

    cancelled = client.post(f"/api/transactions/{transaction_id}/cancel", headers=seller_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "Cancelled"
    assert cancelled.json()["data"]["buyer_confirmed_at"] is None
    assert cancelled.json()["data"]["seller_confirmed_at"] is None
    with session_factory() as session:
        assert session.get(models.Product, product_id).status == "Available"


def test_both_parties_must_confirm_before_completed_and_sold(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert accept(client, seller_headers, transaction_id).status_code == 200

    buyer_confirmation = confirm(client, buyer_headers, transaction_id)
    assert buyer_confirmation.status_code == 200
    assert buyer_confirmation.json()["data"]["status"] == "Accepted"
    assert buyer_confirmation.json()["data"]["buyer_confirmed_at"] is not None
    assert buyer_confirmation.json()["data"]["seller_confirmed_at"] is None

    seller_confirmation = confirm(client, seller_headers, transaction_id)
    assert seller_confirmation.status_code == 200
    assert seller_confirmation.json()["data"]["status"] == "Completed"
    assert seller_confirmation.json()["data"]["buyer_confirmed_at"] is not None
    assert seller_confirmation.json()["data"]["seller_confirmed_at"] is not None
    with session_factory() as session:
        assert session.get(models.Product, product_id).status == "Sold"


def test_same_party_cannot_confirm_for_the_other_party(client, buyer_headers, seller_headers, product_id):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert accept(client, seller_headers, transaction_id).status_code == 200
    assert confirm(client, buyer_headers, transaction_id).status_code == 200
    assert confirm(client, buyer_headers, transaction_id).status_code == 409


def test_non_participant_cannot_cancel_or_confirm(client, buyer_headers, product_id):
    from conftest import register_and_login

    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    outsider = register_and_login(client, "25520003")
    assert client.post(f"/api/transactions/{transaction_id}/cancel", headers=outsider).status_code == 403
    assert client.post(f"/api/transactions/{transaction_id}/confirm-completion", headers=outsider).status_code == 403


def test_purchase_and_sales_history_include_both_parties_and_confirmation_flags(
    client, buyer_headers, seller_headers, product_id
):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    purchases = client.get("/api/transactions/purchases", headers=buyer_headers)
    sales = client.get("/api/transactions/sales", headers=seller_headers)
    assert purchases.status_code == 200 and sales.status_code == 200
    assert purchases.json()["data"][0]["transaction_id"] == transaction_id
    assert sales.json()["data"][0]["transaction_id"] == transaction_id
    assert purchases.json()["data"][0]["buyer"]["user_id"] != purchases.json()["data"][0]["seller"]["user_id"]
    assert "buyer_confirmed_at" in purchases.json()["data"][0]
    assert "seller_confirmed_at" in sales.json()["data"][0]


def test_transaction_history_requires_auth(client):
    assert client.get("/api/transactions/purchases").status_code == 401
    assert client.get("/api/transactions/sales").status_code == 401
