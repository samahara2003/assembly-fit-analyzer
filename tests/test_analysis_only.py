"""Optional assessment preserves exact analysis, strict documents and reports."""

import json
from dataclasses import replace
from decimal import Decimal, localcontext
from io import BytesIO
from xml.etree import ElementTree

import pytest

from assembly_fit_analyzer.calculations import analyze_project
from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.persistence import (
    PersistenceError,
    dumps_project,
    load_project,
    loads_project,
    save_project,
)
from assembly_fit_analyzer.ui.visualization import interval_svg
from assembly_fit_analyzer.ui.workspace import draft_from_project, project_from_draft
from assembly_fit_analyzer.validation import ValidationError


def project(limits=None, *, nominal="10.0000"):
    return AnalysisProject(
        "Analysis only",
        "mm",
        [
            DimensionContribution("H", "Housing", nominal, "-0.100", "0.200", 1),
            DimensionContribution("I", "Insert", "4.000", "-0.300", "0.100", -1),
        ],
        limits,
    )


@pytest.mark.parametrize("nominal", ["10.0000", "3.0000", "4.0000", "4.1000"])
def test_no_limits_means_no_verdict_with_identical_arithmetic_and_traces(nominal):
    p = project(nominal=nominal)
    result = analyze_project(p)
    assessed = analyze_project(project(AcceptanceLimits(-100, 100), nominal=nominal))
    assert result.passes is None
    assert result.acceptance_limits is None
    assert result.project is p
    assert (result.minimum, result.nominal, result.maximum, result.traces) == (
        assessed.minimum,
        assessed.nominal,
        assessed.maximum,
        assessed.traces,
    )
    assert assessed.passes is True


def test_optional_constructor_default_and_context_isolation():
    p = project()
    assert AnalysisProject(p.name, p.unit, p.contributions) == p
    with localcontext() as context:
        context.prec = 1
        before = context.copy()
        result = analyze_project(p)
        assert (result.minimum, result.nominal, result.maximum) == (
            Decimal("5.8000"),
            Decimal("6.0000"),
            Decimal("6.5000"),
        )
        assert context.prec == before.prec
        assert context.flags == before.flags


@pytest.mark.parametrize("limits", [{}, {"lower": "0"}, (0, 1), False, ""])
def test_domain_rejects_partial_or_malformed_limit_objects(limits):
    with pytest.raises(ValidationError, match="acceptance_limits"):
        project(limits)


def test_analysis_only_roundtrip_exact_decimal_scale_order_and_atomic_file(tmp_path):
    p = project()
    text = dumps_project(p)
    document = json.loads(text)
    assert document["schema_version"] == 2
    assert document["project"]["acceptance_limits"] is None
    assert document["project"]["contributions"][0]["nominal"] == "10.0000"
    path = tmp_path / "project.json"
    save_project(p, path)
    restored = load_project(path)
    assert restored == loads_project(text) == p
    assert dumps_project(restored) == text
    assert analyze_project(restored).passes is None
    assert [d.dimension_id for d in restored.contributions] == ["H", "I"]
    assert (
        restored.contributions[0].nominal.as_tuple()
        == p.contributions[0].nominal.as_tuple()
    )
    assert project_from_draft(draft_from_project(p)) == p


@pytest.mark.parametrize("version", [1, 2])
def test_complete_limits_legacy_read_and_v2_write_preserve_assessment(version):
    p = project(AcceptanceLimits("5.8000", "6.5000"))
    document = json.loads(dumps_project(p))
    document["schema_version"] = version
    restored = loads_project(json.dumps(document))
    assert restored == p
    assert analyze_project(restored).passes is True
    assert json.loads(dumps_project(restored))["schema_version"] == 2


