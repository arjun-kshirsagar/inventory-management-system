from decimal import ROUND_HALF_UP, Decimal

PAISE = Decimal("0.01")
RUPEE = Decimal("1")
ZERO = Decimal("0.00")


def q(value: Decimal | int | str) -> Decimal:
    """Round to paise, half-up (the convention used on Indian tax invoices)."""
    return Decimal(value).quantize(PAISE, rounding=ROUND_HALF_UP)


def round_rupee(value: Decimal) -> Decimal:
    return value.quantize(RUPEE, rounding=ROUND_HALF_UP).quantize(PAISE)


_ONES = (
    "Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen "
    "Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen"
).split()
_TENS = "_ _ Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()


def _below_thousand(n: int) -> str:
    words = []
    if n >= 100:
        words.append(f"{_ONES[n // 100]} Hundred")
        n %= 100
    if n >= 20:
        words.append(_TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else ""))
    elif n:
        words.append(_ONES[n])
    return " ".join(words)


def _int_to_words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    for divisor, label in ((10**7, "Crore"), (10**5, "Lakh"), (10**3, "Thousand")):
        if n >= divisor:
            parts.append(f"{_int_to_words(n // divisor)} {label}")
            n %= divisor
    if n:
        parts.append(_below_thousand(n))
    return " ".join(parts)


def amount_in_words(amount: Decimal) -> str:
    """Indian numbering: 123456.50 -> 'Rupees One Lakh ... and Fifty Paise Only'."""
    amount = q(amount)
    rupees = int(amount)
    paise = int((amount - rupees) * 100)
    text = f"Rupees {_int_to_words(rupees)}"
    if paise:
        text += f" and {_int_to_words(paise)} Paise"
    return text + " Only"
