from conftest import register_and_login


def create(client, headers, **over):
    body = {"category_id": 1, "title": "Sản phẩm", "price": 100000, "condition": "Good"}
    body.update(over)
    return client.post("/api/products", headers=headers, json=body)


def test_create_requires_auth(client):
    r = client.post("/api/products", json={"category_id": 1, "title": "x", "price": 1, "condition": "Good"})
    assert r.status_code == 401


def test_create_uses_seller_from_token(client, seller_headers, product_id):
    r = client.get(f"/api/products/{product_id}")
    assert r.status_code == 200
    seller = r.json()["data"]["seller"]
    me = client.get("/api/users/me", headers=seller_headers).json()["data"]
    assert seller["user_id"] == me["user_id"]


def test_create_validations(client, seller_headers):
    assert create(client, seller_headers, condition="Excellent").status_code == 422
    assert create(client, seller_headers, price=-1).status_code == 422
    assert create(client, seller_headers, price=10**9).status_code == 422
    assert create(client, seller_headers, title="   ").status_code == 422
    assert create(client, seller_headers, category_id=999).status_code == 404


def test_price_is_a_json_number(client, seller_headers, product_id):
    price = client.get(f"/api/products/{product_id}").json()["data"]["price"]
    assert isinstance(price, (int, float)) and price == 45000


def test_list_filters_and_pagination(client, seller_headers):
    for i in range(5):
        create(client, seller_headers, title=f"Bàn phím {i}", category_id=2)
    create(client, seller_headers, title="Sách A", category_id=1)

    r = client.get("/api/products", params={"category_id": 2, "page_size": 2, "page": 3}).json()
    assert r["pagination"] == {"current_page": 3, "page_size": 2, "total_items": 5, "total_pages": 3}
    assert len(r["data"]) == 1

    r = client.get("/api/products", params={"q": "sách"}).json()
    assert [p["title"] for p in r["data"]] == ["Sách A"]


def test_search_treats_percent_literally(client, seller_headers):
    create(client, seller_headers, title="Giảm 50% hôm nay")
    create(client, seller_headers, title="Bình thường")
    r = client.get("/api/products", params={"q": "%"}).json()
    assert [p["title"] for p in r["data"]] == ["Giảm 50% hôm nay"]


def test_list_rejects_bad_params(client):
    assert client.get("/api/products", params={"page": 0}).status_code == 422
    assert client.get("/api/products", params={"page_size": 1000}).status_code == 422
    assert client.get("/api/products", params={"status": "Hidden"}).status_code == 400


def test_hidden_product_is_not_public(client, seller_headers, product_id, session_factory):
    import models

    with session_factory() as s:
        s.get(models.Product, product_id).status = "Hidden"
        s.commit()
    assert client.get(f"/api/products/{product_id}").status_code == 404
    assert client.get("/api/products").json()["data"] == []


def test_categories(client):
    names = [c["category_name"] for c in client.get("/api/categories").json()["data"]]
    assert names == ["Giáo trình", "Linh kiện IT", "Khác"]
