"""Exact deterministic interval analysis for independently attainable 1D lengths."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, DecimalException, localcontext

from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.domain.models import validate_contributions
from assembly_fit_analyzer.validation import (
    DecimalInput,
    ValidationError,
    parse_decimal,
)

# Calculation resource policy, independent of domain input parsing. Precision
# includes alignment, preserved trailing zeros, and carry digits for 2N terms.
MAX_WORKING_PRECISION = 10_000
MAX_ABS_EXPONENT = 10_000


class CalculationError(ArithmeticError):
    """Exact arithmetic exceeds the engine's supported resource envelope."""


@dataclass(frozen=True, slots=True)
class ContributionTrace:
    """Original immutable input plus physical and signed contribution limits."""

    dimension: DimensionContribution
    minimum: Decimal
    maximum: Decimal
    nominal_contribution: Decimal
    minimum_contribution: Decimal
    maximum_contribution: Decimal


@dataclass(frozen=True, slots=True)
class WorstCaseResult:
    """Unrounded outputs and the immutable inputs needed to reproduce them."""

    nominal: Decimal
    minimum: Decimal
    maximum: Decimal
    passes: bool | None
    traces: tuple[ContributionTrace, ...] = ()
    acceptance_limits: AcceptanceLimits | None = None
    project: AnalysisProject | None = None


def _working_context(contributions: tuple[DimensionContribution, ...]) -> Context:
    lowest_exponent = MAX_ABS_EXPONENT
    highest_adjusted = -MAX_ABS_EXPONENT
    for dimension in contributions:
        for field in ("nominal", "lower_deviation", "upper_deviation"):
            value = getattr(dimension, field)
            # Finite values are guaranteed by the immutable domain model.
            exponent = int(value.as_tuple().exponent)
            adjusted = value.adjusted()
            if abs(exponent) > MAX_ABS_EXPONENT or abs(adjusted) > MAX_ABS_EXPONENT:
                raise CalculationError(
                    f"dimension {dimension.dimension_id!r}: {field}: decimal exponent "
                    f"exceeds supported +/-{MAX_ABS_EXPONENT} range"
                )
            lowest_exponent = min(lowest_exponent, exponent)
            highest_adjusted = max(highest_adjusted, adjusted)
    # Each endpoint sum contains at most 2N original operands. Allow enough
    # carry digits for their absolute sum, even before cancellation occurs.
    precision = max(1, highest_adjusted - lowest_exponent + 1) + len(
        str(2 * len(contributions))
    )
    if precision > MAX_WORKING_PRECISION:
        raise CalculationError(
            f"contributions: exact arithmetic requires {precision} working digits; "
            f"supported maximum is {MAX_WORKING_PRECISION}"
        )
    context = Context(
        prec=precision,
        Emin=-MAX_ABS_EXPONENT,
        Emax=MAX_ABS_EXPONENT,
        rounding=ROUND_HALF_EVEN,
        capitals=1,
        clamp=0,
    )
    # Never inherit caller precision, rounding behavior, traps, or flags.
    # Any rounding (even trailing-zero removal) or range failure is explicit.
    for signal in context.traps:
        context.traps[signal] = True
    context.clear_flags()
    return context


def _calculate_chain(
    contributions: tuple[DimensionContribution, ...],
) -> tuple[Decimal, Decimal, Decimal, tuple[ContributionTrace, ...]]:
    traces = []
    nominal = minimum = maximum = Decimal(0)
    try:
        with localcontext(_working_context(contributions)):
            for dimension in contributions:
                low = dimension.nominal + dimension.lower_deviation
                high = dimension.nominal + dimension.upper_deviation
                if dimension.sign == 1:
                    signed_nominal = dimension.nominal
                    signed_low, signed_high = low, high
                else:
                    signed_nominal = dimension.nominal.copy_negate()
                    signed_low, signed_high = high.copy_negate(), low.copy_negate()
                traces.append(
                    ContributionTrace(
                        dimension, low, high, signed_nominal, signed_low, signed_high
                    )
                )
                nominal += signed_nominal
                minimum += signed_low
                maximum += signed_high
    except DecimalException as exc:
        raise CalculationError(
            "contributions: exact Decimal arithmetic failed within supported limits"
        ) from exc
    if not all(value.is_finite() for value in (nominal, minimum, maximum)):
        raise CalculationError("contributions: nonfinite calculated result")
    if minimum > maximum:
        raise CalculationError("contributions: calculated minimum exceeds maximum")
    return nominal, minimum, maximum, tuple(traces)


def calculate_nominal(contributions: Sequence[DimensionContribution]) -> Decimal:
    """Calculate the exact signed nominal sum for a validated nonempty chain."""
    return _calculate_chain(validate_contributions(contributions))[0]


def calculate_minimum(contributions: Sequence[DimensionContribution]) -> Decimal:
    """Use positive lower limits and negated negative upper limits."""
    return _calculate_chain(validate_contributions(contributions))[1]


def calculate_maximum(contributions: Sequence[DimensionContribution]) -> Decimal:
    """Use positive upper limits and negated negative lower limits."""
    return _calculate_chain(validate_contributions(contributions))[2]


def meets_acceptance_limits(
    minimum: DecimalInput,
    maximum: DecimalInput,
    lower_limit: DecimalInput,
    upper_limit: DecimalInput,
) -> bool:
    """Validate intervals and check full containment with inclusive comparisons."""
    minimum = parse_decimal(minimum, field="minimum")
    maximum = parse_decimal(maximum, field="maximum")
    if minimum > maximum:
        raise ValidationError("minimum", "must be <= maximum")
    limits = AcceptanceLimits(lower_limit, upper_limit)
    return _within_limits(minimum, maximum, limits)


def _within_limits(
    minimum: Decimal, maximum: Decimal, limits: AcceptanceLimits
) -> bool:
    return minimum >= limits.lower and maximum <= limits.upper


def _analyze(
    contributions: tuple[DimensionContribution, ...],
    limits: AcceptanceLimits | None,
    project: AnalysisProject | None = None,
) -> WorstCaseResult:
    nominal, minimum, maximum, traces = _calculate_chain(contributions)
    return WorstCaseResult(
        nominal=nominal,
        minimum=minimum,
        maximum=maximum,
        passes=_within_limits(minimum, maximum, limits) if limits is not None else None,
        traces=traces,
        acceptance_limits=limits,
        project=project,
    )


def analyze_project(project: AnalysisProject) -> WorstCaseResult:
    """Analyze a validated project, retaining its units and immutable snapshot."""
    if not isinstance(project, AnalysisProject):
        raise ValidationError("project", "must be an AnalysisProject")
    return _analyze(project.contributions, project.acceptance_limits, project)


def analyze_worst_case(
    contributions: Sequence[DimensionContribution],
    lower_limit: DecimalInput,
    upper_limit: DecimalInput,
) -> WorstCaseResult:
    """Compatibility API for unit-consistent chains without project metadata.

    Prefer analyze_project when project identity and units are available.
    """
    items = validate_contributions(contributions)
    limits = AcceptanceLimits(lower_limit, upper_limit)
    return _analyze(items, limits)
