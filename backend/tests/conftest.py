"""Test chạy trên SQLite in-memory: không cần SQL Server.

Các ràng buộc CHECK/UNIQUE/FK đều có trong models nên vẫn được kiểm tra.
(Filtered unique index và trigger chỉ có ở file SQL cho SQL Server, không test ở đây.)
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-key-for-pytest-only-1234567890"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base, get_db
from main import app


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as s:
        s.add_all([models.Category(category_name=n) for n in ["Giáo trình", "Linh kiện IT", "Khác"]])
        s.commit()
    yield factory
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register_and_login(client, student_id="25520001", password="Matkhau123", major="Khoa học máy tính"):
    r = client.post(
        "/api/auth/register",
        json={
            "email": f"{student_id}@gm.uit.edu.vn",
            "student_id": student_id,
            "full_name": f"Sinh viên {student_id}",
            "major": major,
            "password": password,
        },
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", json={"email": f"{student_id}@gm.uit.edu.vn", "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


@pytest.fixture()
def seller_headers(client):
    return register_and_login(client, "25520001")


@pytest.fixture()
def buyer_headers(client):
    return register_and_login(client, "25520002")


@pytest.fixture()
def product_id(client, seller_headers):
    r = client.post(
        "/api/products",
        headers=seller_headers,
        json={"category_id": 1, "title": "Giáo trình Cấu trúc dữ liệu", "price": 45000, "condition": "Good"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["product_id"]
