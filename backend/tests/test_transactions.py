import models


def buy(client, headers, product_id, amount=45000):
    return client.post("/api/transactions", headers=headers, json={"product_id": product_id, "amount": amount})


def test_buy_requires_auth(client, product_id):
    assert client.post("/api/transactions", json={"product_id": product_id, "amount": 1}).status_code == 401


def test_buy_success_marks_sold_and_records_buyer(client, buyer_headers, product_id, session_factory):
    r = buy(client, buyer_headers, product_id, amount=40000)
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["status"] == "Completed" and data["amount"] == 40000

    me = client.get("/api/users/me", headers=buyer_headers).json()["data"]
    with session_factory() as s:
        product = s.get(models.Product, product_id)
        tx = s.get(models.Transaction, data["transaction_id"])
        assert product.status == "Sold"
        assert tx.buyer_id == me["user_id"]
        assert product.updated_at >= product.created_at


def test_second_buyer_cannot_buy_same_product(client, buyer_headers, product_id, session_factory):
    from conftest import register_and_login

    other = register_and_login(client, "25520003")
    assert buy(client, buyer_headers, product_id).status_code == 201
    assert buy(client, other, product_id).status_code == 409
    with session_factory() as s:
        assert s.query(models.Transaction).filter_by(product_id=product_id).count() == 1


def test_seller_cannot_buy_own_product(client, seller_headers, product_id):
    assert buy(client, seller_headers, product_id).status_code == 400


def test_amount_cannot_exceed_listed_price(client, buyer_headers, product_id):
    assert buy(client, buyer_headers, product_id, amount=45001).status_code == 400


def test_negative_amount_rejected(client, buyer_headers, product_id):
    assert buy(client, buyer_headers, product_id, amount=-5).status_code == 422


def test_unknown_product_404(client, buyer_headers):
    assert buy(client, buyer_headers, 99999).status_code == 404


def test_failed_purchase_leaves_product_available(client, buyer_headers, seller_headers, product_id, session_factory):
    buy(client, seller_headers, product_id)  # bị từ chối (tự mua)
    buy(client, buyer_headers, product_id, amount=10**7)  # bị từ chối (quá giá)
    with session_factory() as s:
        assert s.get(models.Product, product_id).status == "Available"
