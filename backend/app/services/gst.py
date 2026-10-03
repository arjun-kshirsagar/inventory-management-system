"""GST calculation for tax-inclusive retail prices.

Apparel prices in India are printed inclusive of GST, so the taxable value is
backed out of the price: taxable = price * 100 / (100 + rate).

Apparel GST depends on the per-piece sale value (taxable value): since 22 Sept 2025,
<= Rs 2,500 is 5% and above is 18%. Rates live in the tax_slabs table so they can be
changed without a deploy.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TaxSlab
from app.services.money import q


class TaxConfigError(Exception):
    pass


@dataclass(frozen=True)
class LineTax:
    rate: Decimal
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal

    @property
    def total_tax(self) -> Decimal:
        return self.cgst + self.sgst + self.igst


def find_slab(slabs: list[TaxSlab], hsn_code: str, on: date) -> TaxSlab:
    candidates = [s for s in slabs if hsn_code.startswith(s.hsn_prefix) and s.effective_from <= on]
    if not candidates:
        raise TaxConfigError(f"No GST rate configured for HSN {hsn_code}")
    return max(candidates, key=lambda s: (len(s.hsn_prefix), s.effective_from))


def load_slabs(db: Session) -> list[TaxSlab]:
    return list(db.scalars(select(TaxSlab)))


def _taxable(inclusive: Decimal, rate: Decimal) -> Decimal:
    return inclusive * 100 / (100 + rate)


def pick_rate(slab: TaxSlab, unit_inclusive: Decimal) -> Decimal:
    """Choose the rate for one piece priced `unit_inclusive` (GST included).

    Try the lower rate first; if the resulting per-piece taxable value is above the
    threshold, the higher rate applies. (Prices between ~2,625 and ~2,950 are ambiguous
    under an inclusive price; this resolves them to the higher rate.)
    """
    if slab.price_threshold is None:
        return slab.rate_below
    if _taxable(unit_inclusive, slab.rate_below) <= slab.price_threshold:
        return slab.rate_below
    return slab.rate_above


def compute_line_tax(net_inclusive: Decimal, qty: int, slab: TaxSlab, interstate: bool) -> LineTax:
    rate = pick_rate(slab, net_inclusive / qty)
    taxable = q(_taxable(net_inclusive, rate))
    tax = q(net_inclusive) - taxable
    if interstate:
        return LineTax(rate, taxable, Decimal("0.00"), Decimal("0.00"), tax)
    cgst = q(tax / 2)
    return LineTax(rate, taxable, cgst, tax - cgst, Decimal("0.00"))


def allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `total` across lines in proportion to `weights`; the last line absorbs rounding."""
    weight_sum = sum(weights)
    if not weights or total == 0 or weight_sum == 0:
        return [Decimal("0.00")] * len(weights)
    shares = [q(total * w / weight_sum) for w in weights[:-1]]
    shares.append(q(total) - sum(shares, Decimal("0.00")))
    return shares
