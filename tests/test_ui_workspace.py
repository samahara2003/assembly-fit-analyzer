"""UI adapters preserve raw edits and delegate engineering rules to the domain."""

from decimal import Decimal, localcontext
from xml.etree import ElementTree

import pytest

from assembly_fit_analyzer.calculations import analyze_project
from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.persistence import PersistenceError, dumps_project
from assembly_fit_analyzer.ui.visualization import compact, interval_svg
from assembly_fit_analyzer.ui.workspace import (
    add_dimension,
    capture_draft,
    contribution_summary,
    draft_from_project,
    editor_rows,
    new_draft,
    project_from_draft,
    project_from_upload,
    range_description,
    remove_dimensions,
)
from assembly_fit_analyzer.validation import ValidationError


@pytest.fixture
def project():
    return AnalysisProject(
        "Precision",
        "in",
        [
            DimensionContribution("A", "Housing", "10.0000", "-0.100", "0.2000", 1),
            DimensionContribution("B", "Insert", "4.0000", "-0.300", "0.1000", -1),
        ],
        AcceptanceLimits("5.8000", "6.5000"),
    )


def test_editor_round_trip_preserves_exact_text_and_order(project):
    draft = draft_from_project(project)
    rows = editor_rows(draft)
    assert rows[0]["nominal"] == "10.0000"
    assert rows[1]["sign"] == "-1"
    restored = project_from_draft(
        capture_draft(draft.name, draft.unit, draft.lower, draft.upper, rows)
    )
    assert restored == project
    assert (
        restored.contributions[0].nominal.as_tuple()
        == project.contributions[0].nominal.as_tuple()
    )


@pytest.mark.parametrize(
    "field",
    ["dimension_id", "label", "nominal", "lower_deviation", "upper_deviation", "sign"],
)
def test_raw_snapshot_detects_every_cell_change(project, field):
    draft = draft_from_project(project)
    rows = editor_rows(draft)
    invalid = "" if field in ("dimension_id", "label") else "invalid input"
    rows[0][field] = invalid
    changed = capture_draft(draft.name, draft.unit, draft.lower, draft.upper, rows)
    assert changed != draft
    assert editor_rows(changed)[0][field] == invalid
    assert editor_rows(draft)[0][field] != invalid
    with pytest.raises(ValidationError) as caught:
        project_from_draft(changed)
    assert "row 1" in str(caught.value)
    assert field in str(caught.value)


@pytest.mark.parametrize("nominal", [None, "", "bad", 0.1, True])
def test_bad_numeric_edits_are_not_coerced(project, nominal):
    draft = draft_from_project(project)
    rows = editor_rows(draft)
    rows[1]["nominal"] = nominal
    changed = capture_draft(draft.name, draft.unit, draft.lower, draft.upper, rows)
    with pytest.raises(ValidationError, match="row 2.*nominal"):
        project_from_draft(changed)


def test_rows_can_be_added_removed_and_duplicates_rejected(project):
    draft = draft_from_project(project)
    rows = editor_rows(draft)
    rows.append(dict(rows[0]))
    duplicate = capture_draft(draft.name, draft.unit, draft.lower, draft.upper, rows)
    with pytest.raises(ValidationError, match="duplicate ID"):
        project_from_draft(duplicate)
    rows[2]["dimension_id"] = "C"
    added = capture_draft(draft.name, draft.unit, draft.lower, draft.upper, rows)
    assert len(project_from_draft(added).contributions) == 3
    rows.pop(0)
    removed = capture_draft(draft.name, draft.unit, draft.lower, draft.upper, rows)
    assert [x.dimension_id for x in project_from_draft(removed).contributions] == [
        "B",
        "C",
    ]
    with pytest.raises(ValidationError, match="contributions"):
        project_from_draft(
            capture_draft(draft.name, draft.unit, draft.lower, draft.upper, [])
        )


def test_name_unit_and_limits_are_part_of_snapshot_and_do_not_convert(project):
    draft = draft_from_project(project)
    for name, unit, lower, upper in [
        ("Other", "in", draft.lower, draft.upper),
        (draft.name, "mm", draft.lower, draft.upper),
        (draft.name, "in", "0", draft.upper),
        (draft.name, "in", draft.lower, "10"),
    ]:
        changed = capture_draft(name, unit, lower, upper, editor_rows(draft))
        assert changed != draft
        assert project_from_draft(changed).contributions == project.contributions


