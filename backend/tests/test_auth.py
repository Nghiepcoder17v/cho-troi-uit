from conftest import register_and_login


def reg(client, **over):
    body = {
        "email": "25520001@gm.uit.edu.vn",
        "student_id": "25520001",
        "full_name": "Hà Văn A",
        "major": "Kỹ thuật phần mềm",
        "password": "Matkhau123",
    }
    body.update(over)
    return client.post("/api/auth/register", json=body)


def test_register_success_hides_password(client):
    r = reg(client)
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["email"] == "25520001@gm.uit.edu.vn"
    assert "password" not in data and "password_hash" not in data


def test_register_normalizes_email_case(client):
    r = reg(client, email="25520001@GM.UIT.EDU.VN")
    assert r.status_code == 201
    assert r.json()["data"]["email"] == "25520001@gm.uit.edu.vn"


def test_register_rejects_non_uit_email(client):
    assert reg(client, email="25520001@gmail.com").status_code == 422


def test_register_rejects_suffix_trick(client):
    assert reg(client, email="25520001@gm.uit.edu.vn.evil.com").status_code == 422


def test_register_rejects_student_id_mismatch(client):
    assert reg(client, student_id="25520009").status_code == 422


def test_register_rejects_bad_student_id(client):
    assert reg(client, email="abc@gm.uit.edu.vn", student_id="abc").status_code == 422


def test_register_rejects_short_password(client):
    assert reg(client, password="1234567").status_code == 422


def test_register_rejects_overlong_password(client):
    assert reg(client, password="a" * 73).status_code == 422


def test_register_duplicate_returns_409(client):
    assert reg(client).status_code == 201
    assert reg(client).status_code == 409


def test_login_success_returns_token(client):
    reg(client)
    r = client.post("/api/auth/login", json={"email": "25520001@gm.uit.edu.vn", "password": "Matkhau123"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["token"] and data["major"] == "Kỹ thuật phần mềm"


def test_login_wrong_password_and_unknown_email_look_the_same(client):
    reg(client)
    a = client.post("/api/auth/login", json={"email": "25520001@gm.uit.edu.vn", "password": "saimatkhau"})
    b = client.post("/api/auth/login", json={"email": "99999999@gm.uit.edu.vn", "password": "saimatkhau"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_me_requires_valid_token(client):
    assert client.get("/api/users/me").status_code == 401
    assert client.get("/api/users/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_me_returns_current_user(client):
    h = register_and_login(client, "25520005")
    r = client.get("/api/users/me", headers=h)
    assert r.status_code == 200 and r.json()["data"]["student_id"] == "25520005"
