from conftest import register_and_login
import models


def test_update_own_profile_and_keep_private_identifiers_unchanged(client):
    headers = register_and_login(client, "25520101")
    response = client.patch(
        "/api/users/me",
        headers=headers,
        json={"full_name": "  Nguyễn Minh  ", "major": "  Kỹ thuật phần mềm  "},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["full_name"] == "Nguyễn Minh"
    assert data["major"] == "Kỹ thuật phần mềm"
    assert data["email"] == "25520101@gm.uit.edu.vn"
    assert data["student_id"] == "25520101"

    forbidden_fields = client.patch(
        "/api/users/me",
        headers=headers,
        json={"email": "attacker@gm.uit.edu.vn", "student_id": "25520199"},
    )
    assert forbidden_fields.status_code == 422


def test_profile_update_rejects_blank_name_and_empty_body(client):
    headers = register_and_login(client, "25520102")
    blank = client.patch(
        "/api/users/me", headers=headers, json={"full_name": "   "}
    )
    empty = client.patch("/api/users/me", headers=headers, json={})
    assert blank.status_code == 422
    assert empty.status_code == 422


def test_profile_update_requires_auth(client):
    assert client.patch("/api/users/me", json={"full_name": "Nguyễn Văn A"}).status_code == 401


def test_change_password_requires_current_password_and_new_password_works(client):
    headers = register_and_login(client, "25520103", password="Matkhau123")

    wrong = client.post(
        "/api/users/me/change-password",
        headers=headers,
        json={"current_password": "sai-mat-khau", "new_password": "Matkhau456"},
    )
    assert wrong.status_code == 400

    changed = client.post(
        "/api/users/me/change-password",
        headers=headers,
        json={"current_password": "Matkhau123", "new_password": "Matkhau456"},
    )
    assert changed.status_code == 200

    good_login = client.post(
        "/api/auth/login",
        json={"email": "25520103@gm.uit.edu.vn", "password": "Matkhau456"},
    )
    old_login = client.post(
        "/api/auth/login",
        json={"email": "25520103@gm.uit.edu.vn", "password": "Matkhau123"},
    )
    assert good_login.status_code == 200
    assert old_login.status_code == 401


def test_password_change_rejects_same_password_and_over_72_bytes(client):
    headers = register_and_login(client, "25520104", password="Matkhau123")
    same = client.post(
        "/api/users/me/change-password",
        headers=headers,
        json={"current_password": "Matkhau123", "new_password": "Matkhau123"},
    )
    too_long = client.post(
        "/api/users/me/change-password",
        headers=headers,
        json={"current_password": "Matkhau123", "new_password": "a" * 73},
    )
    assert same.status_code == 422
    assert too_long.status_code == 422


def test_public_profile_does_not_expose_email_or_student_id(client, seller_headers):
    user_id = client.get("/api/users/me", headers=seller_headers).json()["data"]["user_id"]
    response = client.get(f"/api/users/{user_id}/public-profile")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user_id"] == user_id
    assert data["full_name"] == "Sinh viên 25520001"
    assert "email" not in data
    assert "student_id" not in data
    assert "password_hash" not in data


def test_public_profile_lists_available_and_sold_but_not_hidden_reserved(
    client, seller_headers, product_id, session_factory
):
    seller_id = client.get("/api/users/me", headers=seller_headers).json()["data"]["user_id"]
    with session_factory() as session:
        session.get(models.Product, product_id).status = "Sold"
        session.commit()

    hidden_id = client.post(
        "/api/products",
        headers=seller_headers,
        json={"category_id": 1, "title": "Tin ẩn", "price": 10000, "condition": "Good"},
    ).json()["data"]["product_id"]
    hidden = client.patch(
        f"/api/products/{hidden_id}", headers=seller_headers, json={"status": "Hidden"}
    )
    assert hidden.status_code == 200

    reserved_id = client.post(
        "/api/products",
        headers=seller_headers,
        json={"category_id": 1, "title": "Tin giữ chỗ", "price": 20000, "condition": "Good"},
    ).json()["data"]["product_id"]
    with session_factory() as session:
        session.get(models.Product, reserved_id).status = "Reserved"
        session.commit()

    public = client.get(f"/api/users/{seller_id}/products")
    assert public.status_code == 200
    ids = {item["product_id"] for item in public.json()["data"]}
    assert product_id in ids
    assert hidden_id not in ids
    assert reserved_id not in ids
    assert len(ids) == 1


def test_public_products_support_available_or_sold_filter(client, seller_headers, product_id):
    seller_id = client.get("/api/users/me", headers=seller_headers).json()["data"]["user_id"]
    available = client.get(f"/api/users/{seller_id}/products?status=Available")
    sold = client.get(f"/api/users/{seller_id}/products?status=Sold")
    invalid = client.get(f"/api/users/{seller_id}/products?status=Hidden")
    assert available.status_code == 200 and product_id in {x["product_id"] for x in available.json()["data"]}
    assert sold.status_code == 200 and sold.json()["data"] == []
    assert invalid.status_code == 422