def test_new_draft_has_mandatory_limits_and_keeps_empty_edits():
    draft = new_draft()
    assert draft.lower == draft.upper == ""
    assert editor_rows(draft)[0]["nominal"] == ""
    with pytest.raises(ValidationError):
        project_from_draft(draft)


def test_browser_upload_uses_existing_persistence(project):
    assert project_from_upload(dumps_project(project).encode("utf-8")) == project
    for content in (b"\xff", b"{", b'{"schema_version":2,"project":{}}'):
        with pytest.raises(PersistenceError):
            project_from_upload(content)


@pytest.mark.parametrize(
    ("minimum", "maximum", "description"),
    [
        ("1e-1000", "2", "Entirely positive"),
        ("-2", "-1e-1000", "Entirely negative"),
        ("0", "0", "Zero-width interval at zero"),
        ("0", "1", "Nonnegative; touches zero"),
        ("-1", "0", "Nonpositive; touches zero"),
        (
            "-1e-1000",
            "1e-1000",
            "Crosses zero: possible transition between clearance and interference",
        ),
    ],
)
def test_range_classification_uses_exact_decimal(minimum, maximum, description):
    assert range_description(Decimal(minimum), Decimal(maximum)) == description


def test_svg_is_valid_and_has_all_engineering_markers(project):
    result = analyze_project(project)
    svg = interval_svg(result)
    root = ElementTree.fromstring(svg)
    assert root.attrib["role"] == "img"
    assert "Minimum 5.8000" in svg and "Maximum 6.5000" in svg
    assert "Lower limit 5.8000" in svg and "Upper limit 6.5000" in svg
    assert "Nominal 6.0000" in svg
    assert ">Zero<" not in svg


@pytest.mark.parametrize(
    ("nominal", "lower", "upper"),
    [
        ("0", "0", "0"),
        ("0.1", "-0.1", "0.1"),
        ("1e-1000", "0", "1e-1000"),
        ("1" + "0" * 80 + ".000000000001", "-1e-13", "1e-13"),
    ],
)
def test_plot_handles_point_tiny_and_large_offset_values(nominal, lower, upper):
    item = DimensionContribution("A", "Part", nominal, lower, upper, 1)
    # Acceptance at the permitted endpoints; this test uses engine outputs.
    initial = AnalysisProject("Plot", "mm", [item], AcceptanceLimits(0, "1e100"))
    initial_result = analyze_project(initial)
    project = AnalysisProject(
        "Plot",
        "mm",
        [item],
        AcceptanceLimits(initial_result.minimum, initial_result.maximum),
    )
    result = analyze_project(project)
    with localcontext() as context:
        context.prec = 1
        context.Emax, context.Emin = 1, -1
        for signal in context.traps:
            context.traps[signal] = True
        original_flags = dict(context.flags)
        svg = interval_svg(result)
        assert dict(context.flags) == original_flags
    assert svg is not None
    assert "nan" not in svg.lower() and '="inf"' not in svg.lower()
    assert result == analyze_project(project)


def test_display_guard_does_not_affect_exact_result(project):
    wide = AnalysisProject(
        project.name,
        project.unit,
        project.contributions,
        AcceptanceLimits("-1e10001", "1e10001"),
    )
    result = analyze_project(wide)
    assert result.passes
    assert interval_svg(result) is None
    assert result.minimum == Decimal("5.8000")


def test_compact_labels_keep_simple_values_and_bound_long_ones():
    assert compact(Decimal("1.2300")) == "1.2300"
    assert len(compact(Decimal("123456789012345678901.12345"))) < 24


