"""Extract PDF content to verify exact results, provenance, and pagination."""

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
from io import BytesIO

import pytest

from assembly_fit_analyzer.calculations import analyze_project, analyze_worst_case
from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.persistence import dumps_project
from assembly_fit_analyzer.reporting import ReportError, generate_pdf_report

pytest.importorskip("reportlab")
PdfReader = pytest.importorskip("pypdf").PdfReader


@pytest.fixture
def result():
    return analyze_project(
        AnalysisProject(
            "Housing clearance",
            "mm",
            [
                DimensionContribution("A", "Housing", "10.000", "-0.100", "0.200", 1),
                DimensionContribution("B", "Insert", "4.000", "-0.300", "0.100", -1),
            ],
            AcceptanceLimits("5.800", "6.500"),
        )
    )


def read_report(result, **kwargs):
    data = generate_pdf_report(result, **kwargs)
    assert data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF")
    reader = PdfReader(BytesIO(data), strict=True)
    return reader, "\n".join(page.extract_text() for page in reader.pages)


def test_worked_example_exact_values_trace_units_and_assumptions(result):
    reader, text = read_report(result)
    for value in (
        "Assembly Fit & Tolerance Analyzer",
        "Engineering tolerance analysis report",
        "Housing clearance",
        "Dimensional units: mm",
        "deterministic linear 1D worst-case",
        "Acceptance: Pass",
        "Signed range: Entirely positive",
        "10.000",
        "-0.100",
        "0.200",
        "+1",
        "-1",
        "4.000",
        "-0.300",
        "0.100",
        "9.900",
        "10.200",
        "3.700",
        "4.100",
        "-4.100",
        "-4.000",
        "-3.700",
        "independently and simultaneously attainable",
        "No ISO/ASME certification",
    ):
        assert value in text
    for label, value in (
        ("Minimum result", "5.800"),
        ("Nominal result", "6.000"),
        ("Maximum result", "6.500"),
        ("Functional lower limit (inclusive)", "5.800"),
        ("Functional upper limit (inclusive)", "6.500"),
    ):
        assert f"{label}\n{value}" in text
    assert sha256(dumps_project(result.project).encode()).hexdigest() in text
    assert "Functional interval" in text and "Calculated interval" in text
    assert "Nominal marker" in text
    assert reader.metadata.title == "Engineering tolerance analysis report"
    assert len(reader.pages) >= 2
    assert "not statistical probabilities" in text


@pytest.mark.parametrize(
    ("lower", "upper", "status"),
    [
        ("5.800", "6.500", "Pass"),
        ("5.801", "6.500", "Fail"),
        ("5.800", "6.499", "Fail"),
        ("6.000", "6.000", "Fail"),
    ],
)
def test_passing_and_failing_inclusive_assessments(result, lower, upper, status):
    project = result.project
    updated = analyze_project(
        AnalysisProject(
            project.name,
            project.unit,
            project.contributions,
            AcceptanceLimits(lower, upper),
        )
    )
    _, text = read_report(updated)
    assert f"Acceptance: {status}" in text


@pytest.mark.parametrize(
    ("nominal", "lower", "upper", "accept_low", "accept_high", "classification"),
    [
        ("4", "-0.1", "0.2", "-0.2", "0.5", "Crosses zero"),
        ("3", "-0.1", "0.2", "-1.2", "-0.5", "Entirely negative"),
        ("4", "0", "0", "0", "0", "Zero-width interval at zero"),
        ("4", "0", "0.1", "0", "0.1", "Nonnegative; touches zero"),
    ],
)
def test_signed_results_zero_and_point_intervals(
    nominal, lower, upper, accept_low, accept_high, classification
):
    # The second dimension is fixed except in the first two worked cases.
    variable_insert = nominal != "4" or lower == "-0.1"
    result = analyze_project(
        AnalysisProject(
            "Signed chain",
            "in",
            [
                DimensionContribution("A", "Housing", nominal, lower, upper, 1),
                DimensionContribution(
                    "B",
                    "Insert",
                    "4",
                    "-0.3" if variable_insert else "0",
                    "0.1" if variable_insert else "0",
                    -1,
                ),
            ],
            AcceptanceLimits(accept_low, accept_high),
        )
    )
    _, text = read_report(result)
    assert f"Signed range: {classification}" in text
    assert "Dimensional units: in" in text
    assert f"Minimum result\n{result.minimum}" in text
    assert f"Maximum result\n{result.maximum}" in text
    assert "not guaranteed" in text
    if result.minimum <= 0 <= result.maximum:
        assert "Zero" in text


