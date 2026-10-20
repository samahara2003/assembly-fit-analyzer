"""Engineering examples, independent endpoint oracles, and numeric safeguards."""

from dataclasses import FrozenInstanceError
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, Inexact, localcontext
from fractions import Fraction
from itertools import permutations, product

import pytest

from assembly_fit_analyzer.calculations import (
    CalculationError,
    analyze_project,
    analyze_worst_case,
    calculate_maximum,
    calculate_minimum,
    calculate_nominal,
    meets_acceptance_limits,
)
from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.validation import ValidationError


def example_project(lower="5.8", upper="6.5", unit="mm"):
    return AnalysisProject(
        "Specification example",
        unit,
        [
            DimensionContribution("A", "Housing", "10", "-0.1", "0.2", 1),
            DimensionContribution("B", "Insert", "4", "-0.3", "0.1", -1),
        ],
        AcceptanceLimits(lower, upper),
    )


def outputs(result):
    return result.nominal, result.minimum, result.maximum, result.passes


@pytest.mark.parametrize("unit", ["mm", "in"])
def test_project_api_and_full_trace(unit):
    project = example_project(unit=unit)
    result = analyze_project(project)
    assert outputs(result) == (Decimal("6"), Decimal("5.8"), Decimal("6.5"), True)
    assert result.project is project
    assert result.project.unit == unit
    assert result.acceptance_limits is project.acceptance_limits
    assert isinstance(result.traces, tuple)
    assert [trace.dimension.dimension_id for trace in result.traces] == ["A", "B"]
    first, second = result.traces
    assert first.dimension is project.contributions[0]
    assert first.dimension.label == "Housing"
    assert first.dimension.lower_deviation == Decimal("-0.1")
    assert first.dimension.upper_deviation == Decimal("0.2")
    assert (first.minimum, first.maximum) == (Decimal("9.9"), Decimal("10.2"))
    assert (
        first.nominal_contribution,
        first.minimum_contribution,
        first.maximum_contribution,
    ) == (Decimal("10"), Decimal("9.9"), Decimal("10.2"))
    assert (second.minimum, second.maximum) == (Decimal("3.7"), Decimal("4.1"))
    assert (
        second.nominal_contribution,
        second.minimum_contribution,
        second.maximum_contribution,
    ) == (Decimal("-4"), Decimal("-4.1"), Decimal("-3.7"))
    for field, trace_field in (
        ("nominal", "nominal_contribution"),
        ("minimum", "minimum_contribution"),
        ("maximum", "maximum_contribution"),
    ):
        assert getattr(result, field) == sum(
            getattr(trace, trace_field) for trace in result.traces
        )


@pytest.mark.parametrize(
    ("lower", "upper", "passes"),
    [
        ("5.8", "6.5", True),
        ("0", "100", True),
        ("5.9", "6.5", False),
        ("5.8", "6.4", False),
        ("6", "6", False),
        ("0", "5", False),
        ("7", "8", False),
        ("5.800000000000000000000000000001", "6.5", False),
        ("5.8", "6.499999999999999999999999999999", False),
    ],
)
def test_full_interval_acceptance_without_rounding_or_epsilon(lower, upper, passes):
    assert analyze_project(example_project(lower, upper)).passes is passes


@pytest.mark.parametrize(
    ("lower", "upper", "low", "high"),
    [
        ("-0.1", "0.1", "9.9", "10.1"),
        ("-0.3", "0.2", "9.7", "10.2"),
        ("0", "0.2", "10", "10.2"),
        ("-0.3", "0", "9.7", "10"),
        ("0.1", "0.2", "10.1", "10.2"),
        ("-0.3", "-0.1", "9.7", "9.9"),
        ("0", "0", "10", "10"),
        ("0.2", "0.2", "10.2", "10.2"),
        ("-10", "-10", "0", "0"),
    ],
)
@pytest.mark.parametrize("sign", [-1, 1])
def test_single_dimension_tolerance_forms(lower, upper, low, high, sign):
    item = DimensionContribution("A", "Part", "10", lower, upper, sign)
    expected_min = Decimal(low) if sign == 1 else Decimal(high).copy_negate()
    expected_max = Decimal(high) if sign == 1 else Decimal(low).copy_negate()
    result = analyze_worst_case([item], expected_min, expected_max)
    assert outputs(result) == (Decimal(10 * sign), expected_min, expected_max, True)
    # Same-side deviations may put nominal outside the permitted interval.
    assert result.project is None


