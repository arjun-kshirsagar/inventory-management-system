import pytest


def test_login_and_me(anon):
    r = anon.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "secret123"})
    assert r.status_code == 200
    assert "ims_refresh" in r.cookies
    token = r.json()["access_token"]
    me = anon.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "admin"


def test_refresh_uses_cookie(anon):
    anon.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "secret123"})
    r = anon.post("/api/v1/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]


def test_bad_password(anon):
    r = anon.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "nope"})
    assert r.status_code == 401


def test_unauthenticated(anon):
    assert anon.get("/api/v1/products").status_code == 401


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/api/v1/users"),
        ("post", "/api/v1/products"),
        ("post", "/api/v1/inventory/adjustments"),
        ("get", "/api/v1/reports/dashboard"),
        ("get", "/api/v1/reports/sales"),
        ("get", "/api/v1/reports/gst"),
        ("put", "/api/v1/settings/store"),
        ("post", "/api/v1/settings/tax-slabs"),
        ("post", "/api/v1/brands"),
    ],
)
def test_cashier_forbidden_from_admin_routes(cashier, method, path):
    r = getattr(cashier, method)(path, **({} if method == "get" else {"json": {}}))
    assert r.status_code == 403


def test_cashier_can_read_catalog_and_stock(cashier):
    assert cashier.get("/api/v1/products").status_code == 200
    assert cashier.get("/api/v1/inventory/stock").status_code == 200
