"""Auditable PDF layout built exclusively from verified engine results."""

from datetime import datetime, timezone
from decimal import Decimal, localcontext
from functools import lru_cache
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from io import BytesIO
from threading import RLock
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

from assembly_fit_analyzer.calculations import (
    CalculationError,
    ContributionTrace,
    WorstCaseResult,
    analyze_project,
)
from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.domain.interpretation import range_description
from assembly_fit_analyzer.persistence import dumps_project
from assembly_fit_analyzer.validation import ValidationError
from assembly_fit_analyzer.validation.resources import (
    MAX_PDF_DIMENSIONS,
    MAX_PDF_TEXT_CHARS,
    check_dimension_count,
    check_project_limits,
)

from .errors import ReportError
from .visualization import IntervalFigure

APP_NAME = "Assembly Fit & Tolerance Analyzer"
_FONT = "AssemblyVera"
_BOLD = "AssemblyVeraBold"
_INK = colors.HexColor("#1e3047")
_ACCENT = colors.HexColor("#087f72")
_WIDTH = A4[0] - 88
_RENDER_LOCK = RLock()


def _validate_result(result: WorstCaseResult) -> None:
    if not isinstance(result, WorstCaseResult):
        raise ReportError("analysis: expected a WorstCaseResult from analyze_project()")
    if not isinstance(result.project, AnalysisProject):
        raise ReportError(
            "analysis.project: missing validated project; use analyze_project()"
        )
    try:
        check_dimension_count(
            len(result.project.contributions), maximum=MAX_PDF_DIMENSIONS
        )
        check_project_limits(result.project)
    except ValidationError as exc:
        raise ReportError(f"PDF report limit: {exc}") from exc
    if result.acceptance_limits is None:
        if result.passes is not None:
            raise ReportError("analysis.passes: must be None without acceptance limits")
    elif not isinstance(result.acceptance_limits, AcceptanceLimits):
        raise ReportError(
            "analysis.acceptance_limits: expected AcceptanceLimits or None"
        )
    elif type(result.passes) is not bool:
        raise ReportError("analysis.passes: expected a boolean with acceptance limits")
    if not isinstance(result.traces, tuple) or not result.traces:
        raise ReportError(
            "analysis.traces: complete ordered contribution traces are required"
        )
    if len(result.traces) != len(result.project.contributions):
        raise ReportError(
            "analysis.traces: one trace per project dimension is required"
        )
    for field in ("nominal", "minimum", "maximum"):
        value = getattr(result, field)
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ReportError(f"analysis.{field}: expected a finite Decimal")
    for index, trace in enumerate(result.traces):
        if not isinstance(trace, ContributionTrace):
            raise ReportError(f"analysis.traces[{index}]: expected a ContributionTrace")
        if not isinstance(trace.dimension, DimensionContribution):
            raise ReportError(
                f"analysis.traces[{index}].dimension: expected a dimension"
            )
        for field in (
            "minimum",
            "maximum",
            "nominal_contribution",
            "minimum_contribution",
            "maximum_contribution",
        ):
            value = getattr(trace, field)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ReportError(
                    f"analysis.traces[{index}].{field}: expected finite Decimal"
                )
    _check_workload(result)
    # Output dataclasses are not input validators. Verify provenance/consistency
    # through the existing engine, never through independent reporting formulas.
    try:
        expected = analyze_project(result.project)
    except (CalculationError, ValueError) as exc:
        raise ReportError(
            f"analysis.project: cannot verify the analysis: {exc}"
        ) from exc
    if result != expected:
        raise ReportError(
            "analysis: values, acceptance, or traces disagree with the "
            "project; analyze again"
        )


