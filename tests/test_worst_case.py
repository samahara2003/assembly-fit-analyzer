from decimal import Decimal

import pytest

from assembly_fit_analyzer.calculations.worst_case import (
    analyze_worst_case,
    calculate_maximum,
    calculate_minimum,
    calculate_nominal,
    meets_acceptance_limits,
)
from assembly_fit_analyzer.domain import DimensionContribution
from assembly_fit_analyzer.validation import ValidationError


def test_worst_case_calculations():
    housing = DimensionContribution("D1", "Housing", "60.50", "-0.10", "0.10", 1)
    part_a = DimensionContribution("D2", "Part A", "20.00", "-0.10", "0.10", -1)
    part_b = DimensionContribution("D3", "Part B", "25.00", "-0.05", "0.05", -1)
    part_c = DimensionContribution("D4", "Part C", "15.00", "-0.05", "0.05", -1)

    dimensions = (housing, part_a, part_b, part_c)

    assert calculate_nominal(dimensions) == Decimal("0.50")
    assert calculate_minimum(dimensions) == Decimal("0.20")
    assert calculate_maximum(dimensions) == Decimal("0.80")


def test_possible_interference():
    housing = DimensionContribution("D1", "Housing", "60.50", "-0.10", "0.10", 1)
    part_a = DimensionContribution("D2", "Part A", "20.30", "-0.10", "0.10", -1)
    part_b = DimensionContribution("D3", "Part B", "25.00", "-0.05", "0.05", -1)
    part_c = DimensionContribution("D4", "Part C", "15.00", "-0.05", "0.05", -1)

    dimensions = (housing, part_a, part_b, part_c)

    assert calculate_nominal(dimensions) == Decimal("0.20")
    assert calculate_minimum(dimensions) == Decimal("-0.10")
    assert calculate_maximum(dimensions) == Decimal("0.50")


def test_acceptance_limits():
    assert (
        meets_acceptance_limits(
            Decimal("0.20"),
            Decimal("0.80"),
            Decimal("0.10"),
            Decimal("0.60"),
        )
        is False
    )

    assert (
        meets_acceptance_limits(
            Decimal("0.20"),
            Decimal("0.80"),
            Decimal("0.10"),
            Decimal("0.90"),
        )
        is True
    )


def test_complete_worst_case_analysis():
    housing = DimensionContribution("D1", "Housing", "60.50", "-0.10", "0.10", 1)
    part_a = DimensionContribution("D2", "Part A", "20.00", "-0.10", "0.10", -1)
    part_b = DimensionContribution("D3", "Part B", "25.00", "-0.05", "0.05", -1)
    part_c = DimensionContribution("D4", "Part C", "15.00", "-0.05", "0.05", -1)

    dimensions = (housing, part_a, part_b, part_c)

    result = analyze_worst_case(
        dimensions,
        Decimal("0.10"),
        Decimal("0.60"),
    )

    assert result.nominal == Decimal("0.50")
    assert result.minimum == Decimal("0.20")
    assert result.maximum == Decimal("0.80")
    assert result.passes is False


def test_exact_acceptance_boundaries():
    assert (
        meets_acceptance_limits(
            Decimal("0.20"),
            Decimal("0.80"),
            Decimal("0.20"),
            Decimal("0.80"),
        )
        is True
    )


def test_negative_dimension_is_rejected():
    with pytest.raises(ValidationError):
        DimensionContribution(
            "D1",
            "Invalid part",
            "-20.00",
            "-0.10",
            "0.10",
            1,
        )
