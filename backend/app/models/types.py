from decimal import Decimal

from sqlalchemy import Numeric
from sqlalchemy.orm import mapped_column

Money = Numeric(12, 2)


def money_column(**kwargs):
    return mapped_column(Money, default=Decimal("0.00"), nullable=False, **kwargs)