def test_exact_decimal_scale_exponents_and_context_isolation():
    result = analyze_project(
        AnalysisProject(
            "Precision",
            "mm",
            [
                DimensionContribution(
                    "A",
                    "Precision spacer",
                    "1.123456789012345678901234567890",
                    "-0.000000000000000000000000000001",
                    "0.000000000000000000000000000002",
                    1,
                ),
                DimensionContribution(
                    "B", "Tiny spacer", "1.2300E-80", "-0.000", "0.0000", 1
                ),
            ],
            AcceptanceLimits("0.000000", "2.000000"),
        )
    )
    canonical = generate_pdf_report(result)
    with localcontext() as context:
        context.prec, context.Emax, context.Emin, context.capitals = 1, 1, -1, 0
        for signal in context.traps:
            context.traps[signal] = True
        before = dict(context.flags)
        data = generate_pdf_report(result)
        assert dict(context.flags) == before
    assert data == canonical
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)
    compact_text = re.sub(r"\s+", "", text)
    for value in (
        str(result.nominal),
        str(result.minimum),
        str(result.maximum),
        "1.123456789012345678901234567890",
        "1.2300E-80",
        "2.000000",
    ):
        assert value in compact_text


def test_long_labels_long_numeric_cells_and_markup_are_not_truncated():
    label = (
        "StartLabel "
        + ("precision dimension <not markup> & physical input " * 160)
        + " EndLabel"
    )
    digits = "1." + "1234567890" * 150
    result = analyze_project(
        AnalysisProject(
            "Long project <literal> & label",
            "mm",
            [
                DimensionContribution("D001", label, digits, "0", "0", 1),
            ],
            AcceptanceLimits("0", "2"),
        )
    )
    reader, text = read_report(result)
    assert len(reader.pages) > 3
    assert "StartLabel" in text and "EndLabel" in text
    assert "<not markup>" in text and "<literal>" in text
    assert text.count("physical input") == 160
    assert digits in re.sub(r"\s+", "", text)
    assert "Engineering assumptions and limitations" in text


def test_large_table_pagination_repeats_headers_and_keeps_every_dimension():
    result = analyze_project(
        AnalysisProject(
            "Large chain",
            "mm",
            [
                DimensionContribution(
                    f"D{index:03d}",
                    f"Component label {index:03d}",
                    "1.000",
                    "0",
                    "0",
                    1,
                )
                for index in range(1, 161)
            ],
            AcceptanceLimits("160.000", "160.000"),
        )
    )
    reader, text = read_report(result)
    assert len(reader.pages) > 8
    ids = re.findall(r"(?m)^D\d{3}$", text)
    for index in range(1, 161):
        assert ids.count(f"D{index:03d}") == 2
    for index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()
        assert f"Page {index}" in page_text
        assert "Assembly Fit & Tolerance Analyzer" in page_text
        assert "Units: mm" in page_text
        if re.search(r"(?m)^D\d{3}$", page_text):
            assert "Lower deviation" in page_text or "Signed minimum" in page_text


def test_supported_accented_text_and_embedded_fonts(result):
    project = result.project
    renamed = analyze_project(
        AnalysisProject(
            "Métrique – análisis",
            "mm",
            project.contributions,
            project.acceptance_limits,
        )
    )
    reader, text = read_report(renamed)
    assert "Métrique – análisis" in text
    fonts = [
        font.get_object()
        for page in reader.pages
        for font in page["/Resources"]["/Font"].values()
    ]
    assert any("/FontFile2" in font.get("/FontDescriptor", {}) for font in fonts)


