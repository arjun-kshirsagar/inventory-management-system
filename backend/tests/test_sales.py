import threading
from decimal import Decimal

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import ProductVariant, StockMovement
from app.schemas.sales import PaymentIn, SaleCreate, SaleItemIn
from app.services import sales as sales_service
from app.services.stock import StockError
from tests.conftest import receive

D = Decimal


def sell(client, items, total=None, **extra):
    if total is None:
        quote = client.post("/api/v1/sales/quote", json={"items": items, **extra}).json()
        total = quote["grand_total"]
    return client.post(
        "/api/v1/sales",
        json={"items": items, "payments": [{"method": "cash", "amount": str(total)}], **extra},
    )


def test_sale_reduces_stock_and_computes_gst(cashier, admin, product):
    shirt = product["shirt"]["variants"][0]
    blazer = product["blazer"]["variants"][0]
    receive(admin, shirt["id"], 5)
    receive(admin, blazer["id"], 2)

    r = sell(
        cashier, [{"variant_id": shirt["id"], "qty": 2}, {"variant_id": blazer["id"], "qty": 1}]
    )
    assert r.status_code == 201, r.text
    sale = r.json()
    rates = {i["sku"]: i["gst_rate"] for i in sale["items"]}
    assert rates == {shirt["sku"]: "5.00", blazer["sku"]: "18.00"}
    assert D(sale["igst"]) == 0
    assert D(sale["taxable_value"]) + D(sale["cgst"]) + D(sale["sgst"]) == D("9097.00")
    assert sale["grand_total"] == "9097.00"
    assert sale["invoice_no"].startswith("INV/") and sale["invoice_no"].endswith("/000001")

    stock = {
        s["variant_id"]: s["quantity_on_hand"]
        for s in admin.get("/api/v1/inventory/stock").json()["items"]
    }
    assert stock[shirt["id"]] == 3 and stock[blazer["id"]] == 1


def test_interstate_customer_gets_igst(cashier, admin, product):
    shirt = product["shirt"]["variants"][0]
    receive(admin, shirt["id"], 1)
    customer = cashier.post(
        "/api/v1/customers",
        json={"name": "Ananya", "phone": "9840054321", "state_code": "33"},
    ).json()
    sale = sell(cashier, [{"variant_id": shirt["id"], "qty": 1}], customer_id=customer["id"]).json()
    assert sale["place_of_supply"] == "33"
    assert D(sale["cgst"]) == D(sale["sgst"]) == 0 and D(sale["igst"]) > 0


def test_bill_discount_and_round_off(cashier, admin, product):
    shirt = product["shirt"]["variants"][0]
    receive(admin, shirt["id"], 3)
    items = [{"variant_id": shirt["id"], "qty": 3, "discount": "10.50"}]
    quote = cashier.post(
        "/api/v1/sales/quote", json={"items": items, "bill_discount": "100"}
    ).json()
    # 3 x 1299 = 3897 - 10.50 - 100 = 3786.50 -> rounds to 3787
    assert quote["discount"] == "110.50"
    assert quote["grand_total"] == "3787.00" and quote["round_off"] == "0.50"


def test_payment_must_match_total(cashier, admin, product):
    shirt = product["shirt"]["variants"][0]
    receive(admin, shirt["id"], 1)
    r = sell(cashier, [{"variant_id": shirt["id"], "qty": 1}], total="100")
    assert r.status_code == 400 and "Payments total" in r.json()["detail"]


def test_cannot_oversell(cashier, admin, product):
    shirt = product["shirt"]["variants"][0]
    receive(admin, shirt["id"], 1)
    r = sell(cashier, [{"variant_id": shirt["id"], "qty": 2}])
    assert r.status_code == 409
    # The failed sale must not consume an invoice number.
    ok = sell(cashier, [{"variant_id": shirt["id"], "qty": 1}]).json()
    assert ok["invoice_no"].endswith("/000001")


def test_idempotency_key_prevents_double_sale(cashier, admin, product):
    shirt = product["shirt"]["variants"][0]
    receive(admin, shirt["id"], 5)
    first = sell(cashier, [{"variant_id": shirt["id"], "qty": 1}], idempotency_key="abc-123")
    second = sell(cashier, [{"variant_id": shirt["id"], "qty": 1}], idempotency_key="abc-123")
    assert first.json()["id"] == second.json()["id"]
    stock = admin.get("/api/v1/inventory/stock").json()["items"]
    assert next(s for s in stock if s["variant_id"] == shirt["id"])["quantity_on_hand"] == 4


