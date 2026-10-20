"""Validate inputs without binary float conversion or decimal rounding."""

import re
from decimal import Decimal, DecimalException
from typing import TypeAlias

DecimalInput: TypeAlias = Decimal | str | int
_DECIMAL_TEXT = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


class ValidationError(ValueError):
    """Invalid field, optionally associated with a dimension's stable ID."""

    def __init__(
        self, field: str, message: str, *, dimension_id: str | None = None
    ) -> None:
        self.field = field
        self.dimension_id = dimension_id
        location = f"dimension {dimension_id!r}: " if dimension_id is not None else ""
        super().__init__(f"{location}{field}: {message}")


def parse_decimal(
    value: DecimalInput, *, field: str, dimension_id: str | None = None
) -> Decimal:
    """Accept finite Decimal, integer, or decimal text; reject floats and bools."""
    if isinstance(value, str):
        value = value.strip()
        valid = _DECIMAL_TEXT.fullmatch(value) is not None
    else:
        valid = isinstance(value, Decimal) or type(value) is int
    if not valid:
        raise ValidationError(
            field,
            "expected finite Decimal, integer, or decimal string",
            dimension_id=dimension_id,
        )
    try:
        result = Decimal(value)
    except (DecimalException, ValueError, OverflowError) as exc:
        raise ValidationError(
            field, "invalid decimal value", dimension_id=dimension_id
        ) from exc
    if not result.is_finite():
        raise ValidationError(field, "must be finite", dimension_id=dimension_id)
    return result


def require_text(value: str, *, field: str, dimension_id: str | None = None) -> str:
    """Trim surrounding whitespace and require meaningful text."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            field, "must be a nonempty string", dimension_id=dimension_id
        )
    return value.strip()
