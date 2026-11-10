import models
from conftest import register_and_login


def buy(client, headers, product_id, amount=45000):
    return client.post(
        "/api/transactions",
        headers=headers,
        json={"product_id": product_id, "amount": amount},
    )


def complete(client, buyer_headers, seller_headers, product_id):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert client.post(
        f"/api/transactions/{transaction_id}/accept", headers=seller_headers
    ).status_code == 200
    assert client.post(
        f"/api/transactions/{transaction_id}/confirm-completion", headers=buyer_headers
    ).status_code == 200
    result = client.post(
        f"/api/transactions/{transaction_id}/confirm-completion", headers=seller_headers
    )
    assert result.status_code == 200 and result.json()["data"]["status"] == "Completed"
    return transaction_id


def test_buyer_and_seller_can_review_each_other_after_completed(
    client, buyer_headers, seller_headers, product_id
):
    transaction_id = complete(client, buyer_headers, seller_headers, product_id)

    buyer_review = client.post(
        f"/api/transactions/{transaction_id}/reviews",
        headers=buyer_headers,
        json={"rating": 5, "comment": "Giao dịch tốt, người bán nhiệt tình."},
    )
    seller_review = client.post(
        f"/api/transactions/{transaction_id}/reviews",
        headers=seller_headers,
        json={"rating": 4, "comment": "Người mua đúng hẹn."},
    )
    assert buyer_review.status_code == 201
    assert seller_review.status_code == 201

    seller_id = client.get("/api/users/me", headers=seller_headers).json()["data"]["user_id"]
    buyer_id = client.get("/api/users/me", headers=buyer_headers).json()["data"]["user_id"]
    seller_reviews = client.get(f"/api/users/{seller_id}/reviews")
    buyer_reviews = client.get(f"/api/users/{buyer_id}/reviews")
    assert seller_reviews.status_code == buyer_reviews.status_code == 200
    assert seller_reviews.json()["data"][0]["rating"] == 5
    assert seller_reviews.json()["data"][0]["reviewer"]["user_id"] == buyer_id
    assert buyer_reviews.json()["data"][0]["rating"] == 4
    assert buyer_reviews.json()["data"][0]["reviewer"]["user_id"] == seller_id

    purchases = client.get("/api/transactions/purchases", headers=buyer_headers).json()["data"]
    sales = client.get("/api/transactions/sales", headers=seller_headers).json()["data"]
    assert purchases[0]["transaction_id"] == transaction_id
    assert purchases[0]["my_review"]["rating"] == 5
    assert sales[0]["my_review"]["rating"] == 4


def test_outsider_cannot_review_completed_transaction(
    client, buyer_headers, seller_headers, product_id
):
    transaction_id = complete(client, buyer_headers, seller_headers, product_id)
    outsider = register_and_login(client, "25520003")
    response = client.post(
        f"/api/transactions/{transaction_id}/reviews",
        headers=outsider,
        json={"rating": 5},
    )
    assert response.status_code == 403


def test_review_is_blocked_before_completion_and_after_cancellation(
    client, buyer_headers, seller_headers, product_id
):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    pending = client.post(
        f"/api/transactions/{transaction_id}/reviews",
        headers=buyer_headers,
        json={"rating": 5},
    )
    assert pending.status_code == 409

    cancelled = client.post(
        f"/api/transactions/{transaction_id}/cancel", headers=buyer_headers
    )
    assert cancelled.status_code == 200
    after_cancel = client.post(
        f"/api/transactions/{transaction_id}/reviews",
        headers=buyer_headers,
        json={"rating": 5},
    )
    assert after_cancel.status_code == 409


def test_each_party_can_review_once_and_author_can_edit(
    client, buyer_headers, seller_headers, product_id
):
    transaction_id = complete(client, buyer_headers, seller_headers, product_id)
    created = client.post(
        f"/api/transactions/{transaction_id}/reviews",
        headers=buyer_headers,
        json={"rating": 3, "comment": "Ban đầu."},
    )
    assert created.status_code == 201
    review_id = created.json()["data"]["review_id"]

    duplicate = client.post(
        f"/api/transactions/{transaction_id}/reviews",
        headers=buyer_headers,
        json={"rating": 5},
    )
    assert duplicate.status_code == 409

    edited = client.patch(
        f"/api/reviews/{review_id}",
        headers=buyer_headers,
        json={"rating": 5, "comment": "Đã cập nhật."},
    )
    assert edited.status_code == 200
    assert edited.json()["data"]["rating"] == 5
    assert edited.json()["data"]["comment"] == "Đã cập nhật."

    forbidden = client.patch(
        f"/api/reviews/{review_id}",
        headers=seller_headers,
        json={"rating": 1},
    )
    assert forbidden.status_code == 403


def test_review_rating_and_comment_validation(
    client, buyer_headers, seller_headers, product_id
):
    transaction_id = complete(client, buyer_headers, seller_headers, product_id)
    for rating in (0, 6):
        response = client.post(
            f"/api/transactions/{transaction_id}/reviews",
            headers=buyer_headers,
            json={"rating": rating},
        )
        assert response.status_code == 422

    too_long = client.post(
        f"/api/transactions/{transaction_id}/reviews",
        headers=buyer_headers,
        json={"rating": 5, "comment": "x" * 1001},
    )
    assert too_long.status_code == 422


def test_historical_completed_transaction_without_confirmation_timestamps_is_eligible(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    buyer_id = client.get("/api/users/me", headers=buyer_headers).json()["data"]["user_id"]
    with session_factory() as session:
        product = session.get(models.Product, product_id)
        product.status = "Sold"
        transaction = models.Transaction(
            product_id=product_id,
            buyer_id=buyer_id,
            amount=45000,
            status="Completed",
            buyer_confirmed_at=None,
            seller_confirmed_at=None,
        )
        session.add(transaction)
        session.commit()
        transaction_id = transaction.transaction_id

    response = client.post(
        f"/api/transactions/{transaction_id}/reviews",
        headers=buyer_headers,
        json={"rating": 5, "comment": "Giao dịch cũ vẫn được đánh giá."},
    )
    assert response.status_code == 201


def test_reputation_uses_average_of_real_received_reviews(
    client, buyer_headers, seller_headers, product_id
):
    transaction_id = complete(client, buyer_headers, seller_headers, product_id)
    assert client.post(
        f"/api/transactions/{transaction_id}/reviews",
        headers=buyer_headers,
        json={"rating": 4},
    ).status_code == 201

    second_product = client.post(
        "/api/products",
        headers=seller_headers,
        json={"category_id": 1, "title": "Sản phẩm thứ hai", "price": 45000, "condition": "Good"},
    ).json()["data"]["product_id"]
    second_buyer = register_and_login(client, "25520004")
    second_transaction_id = complete(
        client, second_buyer, seller_headers, second_product
    )
    assert client.post(
        f"/api/transactions/{second_transaction_id}/reviews",
        headers=second_buyer,
        json={"rating": 5},
    ).status_code == 201

    seller_id = client.get("/api/users/me", headers=seller_headers).json()["data"]["user_id"]
    data = client.get(f"/api/users/{seller_id}/reputation").json()["data"]
    assert data["score"] == 4.5
    assert data["review_count"] == 2
    assert data["rating_distribution"] == {"1": 0, "2": 0, "3": 0, "4": 1, "5": 1}
    assert data["completed_sales"] == 2
    assert data["total_sales"] == 2
