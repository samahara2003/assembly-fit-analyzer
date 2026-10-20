"""Shared wording for signed result intervals; no physical meaning is assumed."""

from decimal import Decimal


def range_description(minimum: Decimal, maximum: Decimal) -> str:
    """Describe the signed interval without assuming a chain's physical meaning."""
    if minimum > 0:
        return "Entirely positive"
    if maximum < 0:
        return "Entirely negative"
    if minimum == maximum == 0:
        return "Zero-width interval at zero"
    if minimum == 0:
        return "Nonnegative; touches zero"
    if maximum == 0:
        return "Nonpositive; touches zero"
    return "Crosses zero: possible transition between clearance and interference"
