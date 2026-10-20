"""Decimal parsing uses exact inputs and rejects unsafe numeric coercions."""

from decimal import Decimal, localcontext

import pytest

from assembly_fit_analyzer.domain import AcceptanceLimits, DimensionContribution
from assembly_fit_analyzer.validation import ValidationError, parse_decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (12, "12"),
        (-12, "-12"),
        (10**80, "1e80"),
        ("0.1", "0.1"),
        ("  +1.2300  ", "1.2300"),
        (".5", "0.5"),
        ("1.", "1"),
        ("-2.5e-3", "-0.0025"),
        (Decimal("1.01"), "1.01"),
        ("-0", "0"),
    ],
)
def test_exact_decimal_inputs(value, expected):
    result = parse_decimal(value, field="nominal")
    assert isinstance(result, Decimal)
    assert result == Decimal(expected)


INVALID_NUMBERS = [
    True,
    False,
    1.0,
    0.1,
    float("nan"),
    float("inf"),
    None,
    "",
    " ",
    "bad",
    "1,2",
    "1_000",
    "１２",
    "1 2",
    "1e",
    "--1",
    "NaN",
    "sNaN",
    "Infinity",
    "-Infinity",
    Decimal("NaN"),
    Decimal("sNaN"),
    Decimal("Infinity"),
    Decimal("-Infinity"),
    [],
    {},
    b"1",
    complex(1),
    "1e99999999999999999999999999999999",
]


@pytest.mark.parametrize("value", INVALID_NUMBERS)
def test_invalid_decimal_inputs(value):
    with pytest.raises(ValidationError) as caught:
        parse_decimal(value, field="nominal", dimension_id="A")
    assert caught.value.field == "nominal"
    assert caught.value.dimension_id == "A"
    assert "nominal" in str(caught.value)
    assert "A" in str(caught.value)


@pytest.mark.parametrize("value", INVALID_NUMBERS)
@pytest.mark.parametrize("field", ["nominal", "lower_deviation", "upper_deviation"])
def test_dimension_boundary_rejects_invalid_numbers(value, field):
    fields = dict(
        dimension_id="A",
        label="Part",
        nominal=10,
        lower_deviation=0,
        upper_deviation=0,
        sign=1,
    )
    fields[field] = value
    with pytest.raises(ValidationError) as caught:
        DimensionContribution(**fields)
    assert caught.value.field == field
    assert caught.value.dimension_id == "A"


@pytest.mark.parametrize("value", INVALID_NUMBERS)
@pytest.mark.parametrize("field", ["lower", "upper"])
def test_acceptance_boundary_rejects_invalid_numbers(value, field):
    fields = dict(lower=0, upper=1)
    fields[field] = value
    with pytest.raises(ValidationError) as caught:
        AcceptanceLimits(**fields)
    assert caught.value.field == f"acceptance_limits.{field}"


def test_parsing_preserves_all_digits_and_decimal_scale():
    text = "123456789012345678901234567890.1234500"
    with localcontext() as context:
        context.prec = 2
        assert str(parse_decimal(text, field="nominal")) == text
        assert parse_decimal(10**80 + 1, field="nominal") == Decimal(10**80 + 1)