def _check_workload(result: WorstCaseResult) -> None:
    """Count dynamic table/assessment text before engine verification or layout.

    Count repeated occurrences separately, including trace identifiers and totals.
    Fixed headings and boilerplate are bounded independently by the template.
    """
    project = result.project
    size = len(project.name)

    def include(value: object) -> None:
        nonlocal size
        size += len(str(value))
        if size > MAX_PDF_TEXT_CHARS:
            raise ReportError(
                f"PDF report workload exceeds {MAX_PDF_TEXT_CHARS} dynamic text "
                "characters; use JSON export or reduce the report size"
            )

    for value in (
        result.nominal,
        result.minimum,
        result.maximum,
        *(
            (result.acceptance_limits.lower, result.acceptance_limits.upper)
            if result.acceptance_limits is not None
            else ()
        ),
        result.minimum,
        result.nominal,
        result.maximum,
    ):
        include(value)
    for item in project.contributions:
        for value in (
            item.dimension_id,
            item.label,
            item.nominal,
            item.lower_deviation,
            item.upper_deviation,
            "+1" if item.sign == 1 else "-1",
        ):
            include(value)
    for trace in result.traces:
        for value in (
            trace.dimension.dimension_id,
            trace.minimum,
            trace.maximum,
            trace.minimum_contribution,
            trace.nominal_contribution,
            trace.maximum_contribution,
        ):
            include(value)


@lru_cache(maxsize=1)
def _fonts() -> frozenset[int]:
    directory = files("reportlab").joinpath("fonts")
    pdfmetrics.registerFont(
        TTFont(_FONT, BytesIO(directory.joinpath("Vera.ttf").read_bytes()))
    )
    pdfmetrics.registerFont(
        TTFont(_BOLD, BytesIO(directory.joinpath("VeraBd.ttf").read_bytes()))
    )
    pdfmetrics.registerFontFamily(
        _FONT, normal=_FONT, bold=_BOLD, italic=_FONT, boldItalic=_BOLD
    )
    return frozenset(pdfmetrics.getFont(_FONT).face.charWidths) & frozenset(
        pdfmetrics.getFont(_BOLD).face.charWidths
    )


def _check_text(text: str, field: str, supported: frozenset[int]) -> None:
    for char in text:
        if char in "\n\r\t":
            continue
        if ord(char) < 32 or ord(char) not in supported:
            raise ReportError(
                f"{field}: character U+{ord(char):04X} is unsupported by the embedded "
                "PDF font. Use supported text for the report; JSON inputs are "
                "unchanged."
            )


def _table(headers, rows, widths, cell_style, *, totals=False):
    def cell(value):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), cell_style)

    data = [[cell(value) for value in headers]] + [
        [cell(value) for value in row] for row in rows
    ]
    table = LongTable(
        data, colWidths=widths, repeatRows=1, splitByRow=1, splitInRow=1, hAlign="LEFT"
    )
    styles = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#ccd6e0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if totals:
        styles.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e0eeeb")))
    table.setStyle(TableStyle(styles))
    return table


def generate_pdf_report(
    result: WorstCaseResult, *, generated_at: datetime | None = None
) -> bytes:
    """Render a deterministic report with embedded fonts and exact numeric text."""
    _validate_result(result)
    if generated_at is not None and (
        not isinstance(generated_at, datetime) or generated_at.utcoffset() is None
    ):
        raise ReportError("generated_at: supply a timezone-aware datetime or None")
    # Decimal.__str__ capitalization is the only display context setting used.
    # No engineering arithmetic is performed inside this isolated context.
    try:
        # ReportLab's registered TrueType fonts have mutable subsetting state.
        # Serialize this library boundary across local Streamlit sessions.
        with _RENDER_LOCK, localcontext(capitals=1):
            return _render(result, generated_at)
    except ReportError:
        raise
    except Exception as exc:
        raise ReportError(f"PDF generation failed: {exc}") from exc