def test_v1_null_not_silently_reinterpreted_as_analysis_only():
    document = json.loads(dumps_project(project()))
    document["schema_version"] = 1
    with pytest.raises(PersistenceError, match="acceptance_limits.*JSON object"):
        loads_project(json.dumps(document))


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize(
    "limits",
    [
        {},
        {"lower": "0"},
        {"upper": "1"},
        {"lower": None, "upper": "1"},
        {"lower": "0", "upper": ""},
        {"lower": "-Infinity", "upper": "Infinity"},
        {"lower": "0", "upper": "1", "notes": "extra"},
    ],
)
def test_json_partial_malformed_and_unbounded_limits_rejected(version, limits):
    document = json.loads(dumps_project(project()))
    document["schema_version"] = version
    document["project"]["acceptance_limits"] = limits
    with pytest.raises(PersistenceError):
        loads_project(json.dumps(document))


@pytest.mark.parametrize("version", [1, 2])
def test_json_missing_limits_rejected_in_both_versions(version):
    document = json.loads(dumps_project(project()))
    document["schema_version"] = version
    del document["project"]["acceptance_limits"]
    with pytest.raises(
        PersistenceError, match="missing required fields: acceptance_limits"
    ):
        loads_project(json.dumps(document))


@pytest.mark.parametrize(("lower", "upper"), [("", ""), ("  ", "\t")])
def test_ui_both_blank_is_analysis_only(lower, upper):
    draft = replace(draft_from_project(project()), lower=lower, upper=upper)
    assert project_from_draft(draft).acceptance_limits is None


@pytest.mark.parametrize(
    ("lower", "upper"), [("", "1"), ("0", ""), (" ", "1"), (None, "")]
)
def test_ui_rejects_partial_limits_without_mutating_raw_draft(lower, upper):
    draft = replace(draft_from_project(project()), lower=lower, upper=upper)
    with pytest.raises(ValidationError, match="acceptance_limits"):
        project_from_draft(draft)
    assert draft.lower == lower and draft.upper == upper


@pytest.mark.parametrize("nominal", ["10.0000", "3.0000", "4.0000", "1e1000"])
def test_analysis_only_chart_has_no_acceptance_regions_or_limit_markers(nominal):
    svg = interval_svg(analyze_project(project(nominal=nominal)))
    assert svg is not None
    root = ElementTree.fromstring(svg)
    assert "No functional acceptance limits provided" in "".join(root.itertext())
    assert 'data-region="allowed"' not in svg
    assert 'data-segment="below-limit"' not in svg
    assert 'data-segment="above-limit"' not in svg
    assert "Lower limit" not in svg and "Upper limit" not in svg


@pytest.mark.parametrize(
    ("nominal", "unit"), [("10.0000", "mm"), ("3.0000", "in"), ("4.0000", "mm")]
)
def test_analysis_only_pdf_exact_values_no_verdict_and_determinism(nominal, unit):
    pytest.importorskip("reportlab")
    from pypdf import PdfReader

    from assembly_fit_analyzer.reporting import generate_pdf_report

    p = project(nominal=nominal)
    p = AnalysisProject(p.name, unit, p.contributions)
    result = analyze_project(p)
    data = generate_pdf_report(result)
    assert data == generate_pdf_report(result)
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    assert "Acceptance: Not assessed" in text
    assert "No functional acceptance assessment was performed" in text
    assert "Acceptance: Pass" not in text and "Acceptance: Fail" not in text
    assert f"Dimensional units: {unit}" in text
    for value in (
        result.minimum,
        result.nominal,
        result.maximum,
        p.contributions[0].nominal,
    ):
        assert str(value) in text
    assert "Not provided" in text and "Complete dimensional inputs" in text


@pytest.mark.parametrize("passes", [True, False, 0, 1])
def test_pdf_rejects_forged_verdict_without_limits(passes):
    pytest.importorskip("reportlab")
    from assembly_fit_analyzer.reporting import ReportError, generate_pdf_report

    with pytest.raises(ReportError, match="passes"):
        generate_pdf_report(replace(analyze_project(project()), passes=passes))
