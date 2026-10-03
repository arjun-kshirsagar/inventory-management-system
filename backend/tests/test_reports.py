from decimal import Decimal

from tests.conftest import receive
from tests.test_sales import sell


def test_reports(admin, cashier, product):
    shirt = product["shirt"]["variants"][0]
    blazer = product["blazer"]["variants"][0]
    receive(admin, shirt["id"], 10)
    receive(admin, blazer["id"], 1)
    sale = sell(
        cashier, [{"variant_id": shirt["id"], "qty": 2}, {"variant_id": blazer["id"], "qty": 1}]
    ).json()
    cashier.post(
        f"/api/v1/sales/{sale['id']}/returns",
        json={"items": [{"sale_item_id": sale["items"][0]["id"], "qty": 1}]},
    )

    dash = admin.get("/api/v1/reports/dashboard").json()
    assert dash["bills"] == 1 and dash["sales_total"] == sale["grand_total"]
    assert len(dash["trend"]) == 30
    assert dash["low_stock_count"] == 2  # blazer at 0, shirt "M" at 0

    by_day = admin.get("/api/v1/reports/sales", params={"group_by": "day"}).json()
    assert by_day["totals"]["qty"] == 2  # 3 sold, 1 returned
    by_cashier = admin.get("/api/v1/reports/sales", params={"group_by": "cashier"}).json()
    assert by_cashier["rows"][0]["key"] == "Cashier"
    assert by_cashier["payments"][0]["method"] == "cash"

    perf = admin.get("/api/v1/reports/products").json()
    assert {r["sku"] for r in perf["best_sellers"]} == {shirt["sku"], blazer["sku"]}
    assert any(r["key"] == "S" for r in perf["by_size"])

    val = admin.get("/api/v1/reports/stock-valuation").json()
    assert val["totals"]["units"] == 9  # 10 - 2 + 1 returned shirts, blazer sold

    gst = admin.get("/api/v1/reports/gst").json()
    assert {(r["hsn_code"], r["gst_rate"]) for r in gst["hsn"]} == {
        ("6205", "5.00"),
        ("6203", "18.00"),
    }
    assert gst["credit_notes"][0]["qty"] == 1

    profit = admin.get("/api/v1/reports/profit").json()["totals"]
    assert Decimal(profit["gross_profit"]) == Decimal(profit["revenue"]) - Decimal(profit["cogs"])
    assert Decimal(profit["cogs"]) == Decimal("649") * 1 + Decimal("3249")

    csv = admin.get("/api/v1/reports/sales", params={"format": "csv"})
    assert csv.headers["content-type"].startswith("text/csv")
    assert csv.text.splitlines()[0] == "key,bills,qty,taxable_value,tax,total"
