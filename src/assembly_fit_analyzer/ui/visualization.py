"""Presentation-only SVG. Engineering outputs are never derived from coordinates."""

from decimal import MAX_EMAX, MIN_EMIN, Context, Decimal, localcontext
from fractions import Fraction
from html import escape

from assembly_fit_analyzer.calculations import WorstCaseResult


def compact(value: Decimal) -> str:
    """Bound label length; the UI separately exposes exact Decimal strings."""
    text = str(value)
    return text if len(text) <= 18 else format(value, ".8E")


def interval_svg(result: WorstCaseResult) -> str | None:
    """Compare intervals on one normalized axis, preserving exact input decisions.

    Rational offsets are converted to bounded floats solely for SVG coordinates.
    If compact absolute labels collide, use exact offsets from nominal instead.
    The isolated context used for offset labels never affects engine arithmetic.
    """
    limits = result.acceptance_limits
    values = (
        result.minimum,
        result.maximum,
        result.nominal,
        *((limits.lower, limits.upper) if limits is not None else ()),
    )
    if any(
        abs(value.adjusted()) > 10_000 or abs(int(value.as_tuple().exponent)) > 10_000
        for value in values
    ):
        return None
    low, high = min(values), max(values)
    origin = Fraction(low)
    span = Fraction(high) - origin
    # Give all boundary markers breathing room, including a zero-width interval.
    padding = span / 16 if span else (abs(origin) / 16 if origin else Fraction(1))
    axis_low, axis_span = origin - padding, span + 2 * padding

    def position(value: Decimal) -> float:
        return 44 + 872 * float((Fraction(value) - axis_low) / axis_span)

    def x(value: Decimal) -> str:
        return f"{position(value):.3f}"

    offset_labels = any(
        left != right and compact(left) == compact(right)
        for left in values
        for right in values
    )
    precision = (
        max(value.adjusted() for value in values)
        - min(int(value.as_tuple().exponent) for value in values)
        + 3
    )

    def label(value: Decimal) -> str:
        if not offset_labels:
            return escape(compact(value))
        # Only presentation labels use this context. Enough digits are provided
        # for exact subtraction before compact formatting; no engineering values
        # or acceptance decisions are derived from these labels.
        with localcontext(
            Context(prec=max(1, precision), Emax=MAX_EMAX, Emin=MIN_EMIN)
        ):
            offset = value - result.nominal
        text = compact(offset)
        return escape(("+" if offset > 0 else "") + text)

    def text(value: Decimal, y: int, content: str, color: str = "#31445a") -> str:
        px = position(value)
        anchor = "start" if px < 360 else "end" if px > 600 else "middle"
        return (
            f'<text x="{px:.3f}" y="{y}" text-anchor="{anchor}" '
            f'fill="{color}">{content}</text>'
        )

    bands = [
        '<rect x="44" y="100" width="872" height="94" rx="5" fill="#f1f4f8"/>',
    ]
    if limits is not None:
        lower_x, upper_x = position(limits.lower), position(limits.upper)
        bands.append(
            f'<rect data-region="allowed" x="{lower_x:.3f}" y="100" '
            f'width="{max(0, upper_x - lower_x):.3f}" height="94" fill="#e0eeeb"/>'
        )
    if limits is not None and low < limits.lower:
        bands.append(
            f'<rect data-region="below-limit" x="44" y="100" '
            f'width="{lower_x - 44:.3f}" height="94" fill="#fbe7e5"/>'
        )
    if limits is not None and high > limits.upper:
        bands.append(
            f'<rect data-region="above-limit" x="{upper_x:.3f}" y="100" '
            f'width="{916 - upper_x:.3f}" height="94" fill="#fbe7e5"/>'
        )

    def segment(start: Decimal, end: Decimal, color: str, kind: str) -> str:
        return (
            f'<line data-segment="{kind}" x1="{x(start)}" x2="{x(end)}" '
            f'y1="157" y2="157" stroke="{color}" stroke-width="10" '
            'stroke-linecap="round"/>'
        )

    segments = [
        segment(
            result.minimum,
            result.maximum,
            "#203b60" if limits is None else "#087f72",
            "calculated",
        )
    ]
    if limits is not None and result.minimum < limits.lower:
        segments.append(
            segment(
                result.minimum,
                min(result.maximum, limits.lower),
                "#b43e37",
                "below-limit",
            )
        )
    if limits is not None and result.maximum > limits.upper:
        segments.append(
            segment(
                max(result.minimum, limits.upper),
                result.maximum,
                "#b43e37",
                "above-limit",
            )
        )
    zero = ""
    if low <= 0 <= high:
        zero = (
            f'<line x1="{x(Decimal(0))}" x2="{x(Decimal(0))}" '
            'y1="94" y2="202" stroke="#4e5d73" stroke-dasharray="3 4"/>'
            + text(
                Decimal(0), 218, "Absolute zero" if offset_labels else "Zero", "#4e5d73"
            )
        )
    unit = result.project.unit if result.project else "project units"
    title = "Offsets from nominal" if offset_labels else "Signed chain position"
    boundaries = ""
    legend = (
        '<text x="24" y="295" font-size="11">'
        "No functional acceptance limits provided</text>"
    )
    if limits is not None:
        boundaries = f'''<line x1="{x(limits.lower)}" x2="{x(limits.lower)}"
              y1="62" y2="194"
              stroke="#6383a2" stroke-dasharray="5 4"/>
        <line x1="{x(limits.upper)}" x2="{x(limits.upper)}" y1="86" y2="194"
              stroke="#6383a2" stroke-dasharray="5 4"/>
        {text(limits.lower, 54, "Lower limit " + label(limits.lower))}
        {text(limits.upper, 79, "Upper limit " + label(limits.upper))}'''
        legend = """<rect x="24" y="286" width="10" height="10" fill="#e0eeeb"/>
        <text x="40" y="295" font-size="11">Allowed interval (inclusive)</text>
        <rect x="260" y="286" width="10" height="10" fill="#fbe7e5"/>
        <text x="276" y="295" font-size="11">Outside functional limits</text>"""
    figure_title = (
        "Worst-case interval and inclusive functional limits"
        if limits is not None
        else "Worst-case interval — no functional acceptance assessment"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 306"
        role="img" aria-label="Functional and calculated interval endpoints"
        style="width:100%;height:auto;background:#fff;border-radius:8px">
        <title>{figure_title}</title>
        <g font-family="system-ui,sans-serif" font-size="13" fill="#31445a">
        <text x="24" y="25" font-weight="600">{title} · {escape(unit)}</text>
        {"".join(bands)}
        {zero}
        {boundaries}
        {text(result.nominal, 122, "Nominal " + label(result.nominal), "#203b60")}
        {"".join(segments)}
        <circle cx="{x(result.minimum)}" cy="157" r="5" fill="#203b60"/>
        <circle cx="{x(result.maximum)}" cy="157" r="5" fill="#203b60"/>
        <path d="M {x(result.nominal)} 146 l 7 11 l -7 11 l -7 -11 Z" fill="#203b60"/>
        <line x1="{x(result.minimum)}" x2="{x(result.minimum)}"
              y1="164" y2="228" stroke="#8b99ab"/>
        <line x1="{x(result.maximum)}" x2="{x(result.maximum)}"
              y1="164" y2="254" stroke="#8b99ab"/>
        {text(result.minimum, 244, "Minimum " + label(result.minimum))}
        {text(result.maximum, 270, "Maximum " + label(result.maximum))}
        {legend}
        </g></svg>'''
