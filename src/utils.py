def to_cents(amount: float) -> int:
    return int(round(amount * 100))

def from_cents(amount: int) -> float:
    return round(amount / 100, 2)