def _render(result: WorstCaseResult, generated_at: datetime | None) -> bytes:
    supported = _fonts()
    project = result.project
    _check_text(project.name, "project.name", supported)
    for item in project.contributions:
        _check_text(item.dimension_id, "dimension_id", supported)
        _check_text(item.label, f"dimension {item.dimension_id!r}.label", supported)
    try:
        app_version = version("assembly-fit-analyzer")
    except PackageNotFoundError:
        app_version = "development"
    reference = sha256(dumps_project(project).encode("utf-8")).hexdigest()
    timestamp = (
        generated_at.astimezone(timezone.utc).isoformat()
        if generated_at is not None
        else "Not supplied (deterministic export)"
    )
    body = ParagraphStyle(
        "Body",
        fontName=_FONT,
        fontSize=9,
        leading=13,
        textColor=_INK,
        spaceAfter=7,
        splitLongWords=True,
    )
    cell = ParagraphStyle(
        "Cell",
        parent=body,
        fontSize=8,
        leading=11,
        spaceAfter=0,
        uriWasteReduce=0,
        embeddedHyphenation=0,
    )
    heading = ParagraphStyle(
        "Heading",
        parent=body,
        fontName=_BOLD,
        fontSize=12,
        leading=16,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )
    title = ParagraphStyle(
        "Title", parent=body, fontName=_BOLD, fontSize=19, leading=24
    )

    def p(value, style=body):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)

    story = [
        p("Engineering tolerance analysis report", title),
        p(project.name, heading),
        p(f"Dimensional units: {project.unit} | Application version: {app_version}"),
        p("Methodology: deterministic linear 1D worst-case analysis."),
        p(f"Issue time (UTC): {timestamp}"),
        p(f"Project input SHA-256: {reference}"),
        p("1. Functional assessment", heading),
    ]
    status = (
        "Not assessed" if result.passes is None else "Pass" if result.passes else "Fail"
    )
    explanation = (
        "No functional acceptance assessment was performed; functional limits "
        "were not provided."
        if result.passes is None
        else "Entire worst-case interval lies within the inclusive functional limits."
        if result.passes
        else "Worst-case interval is not fully within the functional limits."
    )
    status_style = ParagraphStyle(
        "Status",
        parent=body,
        fontName=_BOLD,
        fontSize=11,
        textColor=_INK
        if result.passes is None
        else _ACCENT
        if result.passes
        else colors.HexColor("#b43e37"),
    )
    story += [
        p(f"Acceptance: {status}", status_style),
        p(explanation),
        _table(
            ["Quantity", f"Exact value ({project.unit})"],
            [
                ("Minimum result", result.minimum),
                ("Nominal result", result.nominal),
                ("Maximum result", result.maximum),
                (
                    "Functional lower limit (inclusive)",
                    result.acceptance_limits.lower
                    if result.acceptance_limits
                    else "Not provided",
                ),
                (
                    "Functional upper limit (inclusive)",
                    result.acceptance_limits.upper
                    if result.acceptance_limits
                    else "Not provided",
                ),
            ],
            [_WIDTH * 0.48, _WIDTH * 0.52],
            cell,
        ),
        Spacer(1, 8),
        p(
            "Signed range: "
            + range_description(result.minimum, result.maximum).partition(":")[0]
        ),
        p(
            "Sign follows the chosen reference direction. Its physical "
            "meaning depends on the "
            "chain definition. For a clearance chain, crossing zero may "
            "indicate a transition "
            "between clearance and interference; interference is not guaranteed."
        ),
    ]
    figure = IntervalFigure(result, _WIDTH, _FONT)
    if figure.supported:
        story += [
            figure,
            p(
                "Schematic interval overview. Numerical tables contain the "
                "exact values; "
                "plot coordinates do not influence acceptance."
            ),
        ]
    else:
        story.append(
            p(
                "Interval overview omitted: values exceed the display resource "
                "envelope. "
                "The exact numerical assessment above remains valid."
            )
        )
    story += [
        PageBreak(),
        p("2. Complete dimensional inputs", heading),
        p(
            f"All dimensional values in {project.unit}. "
            "Deviations are signed offsets from nominal. "
            "Contribution sign is separate from the nonnegative physical length."
            " Blank dimension cells on continued rows carry the preceding identifier."
        ),
        _table(
            [
                "Dimension",
                "Label",
                "Nominal",
                "Lower deviation",
                "Upper deviation",
                "Sign",
            ],
            [
                (
                    item.dimension_id,
                    item.label,
                    item.nominal,
                    item.lower_deviation,
                    item.upper_deviation,
                    "+1" if item.sign == 1 else "-1",
                )
                for item in project.contributions
            ],
            [_WIDTH * part for part in (0.12, 0.25, 0.16, 0.17, 0.17, 0.13)],
            cell,
        ),
        p("3. Auditable contribution trace", heading),
        p(
            "Physical limits and signed chain contributions are distinct. "
            f"All values in {project.unit}. "
            "A positive contribution uses physical minimum/maximum "
            "directly. A negative contribution "
            "subtracts physical maximum for its minimum contribution and "
            "physical minimum for its maximum. "
            "Signed nominal contributions apply the sign to nominal. "
            "Totals below are copied from the engine."
        ),
        _table(
            [
                "Dimension",
                "Physical minimum",
                "Physical maximum",
                "Signed minimum",
                "Signed nominal",
                "Signed maximum",
            ],
            [
                (
                    trace.dimension.dimension_id,
                    trace.minimum,
                    trace.maximum,
                    trace.minimum_contribution,
                    trace.nominal_contribution,
                    trace.maximum_contribution,
                )
                for trace in result.traces
            ]
            + [("Total", "-", "-", result.minimum, result.nominal, result.maximum)],
            [_WIDTH * part for part in (0.12, 0.176, 0.176, 0.176, 0.176, 0.176)],
            cell,
            totals=True,
        ),
        p("4. Engineering assumptions and limitations", heading),
    ]
    assumptions = [
        "Linear one-dimensional additive chain only; contributions "
        "have fixed signs +1 or -1.",
        "All dimensions and functional limits use the declared project "
        "unit. No unit conversion is performed.",
        "Dimensional limits are independently and simultaneously "
        "attainable. Correlated/shared dimensions "
        "require engineering review before this model is used.",
        "Functional acceptance requires full interval containment, "
        "including boundary equality. "
        "There is no acceptance rounding, hidden epsilon, or clamping "
        "of negative results.",
        "Worst-case bounds are deterministic limits, not statistical "
        "probabilities or yield estimates.",
        "This model excludes GD&T, multi-axis or nonlinear geometry, "
        "thermal effects, and deformation.",
        "No ISO/ASME certification or standards compliance is claimed. "
        "Software checks do not establish "
        "physical suitability or safety. The engineer must verify the "
        "chain, reference direction, and limits.",
        "Exact Decimal text is retained, including trailing zeros and "
        "scientific notation. Long values and "
        "labels wrap across lines/pages without truncation. Table "
        "headers repeat on continued pages.",
    ]
    story.extend(
        p(f"{index}. {statement}")
        for index, statement in enumerate(assumptions, start=1)
    )
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=65,
        bottomMargin=47,
        title="Engineering tolerance analysis report",
        author=APP_NAME,
        subject="Deterministic linear 1D worst-case analysis",
        creator=f"{APP_NAME} {app_version}",
        invariant=1,
        pageCompression=1,
    )

    def decorate(canvas: Canvas, doc) -> None:
        canvas.saveState()
        if generated_at is not None:
            pdf_time = generated_at.astimezone(timezone.utc).strftime(
                "D:%Y%m%d%H%M%S+00'00'"
            )
            canvas.setDateFormatter(lambda *parts: pdf_time)
        canvas.setFont(_BOLD, 8)
        canvas.setFillColor(_INK)
        canvas.drawString(44, A4[1] - 28, APP_NAME)
        canvas.setFont(_FONT, 7)
        canvas.drawString(
            44,
            A4[1] - 42,
            f"Engineering report | Project reference {reference[:16]} | "
            f"Units: {project.unit}",
        )
        canvas.setStrokeColor(colors.HexColor("#ccd6e0"))
        canvas.line(44, A4[1] - 49, A4[0] - 44, A4[1] - 49)
        canvas.line(44, 35, A4[0] - 44, 35)
        canvas.drawString(44, 23, "Exact Decimal results | Deterministic worst-case")
        canvas.drawRightString(A4[0] - 44, 23, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return output.getvalue()