def test_concurrent_sales_of_last_unit(admin, product):
    shirt = product["shirt"]["variants"][0]
    receive(admin, shirt["id"], 1)
    with SessionLocal() as db:
        total = sales_service.quote_sale(
            db, [SaleItemIn(variant_id=shirt["id"], qty=1)], None, D(0)
        ).grand_total

    barrier = threading.Barrier(4)
    results: list[str] = []

    def attempt():
        with SessionLocal() as db:
            barrier.wait()
            try:
                sales_service.create_sale(
                    db,
                    SaleCreate(
                        items=[SaleItemIn(variant_id=shirt["id"], qty=1)],
                        payments=[PaymentIn(method="cash", amount=total)],
                    ),
                    cashier_id=2,
                )
                results.append("ok")
            except StockError:
                results.append("out_of_stock")

    threads = [threading.Thread(target=attempt) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "out_of_stock", "out_of_stock", "out_of_stock"]
    with SessionLocal() as db:
        assert db.get(ProductVariant, shirt["id"]).quantity_on_hand == 0


def test_invoice_numbers_are_sequential(cashier, admin, product):
    shirt = product["shirt"]["variants"][0]
    receive(admin, shirt["id"], 5)
    numbers = [
        sell(cashier, [{"variant_id": shirt["id"], "qty": 1}]).json()["invoice_no"]
        for _ in range(3)
    ]
    assert [n[-6:] for n in numbers] == ["000001", "000002", "000003"]


def test_partial_then_full_return(cashier, admin, product, db):
    shirt = product["shirt"]["variants"][0]
    receive(admin, shirt["id"], 3)
    sale = sell(cashier, [{"variant_id": shirt["id"], "qty": 3, "discount": "1"}]).json()
    item = sale["items"][0]

    r1 = cashier.post(
        f"/api/v1/sales/{sale['id']}/returns",
        json={"items": [{"sale_item_id": item["id"], "qty": 1}], "reason": "size"},
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["credit_note_no"].startswith("CN/")
    assert cashier.get(f"/api/v1/sales/{sale['id']}").json()["status"] == "partially_returned"

    r2 = cashier.post(
        f"/api/v1/sales/{sale['id']}/returns",
        json={"items": [{"sale_item_id": item["id"], "qty": 2, "restock": False}]},
    )
    assert r2.status_code == 201
    refunded = D(r1.json()["refund_amount"]) + D(r2.json()["refund_amount"])
    assert refunded == D(item["line_total"])  # returns add up exactly to the sale line

    detail = cashier.get(f"/api/v1/sales/{sale['id']}").json()
    assert detail["status"] == "returned" and len(detail["returns"]) == 2
    # Only the first (restocked) unit came back into stock.
    ledger = db.scalar(
        select(func.sum(StockMovement.qty_delta)).where(StockMovement.variant_id == shirt["id"])
    )
    assert ledger == db.get(ProductVariant, shirt["id"]).quantity_on_hand == 1

    over = cashier.post(
        f"/api/v1/sales/{sale['id']}/returns",
        json={"items": [{"sale_item_id": item["id"], "qty": 1}]},
    )
    assert over.status_code == 400


def test_cashier_sees_only_own_sales(cashier, admin, product):
    shirt = product["shirt"]["variants"][0]
    receive(admin, shirt["id"], 2)
    admin_sale = sell(admin, [{"variant_id": shirt["id"], "qty": 1}]).json()
    sell(cashier, [{"variant_id": shirt["id"], "qty": 1}])
    assert cashier.get("/api/v1/sales").json()["total"] == 1
    assert admin.get("/api/v1/sales").json()["total"] == 2
    assert cashier.get(f"/api/v1/sales/{admin_sale['id']}").status_code == 404


def test_invoice_and_credit_note_pdfs(cashier, admin, product):
    shirt = product["shirt"]["variants"][0]
    receive(admin, shirt["id"], 2)
    sale = sell(cashier, [{"variant_id": shirt["id"], "qty": 2}]).json()
    for layout in ("a4", "thermal"):
        r = cashier.get(f"/api/v1/sales/{sale['id']}/invoice.pdf", params={"layout": layout})
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
    html = cashier.get(f"/api/v1/sales/{sale['id']}/invoice.html").text
    assert "TAX INVOICE" in html and "6205" in html and "Rupees Two Thousand" in html
    ret = cashier.post(
        f"/api/v1/sales/{sale['id']}/returns",
        json={"items": [{"sale_item_id": sale["items"][0]["id"], "qty": 1}]},
    ).json()
    r = cashier.get(f"/api/v1/returns/{ret['id']}/credit-note.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
