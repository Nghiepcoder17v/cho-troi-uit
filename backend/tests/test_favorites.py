from datetime import datetime

import models
from conftest import register_and_login


def _favorite(client, headers, product_id):
    return client.put(f"/api/users/me/favorites/{product_id}", headers=headers)


def _current_user_id(client, headers):
    response = client.get("/api/users/me", headers=headers)
    assert response.status_code == 200
    return response.json()["data"]["user_id"]


def test_favorites_require_authentication(client, product_id):
    assert client.get("/api/users/me/favorites").status_code == 401
    assert client.put(f"/api/users/me/favorites/{product_id}").status_code == 401
    assert client.delete(f"/api/users/me/favorites/{product_id}").status_code == 401


def test_add_favorite_is_idempotent_and_does_not_change_product_or_transaction(
    client, buyer_headers, product_id, session_factory
):
    buyer_id = _current_user_id(client, buyer_headers)
    assert _favorite(client, buyer_headers, product_id).status_code == 200

    original_created_at = datetime(2020, 1, 2, 3, 4, 5)
    with session_factory() as session:
        favorite = session.get(models.UserFavorite, (buyer_id, product_id))
        assert favorite is not None
        favorite.created_at = original_created_at
        product_status = session.get(models.Product, product_id).status
        session.commit()

    assert _favorite(client, buyer_headers, product_id).status_code == 200
    with session_factory() as session:
        favorite = session.get(models.UserFavorite, (buyer_id, product_id))
        product_after = session.get(models.Product, product_id)
        assert favorite.created_at == original_created_at
        assert product_after.status == product_status
        assert session.query(models.Transaction).count() == 0
        assert session.query(models.UserFavorite).count() == 1


def test_add_favorite_rejects_missing_or_hidden_product(
    client, buyer_headers, product_id, session_factory
):
    assert _favorite(client, buyer_headers, 99999999).status_code == 404
    with session_factory() as session:
        session.get(models.Product, product_id).status = "Hidden"
        session.commit()
    assert _favorite(client, buyer_headers, product_id).status_code == 404
    assert client.get("/api/users/me/favorites", headers=buyer_headers).json()["data"] == []


def test_existing_favorite_is_retained_but_hidden_product_is_redacted(
    client, buyer_headers, product_id, session_factory
):
    assert _favorite(client, buyer_headers, product_id).status_code == 200
    with session_factory() as session:
        session.get(models.Product, product_id).status = "Hidden"
        session.commit()

    response = client.get("/api/users/me/favorites", headers=buyer_headers)
    assert response.status_code == 200
    item = response.json()["data"][0]
    assert item["product_id"] == product_id
    assert item["status"] == "Hidden"
    assert item["product"] is None


def test_reserved_and_sold_products_can_be_favorited_and_return_current_status(
    client, buyer_headers, product_id, session_factory
):
    buyer_id = _current_user_id(client, buyer_headers)
    for status in ("Reserved", "Sold"):
        with session_factory() as session:
            session.get(models.Product, product_id).status = status
            session.commit()
        assert _favorite(client, buyer_headers, product_id).status_code == 200
        item = client.get("/api/users/me/favorites", headers=buyer_headers).json()["data"][0]
        assert item["status"] == status
        assert item["product"]["status"] == status
        with session_factory() as session:
            session.query(models.UserFavorite).filter_by(
                user_id=buyer_id, product_id=product_id
            ).delete()
            session.commit()


def test_delete_is_idempotent_and_only_removes_current_users_relation(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    buyer_id = _current_user_id(client, buyer_headers)
    seller_id = _current_user_id(client, seller_headers)
    assert _favorite(client, buyer_headers, product_id).status_code == 200
    assert _favorite(client, seller_headers, product_id).status_code == 200

    assert client.delete(f"/api/users/me/favorites/{product_id}", headers=buyer_headers).status_code == 204
    assert client.delete(f"/api/users/me/favorites/{product_id}", headers=buyer_headers).status_code == 204
    with session_factory() as session:
        assert session.get(models.UserFavorite, (buyer_id, product_id)) is None
        assert session.get(models.UserFavorite, (seller_id, product_id)) is not None


def test_favorite_list_is_private_and_uses_stable_pagination(
    client, buyer_headers, seller_headers, product_id, session_factory
):
    assert _favorite(client, buyer_headers, product_id).status_code == 200
    second_product = client.post(
        "/api/products",
        headers=seller_headers,
        json={"category_id": 1, "title": "Sản phẩm yêu thích thứ hai", "price": 47000, "condition": "Good"},
    ).json()["data"]["product_id"]
    assert _favorite(client, buyer_headers, second_product).status_code == 200

    buyer_id = _current_user_id(client, buyer_headers)
    fixed_time = datetime(2025, 5, 1, 12, 0, 0)
    with session_factory() as session:
        for product in (product_id, second_product):
            session.get(models.UserFavorite, (buyer_id, product)).created_at = fixed_time
        session.commit()

    page_one = client.get("/api/users/me/favorites?page=1&page_size=1", headers=buyer_headers)
    page_two = client.get("/api/users/me/favorites?page=2&page_size=1", headers=buyer_headers)
    assert page_one.status_code == page_two.status_code == 200
    assert page_one.json()["pagination"]["total_items"] == 2
    assert page_one.json()["data"][0]["product_id"] == max(product_id, second_product)
    assert page_two.json()["data"][0]["product_id"] == min(product_id, second_product)

    outsider_headers = register_and_login(client, "25520003")
    outsider = client.get("/api/users/me/favorites", headers=outsider_headers)
    seller = client.get("/api/users/me/favorites", headers=seller_headers)
    assert outsider.status_code == seller.status_code == 200
    assert outsider.json()["data"] == []
    assert seller.json()["data"] == []


def test_favorite_does_not_expose_private_account_fields(client, buyer_headers, product_id):
    assert _favorite(client, buyer_headers, product_id).status_code == 200
    item = client.get("/api/users/me/favorites", headers=buyer_headers).json()["data"][0]
    assert "email" not in item["product"]["seller"]
    assert "student_id" not in item["product"]["seller"]
    assert "description" not in item["product"]
