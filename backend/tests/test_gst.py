from datetime import date
from decimal import Decimal

import pytest

from app.models import TaxSlab
from app.services import gst
from app.services.money import amount_in_words
from app.services.numbering import financial_year

APPAREL = TaxSlab(
    hsn_prefix="62",
    price_threshold=Decimal("2500"),
    rate_below=Decimal("5"),
    rate_above=Decimal("18"),
    effective_from=date(2025, 9, 22),
)


@pytest.mark.parametrize(
    "unit_price, expected",
    [
        ("999", "5"),
        ("2625", "5"),  # 2625 / 1.05 = 2500.00 exactly -> still 5%
        ("2626", "18"),
        ("2950", "18"),
        ("6499", "18"),
    ],
)
def test_apparel_rate_threshold(unit_price, expected):
    assert gst.pick_rate(APPAREL, Decimal(unit_price)) == Decimal(expected)


def test_intra_state_splits_cgst_sgst():
    tax = gst.compute_line_tax(Decimal("1299.00"), 1, APPAREL, interstate=False)
    assert tax.rate == Decimal("5")
    assert tax.taxable_value == Decimal("1237.14")
    assert tax.cgst + tax.sgst == Decimal("61.86")
    assert tax.cgst == Decimal("30.93") and tax.sgst == Decimal("30.93")
    assert tax.igst == 0
    assert tax.taxable_value + tax.total_tax == Decimal("1299.00")


def test_inter_state_uses_igst():
    tax = gst.compute_line_tax(Decimal("6499.00"), 1, APPAREL, interstate=True)
    assert tax.rate == Decimal("18")
    assert tax.cgst == 0 and tax.sgst == 0
    assert tax.taxable_value + tax.igst == Decimal("6499.00")


def test_rate_uses_per_piece_value_not_line_total():
    # Two shirts at 1,500 = 3,000 line total, but each piece is under the threshold.
    tax = gst.compute_line_tax(Decimal("3000.00"), 2, APPAREL, interstate=False)
    assert tax.rate == Decimal("5")


def test_discount_can_drop_item_into_lower_slab():
    # 2,799 list price discounted to 2,599 -> per piece taxable 2,475.24 -> 5%
    tax = gst.compute_line_tax(Decimal("2599.00"), 1, APPAREL, interstate=False)
    assert tax.rate == Decimal("5")


def test_find_slab_prefers_longest_prefix_and_latest_date():
    default = TaxSlab(
        hsn_prefix="",
        rate_below=Decimal("18"),
        rate_above=Decimal("18"),
        price_threshold=None,
        effective_from=date(2017, 7, 1),
    )
    old = TaxSlab(
        hsn_prefix="62",
        rate_below=Decimal("5"),
        rate_above=Decimal("12"),
        price_threshold=Decimal("1000"),
        effective_from=date(2017, 7, 1),
    )
    slabs = [default, old, APPAREL]
    assert gst.find_slab(slabs, "6205", date(2026, 1, 1)) is APPAREL
    assert gst.find_slab(slabs, "6205", date(2025, 1, 1)) is old
    assert gst.find_slab(slabs, "4203", date(2026, 1, 1)) is default


def test_find_slab_without_match_raises():
    with pytest.raises(gst.TaxConfigError):
        gst.find_slab([APPAREL], "4203", date(2026, 1, 1))


def test_allocate_sums_exactly():
    shares = gst.allocate(Decimal("100"), [Decimal("1"), Decimal("1"), Decimal("1")])
    assert shares == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]


def test_amount_in_words():
    assert amount_in_words(Decimal("123456.50")) == (
        "Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six and Fifty Paise Only"
    )
    assert amount_in_words(Decimal("1299")) == "Rupees One Thousand Two Hundred Ninety Nine Only"


def test_financial_year():
    assert financial_year(date(2026, 10, 3)) == "2026-27"
    assert financial_year(date(2027, 3, 31)) == "2026-27"
    assert financial_year(date(2027, 4, 1)) == "2027-28"