def test_structural_row_helpers_preserve_invalid_raw_input_and_metadata(project):
    draft = draft_from_project(project)
    rows = editor_rows(draft)
    rows[0]["nominal"] = "raw invalid number"
    rows[0]["dimension_id"] = "D1"
    draft = capture_draft(" Unsaved name ", "mm", "bad", "1.00000", rows)
    added = add_dimension(draft)
    assert added.rows[-1] == ("D2", "", "", "0", "0", "+1")
    assert added.rows[:-1] == draft.rows
    assert (added.name, added.unit, added.lower, added.upper) == (
        draft.name,
        draft.unit,
        draft.lower,
        draft.upper,
    )
    assert remove_dimensions(added, [2]) == draft
    assert remove_dimensions(draft, [1, 0]).rows == ()


@pytest.mark.parametrize("indices", [[-1], [100], [True], ["0"]])
def test_removing_invalid_row_positions_is_rejected(indices):
    with pytest.raises(ValueError, match="row is out of range"):
        remove_dimensions(new_draft(), indices)


def test_contribution_summary_totals_and_values_are_exact_engine_outputs(project):
    result = analyze_project(project)
    with localcontext() as context:
        context.prec = 1
        summary = contribution_summary(result)
    assert list(summary[0]) == ["Dimension", "Minimum", "Nominal", "Maximum"]
    assert summary[1] == {
        "Dimension": "B · Insert",
        "Minimum": "-4.1000",
        "Nominal": "-4.0000",
        "Maximum": "-3.7000",
    }
    assert summary[-1] == {
        "Dimension": "Total",
        "Minimum": str(result.minimum),
        "Nominal": str(result.nominal),
        "Maximum": str(result.maximum),
    }


@pytest.mark.parametrize(
    ("lower", "upper", "below", "above"),
    [
        ("5.8", "6.5", False, False),
        ("5.9", "6.5", True, False),
        ("5.8", "6.4", False, True),
        ("5.9", "6.4", True, True),
        ("7", "8", True, False),
        ("0", "1", False, True),
    ],
)
def test_chart_out_of_limit_segments_correspond_to_endpoints(
    project, lower, upper, below, above
):
    result = analyze_project(
        AnalysisProject(
            project.name,
            project.unit,
            project.contributions,
            AcceptanceLimits(lower, upper),
        )
    )
    svg = interval_svg(result)
    root = ElementTree.fromstring(svg)
    segments = {item.attrib.get("data-segment") for item in root.iter()}
    assert ("below-limit" in segments) is below
    assert ("above-limit" in segments) is above
    assert result.passes is (not below and not above)


@pytest.mark.parametrize(
    ("nominal", "lower", "upper", "limit_low", "limit_high", "zero"),
    [
        ("4", "-0.1", "0.2", "-0.2", "0.5", True),
        ("3", "-0.1", "0.2", "-1.2", "-0.5", False),
    ],
)
def test_chart_zero_crossing_and_negative_results(
    nominal, lower, upper, limit_low, limit_high, zero
):
    project = AnalysisProject(
        "Signed chain",
        "mm",
        [
            DimensionContribution("A", "A", nominal, lower, upper, 1),
            DimensionContribution("B", "B", "4", "-0.3", "0.1", -1),
        ],
        AcceptanceLimits(limit_low, limit_high),
    )
    result = analyze_project(project)
    svg = interval_svg(result)
    assert (">Zero<" in svg) is zero
    assert result.passes
    assert "Minimum " + str(result.minimum) in svg
    assert "Maximum " + str(result.maximum) in svg


def test_chart_uses_nominal_offsets_when_compact_absolute_labels_coincide():
    item = DimensionContribution(
        "A", "Large offset", "100000000000000000000.000000000001", "-1e-13", "1e-13", 1
    )
    initial = analyze_project(
        AnalysisProject("Offset", "mm", [item], AcceptanceLimits(0, "1e30"))
    )
    result = analyze_project(
        AnalysisProject(
            "Offset", "mm", [item], AcceptanceLimits(initial.minimum, initial.maximum)
        )
    )
    with localcontext() as context:
        context.prec = 1
        for signal in context.traps:
            context.traps[signal] = True
        original = dict(context.flags)
        svg = interval_svg(result)
        assert dict(context.flags) == original
    assert "Offsets from nominal" in svg
    assert "Minimum -1E-13" in svg
    assert "Maximum +1E-13" in svg
    assert result.passes
