"""Exercise public constructors and their immutable validated state."""

from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext

import pytest

from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.validation import ValidationError


def dimension(**overrides):
    fields = dict(
        dimension_id="A",
        label="Housing",
        nominal="10",
        lower_deviation="-0.1",
        upper_deviation="0.1",
        sign=1,
    )
    return DimensionContribution(**(fields | overrides))


def project(**overrides):
    fields = dict(
        name="Fit",
        unit="mm",
        contributions=[dimension()],
        acceptance_limits=AcceptanceLimits("-1", "1"),
    )
    return AnalysisProject(**(fields | overrides))


@pytest.mark.parametrize(
    ("lower", "upper"),
    [
        ("-0.1", "0.1"),
        ("-0.3", "0.2"),
        ("0.1", "0.2"),
        ("-0.3", "-0.1"),
        ("0.2", "0.2"),
        (0, 0),
        ("-10", "-10"),
    ],
)
@pytest.mark.parametrize("sign", [-1, 1])
def test_valid_dimension_intervals(lower, upper, sign):
    item = dimension(lower_deviation=lower, upper_deviation=upper, sign=sign)
    assert item.nominal == Decimal(10)
    assert item.lower_deviation == Decimal(lower)
    assert item.upper_deviation == Decimal(upper)
    assert item.sign == sign
    assert isinstance(item.nominal, Decimal)


def test_zero_physical_length_is_valid():
    assert dimension(nominal=0, lower_deviation=0, upper_deviation=0).nominal == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dimension_id", ""),
        ("dimension_id", None),
        ("label", " \t"),
        ("label", 1),
        ("nominal", "-1"),
        ("lower_deviation", "-10.001"),
        ("lower_deviation", "0.2"),
        ("upper_deviation", "-11"),
        ("nominal", None),
        ("lower_deviation", "bad"),
        ("upper_deviation", float("inf")),
    ],
)
def test_invalid_dimension_fields(field, value):
    with pytest.raises(ValidationError) as caught:
        dimension(**{field: value})
    error = caught.value
    # Reversed deviations are identified at the lower-deviation field.
    expected = (
        "lower_deviation" if field == "upper_deviation" and value == "-11" else field
    )
    assert error.field == expected
    assert error.dimension_id == (None if field == "dimension_id" else "A")
    assert expected in str(error)
    if error.dimension_id:
        assert "A" in str(error)


@pytest.mark.parametrize("sign", [True, False, 0, 2, -2, 1.0, "1", None, Decimal(1)])
def test_invalid_sign(sign):
    with pytest.raises(ValidationError, match="sign") as caught:
        dimension(sign=sign)
    assert caught.value.dimension_id == "A"


def test_negative_nominal_rejected_even_with_positive_limits():
    with pytest.raises(ValidationError, match="nominal"):
        dimension(nominal="-1", lower_deviation="2", upper_deviation="3")


def test_both_negative_limits_rejected():
    with pytest.raises(ValidationError, match="physical dimensional limit"):
        dimension(lower_deviation="-12", upper_deviation="-11")


def test_physical_limit_validation_does_not_round():
    with localcontext() as context:
        context.prec = 2
        with pytest.raises(ValidationError, match="lower_deviation"):
            dimension(nominal="1", lower_deviation="-1.00000000000000000001")
        item = dimension(nominal="1", lower_deviation="-1")
        assert item.lower_deviation == Decimal(-1)


@pytest.mark.parametrize(("lower", "upper"), [("-2", "-1"), ("-1", "1"), (0, 0)])
def test_valid_acceptance_limits(lower, upper):
    limits = AcceptanceLimits(lower, upper)
    assert limits.lower == Decimal(lower)
    assert limits.upper == Decimal(upper)
    assert isinstance(limits.lower, Decimal)


@pytest.mark.parametrize(
    ("lower", "upper", "field"),
    [
        ("2", "1", "acceptance_limits.lower"),
        (None, "1", "acceptance_limits.lower"),
        ("0", 1.0, "acceptance_limits.upper"),
        ("0", "NaN", "acceptance_limits.upper"),
    ],
)
def test_invalid_acceptance_limits(lower, upper, field):
    with pytest.raises(ValidationError) as caught:
        AcceptanceLimits(lower, upper)
    assert caught.value.field == field


def test_acceptance_interval_ordering_does_not_round():
    with localcontext() as context:
        context.prec = 2
        with pytest.raises(ValidationError, match="acceptance_limits.lower"):
            AcceptanceLimits("1.00000000000000000001", "1")


@pytest.mark.parametrize("unit", ["mm", "in"])
def test_project_copies_chain_and_preserves_order(unit):
    items = [dimension(), dimension(dimension_id="B", sign=-1)]
    result = project(unit=unit, contributions=items)
    items.clear()
    assert isinstance(result.contributions, tuple)
    assert [item.dimension_id for item in result.contributions] == ["A", "B"]
    assert result.unit == unit


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", " \n"),
        ("name", None),
        ("unit", "cm"),
        ("unit", "MM"),
        ("unit", " mm "),
        ("unit", None),
        ("unit", 1),
        ("contributions", []),
        ("contributions", None),
        ("contributions", "A"),
        ("contributions", {}),
        ("acceptance_limits", {}),
        ("acceptance_limits", (0, 1)),
    ],
)
def test_invalid_project_fields(field, value):
    with pytest.raises(ValidationError) as caught:
        project(**{field: value})
    assert caught.value.field == field


def test_invalid_contribution_member():
    with pytest.raises(ValidationError) as caught:
        project(contributions=[dimension(), {}])
    assert caught.value.field == "contributions[1]"


def test_duplicate_dimension_ids():
    with pytest.raises(ValidationError, match="duplicate ID") as caught:
        project(contributions=[dimension(), dimension(label="Other part", sign=-1)])
    assert caught.value.field == "dimension_id"
    assert caught.value.dimension_id == "A"


def test_text_is_trimmed_and_duplicate_ids_use_normalized_text():
    item = dimension(dimension_id=" A ", label=" Housing ")
    assert item.dimension_id == "A"
    assert item.label == "Housing"
    assert project(name=" Fit ").name == "Fit"
    with pytest.raises(ValidationError, match="duplicate ID"):
        project(contributions=[item, dimension()])


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (dimension(), "nominal", Decimal(20)),
        (AcceptanceLimits(0, 1), "lower", Decimal(-1)),
        (project(), "contributions", ()),
    ],
)
def test_models_are_immutable(model, field, value):
    with pytest.raises(FrozenInstanceError):
        setattr(model, field, value)


@pytest.mark.parametrize(
    ("constructor", "fields", "missing"),
    [
        (
            DimensionContribution,
            dict(
                dimension_id="A",
                label="Part",
                nominal=1,
                lower_deviation=0,
                upper_deviation=0,
                sign=1,
            ),
            field,
        )
        for field in (
            "dimension_id",
            "label",
            "nominal",
            "lower_deviation",
            "upper_deviation",
            "sign",
        )
    ]
    + [
        (AcceptanceLimits, dict(lower=0, upper=1), field)
        for field in ("lower", "upper")
    ]
    + [
        (
            AnalysisProject,
            dict(
                name="Fit",
                unit="mm",
                contributions=[dimension()],
                acceptance_limits=AcceptanceLimits(0, 1),
            ),
            field,
        )
        for field in ("name", "unit", "contributions")
    ],
)
def test_missing_fields_identified_by_constructor(constructor, fields, missing):
    fields = fields.copy()
    del fields[missing]
    with pytest.raises(TypeError, match=missing):
        constructor(**fields)