def test_negative_gaps_are_preserved_and_can_pass():
    project = AnalysisProject(
        "Interference",
        "mm",
        [
            DimensionContribution("H", "Hole", "10", "-0.1", "0.1", 1),
            DimensionContribution("S", "Shaft", "11", "-0.2", "0.2", -1),
        ],
        AcceptanceLimits("-1.3", "-0.7"),
    )
    assert outputs(analyze_project(project)) == (
        Decimal("-1"),
        Decimal("-1.3"),
        Decimal("-0.7"),
        True,
    )


def test_possible_interference_with_nominal_pass_still_fails():
    item = DimensionContribution("A", "Part", "0.1", "-0.1", "0.2", -1)
    result = analyze_worst_case([item], "-0.1", 0)
    assert outputs(result) == (Decimal("-0.1"), Decimal("-0.3"), Decimal(0), False)


@pytest.mark.parametrize("sign", [-1, 1])
def test_zero_length_zero_tolerance_and_point_acceptance(sign):
    item = DimensionContribution("Z", "Zero", 0, 0, 0, sign)
    result = analyze_worst_case((item,), 0, 0)
    assert outputs(result) == (Decimal(0), Decimal(0), Decimal(0), True)


@pytest.mark.parametrize("signs", list(product((-1, 1), repeat=4)))
def test_mixed_signs_against_independent_fraction_endpoint_enumeration(signs):
    data = [
        ("10.01", "-0.03", "0.02"),
        ("4.11", "0", "0.04"),
        ("2.05", "-0.02", "0"),
        ("1.07", "0.01", "0.03"),
    ]
    items = tuple(
        DimensionContribution(str(index), "Part", *values, sign)
        for index, (values, sign) in enumerate(zip(data, signs, strict=True))
    )
    endpoints = [
        (
            Fraction(item.nominal) + Fraction(item.lower_deviation),
            Fraction(item.nominal) + Fraction(item.upper_deviation),
        )
        for item in items
    ]
    corners = [
        sum(sign * value for sign, value in zip(signs, corner, strict=True))
        for corner in product(*endpoints)
    ]
    expected_nominal = sum(Fraction(item.nominal) * item.sign for item in items)
    result = analyze_worst_case(items, -100, 100)
    assert result.nominal == expected_nominal
    assert result.minimum == min(corners)
    assert result.maximum == max(corners)
    assert result.passes


@pytest.mark.parametrize("precision", [1, 2, 28, 100])
@pytest.mark.parametrize("rounding", [ROUND_FLOOR, ROUND_CEILING])
def test_precision_cancellation_context_isolation_and_repeatability(
    precision, rounding
):
    whole = "1" + "0" * 80
    items = (
        DimensionContribution(
            "A", "Large", whole + "." + "0" * 29 + "1", "-1e-31", "2e-31", 1
        ),
        DimensionContribution("B", "Large subtraction", whole, 0, 0, -1),
    )
    project = AnalysisProject(
        "Precision", "mm", items, AcceptanceLimits("9e-31", "1.2e-30")
    )
    with localcontext() as context:
        context.prec = precision
        context.rounding = rounding
        context.Emin = -2
        context.Emax = 2
        context.clamp = 1
        for signal in context.traps:
            context.traps[signal] = False
        context.flags[Inexact] = True
        before = context.copy()
        first = analyze_project(project)
        assert outputs(first) == (
            Decimal("1e-30"),
            Decimal("9e-31"),
            Decimal("1.2e-30"),
            True,
        )
        assert analyze_project(project) == first
        assert context.prec == before.prec
        assert context.rounding == before.rounding
        assert (context.Emin, context.Emax, context.clamp) == (
            before.Emin,
            before.Emax,
            before.clamp,
        )
        assert context.flags == before.flags
        assert context.traps == before.traps
        assert calculate_nominal(items) == first.nominal
        assert calculate_minimum(items) == first.minimum
        assert calculate_maximum(items) == first.maximum


def test_all_decimal_traps_enabled_in_calling_context():
    with localcontext() as context:
        context.prec = 1
        for signal in context.traps:
            context.traps[signal] = True
        assert analyze_project(example_project()).passes
        assert not any(context.flags.values())


