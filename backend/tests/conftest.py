import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://ims:ims@localhost:5432/ims_test")

from datetime import date  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.models  # noqa: E402, F401
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import StoreSettings, TaxSlab, User  # noqa: E402
from app.models.enums import Role  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def clean_db(schema):
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    with SessionLocal() as db:
        db.add(StoreSettings(id=1, name="Test Store", state_code="27", state_name="Maharashtra"))
        for prefix in ("61", "62"):
            db.add(
                TaxSlab(
                    name=f"Apparel {prefix}",
                    hsn_prefix=prefix,
                    price_threshold=Decimal("2500"),
                    rate_below=Decimal("5"),
                    rate_above=Decimal("18"),
                    effective_from=date(2025, 9, 22),
                )
            )
        db.add(
            TaxSlab(
                name="Default",
                hsn_prefix="",
                rate_below=Decimal("18"),
                rate_above=Decimal("18"),
                effective_from=date(2025, 9, 22),
            )
        )
        db.add_all(
            [
                User(
                    email="admin@test.local",
                    name="Admin",
                    role=Role.ADMIN,
                    password_hash=hash_password("secret123"),
                ),
                User(
                    email="cashier@test.local",
                    name="Cashier",
                    role=Role.CASHIER,
                    password_hash=hash_password("secret123"),
                ),
            ]
        )
        db.commit()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def _client(user_id: int) -> TestClient:
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {create_access_token(user_id)}"
    return client


@pytest.fixture
def admin() -> TestClient:
    return _client(1)


@pytest.fixture
def cashier() -> TestClient:
    return _client(2)


@pytest.fixture
def anon() -> TestClient:
    return TestClient(app)


@pytest.fixture
def product(admin):
    """A shirt (HSN 6205) in S/M x Blue at 1299, and a blazer (6203) at 6499."""

    def make(name, hsn, price, mrp, sizes, colors=("Blue",)):
        r = admin.post(
            "/api/v1/products",
            json={
                "name": name,
                "hsn_code": hsn,
                "matrix": {
                    "sizes": list(sizes),
                    "colors": list(colors),
                    "mrp": str(mrp),
                    "selling_price": str(price),
                    "cost_price": str(price // 2),
                },
            },
        )
        assert r.status_code == 201, r.text
        return r.json()

    shirt = make("Oxford Shirt", "6205", 1299, 1499, ["S", "M"])
    blazer = make("Blazer", "6203", 6499, 6999, ["40"], ["Charcoal"])
    return {"shirt": shirt, "blazer": blazer}


def receive(admin: TestClient, variant_id: int, qty: int, unit_cost: str | None = None):
    item = {"variant_id": variant_id, "qty": qty}
    if unit_cost:
        item["unit_cost"] = unit_cost
    r = admin.post("/api/v1/inventory/receipts", json={"items": [item]})
    assert r.status_code == 201, r.text
    return r.json()
