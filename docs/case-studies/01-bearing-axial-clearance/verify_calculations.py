"""Reproduce the draft study with an independent exact-rational corner oracle.

Run from the repository root with the existing package installed. This is a
documentation calculation worksheet, not a new application calculation API.
No acceptance interval, project JSON, PDF, or operating verdict is invented.
"""

from fractions import Fraction
from itertools import product

from assembly_fit_analyzer.calculations import (
    calculate_maximum,
    calculate_minimum,
    calculate_nominal,
)
from assembly_fit_analyzer.domain import DimensionContribution

# Each tuple: ID, nominal mm, lower deviation mm, upper deviation mm, sign.
# H: proposed stop spacing; W: selected SKF Explorer catalogue outer-ring width;
# P: separately assumed cold left gap, not measured or released drawing data.
Row = tuple[str, str, str, str, int]
BASE_H: Row = ("H", "14.500", "-0.100", "0.100", 1)
ALT_H: Row = ("H", "14.700", "-0.100", "0.100", 1)
WIDTH: Row = ("W", "14.000", "-0.060", "0.000", -1)
POSITION: Row = ("P", "0.200", "-0.050", "0.050", -1)


def reference(rows: tuple[Row, ...]) -> tuple[Fraction, Fraction, Fraction, int]:
    """Enumerate actual physical endpoints, independently of engine rules."""
    endpoints = []
    signs = []
    nominal = Fraction(0)
    for _, n, lower, upper, sign in rows:
        dimension = Fraction(n)
        bounds = (dimension + Fraction(lower), dimension + Fraction(upper))
        assert 0 <= bounds[0] <= bounds[1]
        nominal += sign * dimension
        endpoints.append(bounds)
        signs.append(sign)
    values = [
        sum((s * x for s, x in zip(signs, corner, strict=True)), Fraction(0))
        for corner in product(*endpoints)
    ]
    return min(values), nominal, max(values), len(values)


def millimetres(value: Fraction) -> str:
    """Print our exact millimetre values using integer micrometres, never float."""
    micrometres = value * 1_000
    assert micrometres.denominator == 1
    integer = micrometres.numerator
    sign = "-" if integer < 0 else ""
    whole, remainder = divmod(abs(integer), 1_000)
    return f"{sign}{whole}.{remainder:03d}"


def main() -> None:
    cases = (
        ("Original total C", (BASE_H, WIDTH), ("0.400", "0.500", "0.660")),
        ("Alternative total C", (ALT_H, WIDTH), ("0.600", "0.700", "0.860")),
        (
            "Original right gap",
            (BASE_H, WIDTH, POSITION),
            ("0.150", "0.300", "0.510"),
        ),
        (
            "Alternative right gap",
            (ALT_H, WIDTH, POSITION),
            ("0.350", "0.500", "0.710"),
        ),
        (
            "Left gap (assumed)",
            (("P", "0.200", "-0.050", "0.050", 1),),
            ("0.150", "0.200", "0.250"),
        ),
    )
    corner_count = 0
    for name, rows, expected in cases:
        minimum, nominal, maximum, count = reference(rows)
        oracle = minimum, nominal, maximum
        assert oracle == tuple(map(Fraction, expected)), name
        dimensions = tuple(
            DimensionContribution(i, i, n, lower, upper, sign)
            for i, n, lower, upper, sign in rows
        )
        actual = (
            calculate_minimum(dimensions),
            calculate_nominal(dimensions),
            calculate_maximum(dimensions),
        )
        assert tuple(map(Fraction, actual)) == oracle, name
        corner_count += count
        print(f"{name}: min / nominal / max = {' / '.join(expected)} mm")

    # Check the shared-position identity at all actual H/W/P corners. Independent
    # minima of left and right gaps cannot be added as if they were independent.
    for h, w, p in product(
        map(Fraction, ("14.400", "14.600")),
        map(Fraction, ("13.940", "14.000")),
        map(Fraction, ("0.150", "0.250")),
    ):
        assert p + (h - w - p) == h - w
        assert p > 0 and h - w - p > 0

    alpha, length = Fraction("0.000012"), Fraction("150")
    shaft_growth = alpha * length * (80 - 20)
    housing_growth = alpha * length * (50 - 20)
    delta = shaft_growth - housing_growth
    assert (shaft_growth, housing_growth, delta) == tuple(
        map(Fraction, ("0.108", "0.054", "0.054"))
    )
    print("Uniform station expansion: shaft 0.108; housing 0.054; difference +0.054 mm")

    # Conditional face movement only: Delta P = delta, Delta H = Delta W = 0.
    # These are not qualified hot clearances or functional acceptance limits.
    for name, rows, expected in (
        ("Original", (BASE_H, WIDTH, POSITION), ("0.096", "0.246", "0.456")),
        ("Alternative", (ALT_H, WIDTH, POSITION), ("0.296", "0.446", "0.656")),
    ):
        cold = reference(rows)[:3]
        hot = tuple(value - delta for value in cold)
        assert hot == tuple(map(Fraction, expected))
        print(f"{name} conditional right gap: {' / '.join(expected)} mm")
    left = tuple(Fraction(value) + delta for value in ("0.150", "0.200", "0.250"))
    assert left == tuple(map(Fraction, ("0.204", "0.254", "0.304")))

    total = Fraction("14.500") - Fraction("14.000")
    right = total - Fraction("0.480")
    assert (total, right, right - delta) == tuple(
        map(Fraction, ("0.500", "0.020", "-0.034"))
    )
    print(
        f"Position counterexample: total {millimetres(total)}; "
        f"cold right {millimetres(right)}; moved right {millimetres(right - delta)} mm"
    )
    print(
        f"Verified 5 chains / {corner_count} corners against the existing engine; "
        "thermal arithmetic, shared-P identity and counterexample verified."
    )
    print("Draft only: no functional Pass/Fail, JSON project, or PDF generated.")


if __name__ == "__main__":
    main()
