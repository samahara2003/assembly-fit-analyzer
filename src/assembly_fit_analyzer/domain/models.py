"""Input models; chain calculation and acceptance evaluation are separate."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from assembly_fit_analyzer.validation import (
    DecimalInput,
    ValidationError,
    parse_decimal,
)
from assembly_fit_analyzer.validation.inputs import require_text


@dataclass(frozen=True, slots=True, init=False)
class DimensionContribution:
    """A nonnegative physical length and its separate chain orientation."""

    dimension_id: str
    label: str
    nominal: Decimal
    lower_deviation: Decimal
    upper_deviation: Decimal
    sign: Literal[-1, 1]

    def __init__(
        self,
        dimension_id: str,
        label: str,
        nominal: DecimalInput,
        lower_deviation: DecimalInput,
        upper_deviation: DecimalInput,
        sign: Literal[-1, 1],
    ) -> None:
        dimension_id = require_text(dimension_id, field="dimension_id")
        label = require_text(label, field="label", dimension_id=dimension_id)
        values = {
            field: parse_decimal(value, field=field, dimension_id=dimension_id)
            for field, value in (
                ("nominal", nominal),
                ("lower_deviation", lower_deviation),
                ("upper_deviation", upper_deviation),
            )
        }
        if values["nominal"] < 0:
            raise ValidationError(
                "nominal",
                "physical length must be nonnegative",
                dimension_id=dimension_id,
            )
        if values["lower_deviation"] > values["upper_deviation"]:
            raise ValidationError(
                "lower_deviation",
                "must be <= upper_deviation",
                dimension_id=dimension_id,
            )
        for field in ("lower_deviation", "upper_deviation"):
            # n + d >= 0 iff n >= -d. copy_negate is exact and independent of
            # Decimal context precision, unlike addition or unary minus.
            if values["nominal"] < values[field].copy_negate():
                raise ValidationError(
                    field,
                    "derived physical dimensional limit must be nonnegative",
                    dimension_id=dimension_id,
                )
        if type(sign) is not int or sign not in (-1, 1):
            raise ValidationError(
                "sign", "must be integer +1 or -1", dimension_id=dimension_id
            )
        object.__setattr__(self, "dimension_id", dimension_id)
        object.__setattr__(self, "label", label)
        for field, value in values.items():
            object.__setattr__(self, field, value)
        object.__setattr__(self, "sign", sign)


@dataclass(frozen=True, slots=True, init=False)
class AcceptanceLimits:
    """Mandatory inclusive functional bounds, which may be negative."""

    lower: Decimal
    upper: Decimal

    def __init__(self, lower: DecimalInput, upper: DecimalInput) -> None:
        lower = parse_decimal(lower, field="acceptance_limits.lower")
        upper = parse_decimal(upper, field="acceptance_limits.upper")
        if lower > upper:
            raise ValidationError("acceptance_limits.lower", "must be <= upper")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)


def validate_contributions(
    contributions: Sequence[DimensionContribution],
) -> tuple[DimensionContribution, ...]:
    """Snapshot and validate a chain for projects and standalone calculations."""
    if not isinstance(contributions, Sequence) or isinstance(
        contributions, (str, bytes)
    ):
        raise ValidationError("contributions", "must be a nonempty sequence")
    items = tuple(contributions)
    if not items:
        raise ValidationError("contributions", "must contain at least one dimension")
    seen = set()
    for index, item in enumerate(items):
        if not isinstance(item, DimensionContribution):
            raise ValidationError(
                f"contributions[{index}]", "must be a DimensionContribution"
            )
        if item.dimension_id in seen:
            raise ValidationError(
                "dimension_id", "duplicate ID", dimension_id=item.dimension_id
            )
        seen.add(item.dimension_id)
    return items


@dataclass(frozen=True, slots=True, init=False)
class AnalysisProject:
    """A named, single-unit chain with an immutable input snapshot."""

    name: str
    unit: Literal["mm", "in"]
    contributions: tuple[DimensionContribution, ...]
    acceptance_limits: AcceptanceLimits | None

    def __init__(
        self,
        name: str,
        unit: Literal["mm", "in"],
        contributions: Sequence[DimensionContribution],
        acceptance_limits: AcceptanceLimits | None = None,
    ) -> None:
        name = require_text(name, field="name")
        if not isinstance(unit, str) or unit not in ("mm", "in"):
            raise ValidationError("unit", "must be 'mm' or 'in'; no unit conversion")
        items = validate_contributions(contributions)
        if acceptance_limits is not None and not isinstance(
            acceptance_limits, AcceptanceLimits
        ):
            raise ValidationError(
                "acceptance_limits", "must be AcceptanceLimits or None"
            )
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "contributions", items)
        object.__setattr__(self, "acceptance_limits", acceptance_limits)
