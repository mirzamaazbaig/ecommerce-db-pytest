"""Minimal API client used only to produce realistic data; every assertion is made in SQL."""
import uuid

import requests

from framework import db
from framework.config import API_URL, PASSWORD


class Client:
    def __init__(self):
        self.session = requests.Session()

    def request(self, method, path, **kw):
        kw.setdefault("timeout", 10)
        return self.session.request(method, f"{API_URL}/{path}", **kw)


def available() -> bool:
    try:
        return requests.get(f"{API_URL}/products", params={"limit": 1}, timeout=3).ok
    except requests.RequestException:
        return False


def register(prefix="u"):
    client = Client()
    email = f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"
    res = client.request("POST", "auth/register", json={"email": email, "password": PASSWORD})
    assert res.status_code == 201, res.text
    client.id = res.json()["user"]["id"]
    client.email = email
    return client


def register_admin():
    client = register("adm")
    with db.connect(autocommit=True) as conn:
        conn.execute("UPDATE users SET role = 'admin' WHERE id = %s", (client.id,))
    assert client.request("POST", "auth/login", json={"email": client.email, "password": PASSWORD}).status_code == 200
    return client


def create_product(admin, **overrides):
    body = {"name": f"DB Product {uuid.uuid4().hex[:8]}", "description": "db suite", "price": 25, "stock": 10,
            "imageUrl": None, "categoryId": 1, **overrides}
    res = admin.request("POST", "products", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def order(user, *lines):
    """lines are (product, quantity). Client prices are sent as 1: the server must ignore them."""
    items = [{"productId": p["id"], "quantity": q, "price": 1} for p, q in lines]
    return user.request("POST", "orders", json={"items": items})