def test_carry_digits_and_permutation_invariance():
    items = tuple(
        DimensionContribution(str(i), "Part", "9.99", "-0.01", "0.01", 1)
        for i in range(100)
    )
    assert outputs(analyze_worst_case(items, "998", "1000")) == (
        Decimal("999"),
        Decimal("998"),
        Decimal("1000"),
        True,
    )
    mixed = (
        DimensionContribution("A", "Large", "1e80", 0, 0, 1),
        DimensionContribution("B", "Small", "1e-30", 0, 0, 1),
        DimensionContribution("C", "Subtract", "1e80", 0, 0, -1),
    )
    for ordering in permutations(mixed):
        assert outputs(analyze_worst_case(ordering, "1e-30", "1e-30")) == (
            Decimal("1e-30"),
            Decimal("1e-30"),
            Decimal("1e-30"),
            True,
        )


def test_trace_and_result_are_immutable():
    result = analyze_project(example_project())
    with pytest.raises(FrozenInstanceError):
        result.minimum = Decimal(0)
    with pytest.raises(FrozenInstanceError):
        result.traces[0].minimum = Decimal(0)


@pytest.mark.parametrize("value", [None, {}, (), "project", True])
def test_project_entry_rejects_wrong_types(value):
    with pytest.raises(ValidationError, match="project"):
        analyze_project(value)


@pytest.mark.parametrize(
    "function",
    [calculate_nominal, calculate_minimum, calculate_maximum, analyze_worst_case],
)
@pytest.mark.parametrize("chain", [(), None, "chain", [{}]])
def test_all_chain_entries_reuse_domain_validation(function, chain):
    args = (chain, 0, 1) if function is analyze_worst_case else (chain,)
    with pytest.raises(ValidationError, match="contributions"):
        function(*args)


@pytest.mark.parametrize(
    "function",
    [calculate_nominal, calculate_minimum, calculate_maximum, analyze_worst_case],
)
def test_all_chain_entries_reject_duplicate_ids(function):
    item = example_project().contributions[0]
    args = ([item, item], 0, 1) if function is analyze_worst_case else ([item, item],)
    with pytest.raises(ValidationError, match="duplicate ID") as caught:
        function(*args)
    assert caught.value.dimension_id == "A"


@pytest.mark.parametrize("value", [True, 0.1, None, "NaN", Decimal("sNaN"), "Infinity"])
@pytest.mark.parametrize("field", ["minimum", "maximum", "lower_limit", "upper_limit"])
def test_acceptance_helper_rejects_invalid_numbers(value, field):
    values = dict(minimum=0, maximum=1, lower_limit=0, upper_limit=1)
    values[field] = value
    with pytest.raises(ValidationError):
        meets_acceptance_limits(**values)


@pytest.mark.parametrize("bounds", [(2, 1, 0, 3), (0, 1, 3, 2)])
def test_acceptance_helper_rejects_reversed_intervals(bounds):
    with pytest.raises(ValidationError):
        meets_acceptance_limits(*bounds)


@pytest.mark.parametrize("lower", [True, 0.1, None, "NaN", "Infinity", "7"])
def test_legacy_analysis_rejects_invalid_acceptance_limits(lower):
    with pytest.raises(ValidationError):
        analyze_worst_case(example_project().contributions, lower, "6.5")


@pytest.mark.parametrize(
    ("nominal", "lower", "upper", "message"),
    [
        ("1e10001", "0", "0", "nominal"),
        ("1", "0", "1e-10001", "upper_deviation"),
        ("1e5000", "0", "1e-5000", "working digits"),
        ("9e10000", "0e10000", "9e10000", "arithmetic failed"),
    ],
)
def test_explicit_resource_errors_instead_of_rounded_or_nonfinite_results(
    nominal, lower, upper, message
):
    item = DimensionContribution("A", "Extreme", nominal, lower, upper, 1)
    with pytest.raises(CalculationError, match=message):
        analyze_worst_case([item], 0, "1e10002")


def test_supported_precision_boundary():
    # 9,999 aligned places + one carry place: exactly 10,000 working digits.
    item = DimensionContribution("A", "Boundary", "1e4999", 0, "1e-4999", 1)
    result = analyze_worst_case([item], 0, "1e5000")
    assert Fraction(result.maximum) == Fraction("1e4999") + Fraction("1e-4999")
    assert result.passes
