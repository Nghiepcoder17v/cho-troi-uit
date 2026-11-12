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


def _transaction_events(session_factory, transaction_id):
    with session_factory() as session:
        return (
            session.query(models.TransactionEvent)
            .filter_by(transaction_id=transaction_id)
            .order_by(models.TransactionEvent.occurred_at, models.TransactionEvent.event_id)
            .all()
        )


def test_request_creation_writes_one_event_atomically(client, buyer_headers, product_id, session_factory):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    events = _transaction_events(session_factory, transaction_id)
    assert len(events) == 1
    assert events[0].event_type == "REQUEST_CREATED"
    assert events[0].actor_user_id is not None
    assert events[0].from_status is None
    assert events[0].to_status == "Pending"


def test_accept_and_reject_write_actor_specific_events(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    accepted_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert accept(client, seller_headers, accepted_id).status_code == 200
    accepted_events = _transaction_events(session_factory, accepted_id)
    assert [event.event_type for event in accepted_events] == ["REQUEST_CREATED", "SELLER_ACCEPTED"]
    assert (accepted_events[-1].from_status, accepted_events[-1].to_status) == ("Pending", "Accepted")

    # The first request is still active, so use a separate product for the rejection path.
    second_product = client.post(
        "/api/products",
        headers=seller_headers,
        json={"category_id": 1, "title": "Sản phẩm từ chối", "price": 45000, "condition": "Good"},
    ).json()["data"]["product_id"]
    rejected_id = buy(client, buyer_headers, second_product).json()["data"]["transaction_id"]
    assert client.post(f"/api/transactions/{rejected_id}/reject", headers=seller_headers).status_code == 200
    rejected_events = _transaction_events(session_factory, rejected_id)
    assert [event.event_type for event in rejected_events] == ["REQUEST_CREATED", "SELLER_REJECTED"]
    assert (rejected_events[-1].from_status, rejected_events[-1].to_status) == ("Pending", "Cancelled")


def test_buyer_and_seller_cancellations_have_distinct_event_codes(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    buyer_cancelled_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert client.post(
        f"/api/transactions/{buyer_cancelled_id}/cancel", headers=buyer_headers
    ).status_code == 200

    other_product = client.post(
        "/api/products",
        headers=seller_headers,
        json={"category_id": 1, "title": "Sản phẩm hủy bởi người bán", "price": 45000, "condition": "Good"},
    ).json()["data"]["product_id"]
    seller_cancelled_id = buy(client, buyer_headers, other_product).json()["data"]["transaction_id"]
    assert client.post(
        f"/api/transactions/{seller_cancelled_id}/cancel", headers=seller_headers
    ).status_code == 200

    assert [event.event_type for event in _transaction_events(session_factory, buyer_cancelled_id)] == [
        "REQUEST_CREATED", "BUYER_CANCELLED"
    ]
    assert [event.event_type for event in _transaction_events(session_factory, seller_cancelled_id)] == [
        "REQUEST_CREATED", "SELLER_CANCELLED"
    ]


def test_two_party_confirmation_writes_one_completion_marker(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert accept(client, seller_headers, transaction_id).status_code == 200
    assert confirm(client, buyer_headers, transaction_id).status_code == 200
    assert confirm(client, seller_headers, transaction_id).status_code == 200

    events = _transaction_events(session_factory, transaction_id)
    assert [event.event_type for event in events] == [
        "REQUEST_CREATED", "SELLER_ACCEPTED", "BUYER_CONFIRMED",
        "SELLER_CONFIRMED", "TRANSACTION_COMPLETED",
    ]
    assert (events[2].from_status, events[2].to_status) == ("Accepted", "Accepted")
    assert (events[3].from_status, events[3].to_status) == ("Accepted", "Completed")
    assert events[4].actor_user_id is None
    assert (events[4].from_status, events[4].to_status) == ("Completed", "Completed")


def test_cancellation_keeps_prior_confirmation_event_and_does_not_complete(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert accept(client, seller_headers, transaction_id).status_code == 200
    assert confirm(client, buyer_headers, transaction_id).status_code == 200
    assert client.post(f"/api/transactions/{transaction_id}/cancel", headers=seller_headers).status_code == 200

    events = _transaction_events(session_factory, transaction_id)
    assert [event.event_type for event in events] == [
        "REQUEST_CREATED", "SELLER_ACCEPTED", "BUYER_CONFIRMED", "SELLER_CANCELLED"
    ]
    assert (events[-1].from_status, events[-1].to_status) == ("Accepted", "Cancelled")
    assert not any(event.event_type == "TRANSACTION_COMPLETED" for event in events)


def test_failed_product_release_rolls_back_transaction_event_and_status(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    with session_factory() as session:
        product = session.get(models.Product, product_id)
        product.status = "Sold"
        session.commit()

    response = client.post(f"/api/transactions/{transaction_id}/reject", headers=seller_headers)
    assert response.status_code == 409
    with session_factory() as session:
        transaction = session.get(models.Transaction, transaction_id)
        assert transaction.status == "Pending"
    assert [event.event_type for event in _transaction_events(session_factory, transaction_id)] == [
        "REQUEST_CREATED"
    ]


def test_failed_completion_does_not_commit_confirmation_event(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert accept(client, seller_headers, transaction_id).status_code == 200
    assert confirm(client, buyer_headers, transaction_id).status_code == 200
    with session_factory() as session:
        product = session.get(models.Product, product_id)
        product.status = "Available"
        session.commit()

    response = confirm(client, seller_headers, transaction_id)
    assert response.status_code == 409
    with session_factory() as session:
        transaction = session.get(models.Transaction, transaction_id)
        assert transaction.status == "Accepted"
        assert transaction.seller_confirmed_at is None
    assert [event.event_type for event in _transaction_events(session_factory, transaction_id)] == [
        "REQUEST_CREATED", "SELLER_ACCEPTED", "BUYER_CONFIRMED"
    ]


def test_history_includes_events_and_system_actor_is_null(
    client, buyer_headers, seller_headers, product_id
):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    assert accept(client, seller_headers, transaction_id).status_code == 200
    assert confirm(client, buyer_headers, transaction_id).status_code == 200
    assert confirm(client, seller_headers, transaction_id).status_code == 200

    buyer_history = client.get("/api/transactions/purchases", headers=buyer_headers).json()["data"]
    seller_history = client.get("/api/transactions/sales", headers=seller_headers).json()["data"]
    assert buyer_history[0]["transaction_id"] == transaction_id
    assert seller_history[0]["transaction_id"] == transaction_id
    assert [event["event_type"] for event in buyer_history[0]["events"]] == [
        "REQUEST_CREATED", "SELLER_ACCEPTED", "BUYER_CONFIRMED",
        "SELLER_CONFIRMED", "TRANSACTION_COMPLETED",
    ]
    assert buyer_history[0]["events"][-1]["actor"] is None
    assert buyer_history[0]["events"][2]["actor"]["full_name"] == "Sinh viên 25520002"


def test_legacy_history_without_events_returns_empty_array(
    client, buyer_headers, product_id, session_factory
):
    transaction_id = buy(client, buyer_headers, product_id).json()["data"]["transaction_id"]
    with session_factory() as session:
        session.query(models.TransactionEvent).filter_by(transaction_id=transaction_id).delete()
        session.commit()

    response = client.get("/api/transactions/purchases", headers=buyer_headers)
    assert response.status_code == 200
    assert response.json()["data"][0]["events"] == []


def test_non_participant_cannot_read_another_transactions_events(
    client, buyer_headers, product_id
):
    from conftest import register_and_login

    buy(client, buyer_headers, product_id)
    outsider_headers = register_and_login(client, "25520003")
    # No public event-by-id route exists; purchase history stays scoped to the caller.
    outsider_history = client.get("/api/transactions/purchases", headers=outsider_headers)
    seller_history = client.get("/api/transactions/sales", headers=outsider_headers)
    assert outsider_history.status_code == 200 and outsider_history.json()["data"] == []
    assert seller_history.status_code == 200 and seller_history.json()["data"] == []
