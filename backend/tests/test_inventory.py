from sqlalchemy import func, select

from app.models import ProductVariant, StockMovement
from tests.conftest import receive


def test_matrix_creates_variants_with_sku_and_ean13(product):
    variants = product["shirt"]["variants"]
    assert [(v["size"], v["color"]) for v in variants] == [("S", "Blue"), ("M", "Blue")]
    assert variants[0]["sku"] == f"P{product['shirt']['id']:05d}-S-BLU"
    barcode = variants[0]["barcode"]
    assert len(barcode) == 13 and barcode.startswith("200")


def test_receive_stock_and_ledger(admin, product, db):
    v = product["shirt"]["variants"][0]
    grn = receive(admin, v["id"], 10, unit_cost="600.00")
    assert grn["total_qty"] == 10
    stock = admin.get("/api/v1/inventory/stock", params={"q": v["sku"]}).json()
    assert stock["items"][0]["quantity_on_hand"] == 10
    assert stock["items"][0]["cost_price"] == "600.00"
    ledger = db.scalar(
        select(func.sum(StockMovement.qty_delta)).where(StockMovement.variant_id == v["id"])
    )
    assert ledger == db.get(ProductVariant, v["id"]).quantity_on_hand == 10


def test_adjustment_cannot_go_negative(admin, product):
    v = product["shirt"]["variants"][0]
    receive(admin, v["id"], 2)
    r = admin.post(
        "/api/v1/inventory/adjustments",
        json={"variant_id": v["id"], "qty_delta": -3, "reason": "damaged"},
    )
    assert r.status_code == 400
    r = admin.post(
        "/api/v1/inventory/adjustments",
        json={"variant_id": v["id"], "qty_delta": -1, "reason": "damaged"},
    )
    assert r.status_code == 201
    movements = admin.get("/api/v1/inventory/movements", params={"variant_id": v["id"]}).json()
    assert [m["type"] for m in movements["items"]] == ["adjustment", "purchase"]


def test_csv_import(admin):
    csv_text = (
        "product_name,category,brand,hsn_code,size,color,mrp,selling_price,cost_price\n"
        "Chinos,Trousers,Basics,6203,30,Khaki,1999,1799,800\n"
        "Chinos,Trousers,Basics,6203,32,Khaki,1999,1799,800\n"
        "Polo,T-Shirts,Basics,6105,M,Red,999,899,350\n"
    )
    r = admin.post("/api/v1/products/import", files={"file": ("p.csv", csv_text, "text/csv")})
    assert r.json() == {"products_created": 2, "variants_created": 3, "errors": []}


def test_csv_import_rejects_whole_file_on_error(admin):
    csv_text = (
        "product_name,hsn_code,size,color,mrp\nChinos,6203,30,Khaki,1999\nBad,62,30,Khaki,abc\n"
    )
    r = admin.post("/api/v1/products/import", files={"file": ("p.csv", csv_text, "text/csv")})
    body = r.json()
    assert body["variants_created"] == 0 and len(body["errors"]) == 1
    assert admin.get("/api/v1/products").json()["total"] == 0


def test_pos_lookup_by_barcode(cashier, admin, product):
    v = product["shirt"]["variants"][1]
    r = cashier.get("/api/v1/variants/lookup", params={"q": v["barcode"]})
    assert [x["id"] for x in r.json()] == [v["id"]]
    assert r.json()[0]["product_name"] == "Oxford Shirt"


def test_barcode_labels_pdf(admin, product):
    v = product["shirt"]["variants"][0]
    r = admin.post("/api/v1/variants/labels.pdf", json=[{"variant_id": v["id"], "copies": 3}])
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
