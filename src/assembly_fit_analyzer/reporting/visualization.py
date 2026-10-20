"""Small vector interval figure; float conversion is restricted to page coordinates."""

from decimal import Decimal
from fractions import Fraction

from reportlab.lib import colors
from reportlab.platypus import Flowable

from assembly_fit_analyzer.calculations import WorstCaseResult


class IntervalFigure(Flowable):
    """Result snapshot drawn on a normalized signed axis, without new formulas."""

    def __init__(self, result: WorstCaseResult, width: float, font: str):
        super().__init__()
        self.result = result
        self.width, self.height = width, 133
        self.font = font
        values = (
            result.minimum,
            result.maximum,
            result.nominal,
            *(
                (result.acceptance_limits.lower, result.acceptance_limits.upper)
                if result.acceptance_limits is not None
                else ()
            ),
        )
        self.supported = all(
            abs(value.adjusted()) <= 10_000
            and abs(int(value.as_tuple().exponent)) <= 10_000
            for value in values
        )
        if self.supported:
            self.low, self.high = min(values), max(values)
            self.origin = Fraction(self.low)
            self.span = Fraction(self.high) - self.origin

    def draw(self):
        canvas = self.canv
        result = self.result
        start, width = 132, self.width - 147

        def x(value: Decimal) -> float:
            ratio = (
                float((Fraction(value) - self.origin) / self.span) if self.span else 0.5
            )
            return start + width * ratio

        canvas.setFont(self.font, 8)
        canvas.setFillColor(colors.HexColor("#31445a"))
        canvas.drawString(0, 106, "Functional interval")
        if result.acceptance_limits is None:
            canvas.drawString(start, 106, "Not provided — no assessment")
        canvas.drawString(0, 64, "Calculated interval")
        canvas.drawString(0, 22, "Nominal marker")
        if self.low <= 0 <= self.high:
            canvas.setStrokeColor(colors.HexColor("#68758a"))
            canvas.setLineWidth(0.5)
            canvas.setDash(3, 3)
            canvas.line(x(Decimal(0)), 14, x(Decimal(0)), 123)
            canvas.drawCentredString(x(Decimal(0)), 126, "Zero")
            canvas.setDash()
        bands = []
        if result.acceptance_limits is not None:
            bands.append(
                (
                    result.acceptance_limits.lower,
                    result.acceptance_limits.upper,
                    109,
                    "#b9cadf",
                )
            )
        bands.append(
            (
                result.minimum,
                result.maximum,
                67,
                "#203b60"
                if result.passes is None
                else "#087f72"
                if result.passes
                else "#b43e37",
            )
        )
        for lower, upper, y, color in bands:
            canvas.setStrokeColor(colors.HexColor(color))
            canvas.setFillColor(colors.HexColor(color))
            canvas.setLineWidth(7)
            canvas.line(x(lower), y, x(upper), y)
            canvas.circle(x(lower), y, 3, fill=1, stroke=0)
            canvas.circle(x(upper), y, 3, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#203b60"))
        canvas.circle(x(result.nominal), 25, 4, fill=1, stroke=0)
