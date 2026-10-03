import enum


class Role(enum.StrEnum):
    ADMIN = "admin"
    CASHIER = "cashier"


class MovementType(enum.StrEnum):
    PURCHASE = "purchase"
    SALE = "sale"
    RETURN = "return"
    ADJUSTMENT = "adjustment"


class SaleStatus(enum.StrEnum):
    COMPLETED = "completed"
    PARTIALLY_RETURNED = "partially_returned"
    RETURNED = "returned"


class PaymentMethod(enum.StrEnum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
