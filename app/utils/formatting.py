CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}


def format_number(value: float) -> str:
    """1 -> "1", 5.5 -> "5.5", 50000 -> "50,000", 6.0459 -> "6.05"."""
    if abs(value - round(value)) < 1e-9:
        return f"{round(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def format_money(amount: float, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency)
    number = format_number(amount)
    return f"{symbol}{number}" if symbol else f"{number} {currency}"


def format_quantity(value: float, unit: str) -> str:
    """format_quantity(1, "months") -> "1 month"; units are given in plural form."""
    number = format_number(value)
    singular = number == "1" and unit.endswith("s")
    return f"{number} {unit[:-1] if singular else unit}"


def format_percent(fraction: float) -> str:
    return f"{fraction * 100:.1f}%".replace(".0%", "%")


def format_money_short(amount: float, currency: str) -> str:
    """55000 -> "€55K", 52500 -> "€52.5K", 1250000 -> "€1.25M", 900 -> "€900"."""
    for divisor, suffix in ((1_000_000, "M"), (1_000, "K")):
        if abs(amount) >= divisor:
            number = f"{amount / divisor:.2f}".rstrip("0").rstrip(".") + suffix
            break
    else:
        number = format_number(amount)
    symbol = CURRENCY_SYMBOLS.get(currency)
    return f"{symbol}{number}" if symbol else f"{number} {currency}"


def format_duration_short(value: float, unit: str) -> str:
    """(5, "months") -> "5 mo", (26, "weeks") -> "26 wk"."""
    return f"{format_number(value)} {'mo' if unit == 'months' else 'wk'}"