def test_unsupported_characters_fail_explicitly_instead_of_missing_glyphs(result):
    project = result.project
    unsupported = analyze_project(
        AnalysisProject(
            "Unsupported 日本語", "mm", project.contributions, project.acceptance_limits
        )
    )
    with pytest.raises(ReportError, match="project.name.*U\\+65E5.*unsupported"):
        generate_pdf_report(unsupported)


def test_deterministic_bytes_and_explicit_issue_timestamp(result):
    first = generate_pdf_report(result)
    read_report(
        replace(
            result,
            project=AnalysisProject(
                "Another project",
                "mm",
                result.project.contributions,
                result.project.acceptance_limits,
            ),
        )
    )
    assert generate_pdf_report(result) == first
    issued = datetime(2026, 10, 19, 15, 30, tzinfo=timezone.utc)
    data = generate_pdf_report(result, generated_at=issued)
    assert data == generate_pdf_report(result, generated_at=issued)
    assert data != first
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    assert "2026-10-19T15:30:00+00:00" in text
    assert PdfReader(BytesIO(data)).metadata.creation_date == issued
    equivalent = issued.astimezone(timezone(timedelta(hours=-7)))
    assert data == generate_pdf_report(result, generated_at=equivalent)


@pytest.mark.parametrize("timestamp", ["now", True, datetime(2026, 1, 1)])
def test_invalid_issue_timestamp(result, timestamp):
    with pytest.raises(ReportError, match="generated_at"):
        generate_pdf_report(result, generated_at=timestamp)


@pytest.mark.parametrize("value", [None, {}, (), "result"])
def test_missing_or_invalid_result_type(value):
    with pytest.raises(ReportError, match="expected a WorstCaseResult"):
        generate_pdf_report(value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project", None),
        ("acceptance_limits", None),
        ("traces", ()),
        ("traces", (None,)),
        ("passes", 1),
        ("passes", False),
        ("nominal", 6.0),
        ("minimum", Decimal("NaN")),
        ("maximum", Decimal("Infinity")),
        ("nominal", Decimal("7")),
    ],
)
def test_incomplete_or_inconsistent_result_is_rejected(result, field, value):
    with pytest.raises(ReportError):
        generate_pdf_report(replace(result, **{field: value}))


def test_missing_project_from_legacy_analysis_is_actionable(result):
    legacy = analyze_worst_case(result.project.contributions, "5.8", "6.5")
    with pytest.raises(ReportError, match="use analyze_project"):
        generate_pdf_report(legacy)


def test_inconsistent_or_nonfinite_trace_is_rejected(result):
    for value in (Decimal("NaN"), Decimal("9")):
        bad = replace(result.traces[0], minimum_contribution=value)
        with pytest.raises(ReportError):
            generate_pdf_report(replace(result, traces=(bad,) + result.traces[1:]))


def test_extreme_acceptance_omits_only_visualization(result):
    project = result.project
    extreme = analyze_project(
        AnalysisProject(
            project.name,
            project.unit,
            project.contributions,
            AcceptanceLimits("-1e10001", "1e10001"),
        )
    )
    _, text = read_report(extreme)
    assert "Interval overview omitted" in text
    assert "Acceptance: Pass" in text
    assert "-1E+10001" in text and "1E+10001" in text


def test_rendering_failure_becomes_report_error(result, monkeypatch):
    from assembly_fit_analyzer.reporting import pdf

    def failed(*args, **kwargs):
        raise OSError("simulated rendering failure")

    monkeypatch.setattr(pdf.SimpleDocTemplate, "build", failed)
    with pytest.raises(ReportError, match="PDF generation failed.*simulated rendering"):
        generate_pdf_report(result)


def test_concurrent_report_requests_are_deterministic(result):
    expected = generate_pdf_report(result)
    with ThreadPoolExecutor(max_workers=3) as executor:
        reports = list(executor.map(generate_pdf_report, [result] * 6))
    assert all(data == expected for data in reports)
