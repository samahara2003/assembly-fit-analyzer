"""Boundary and early-rejection checks for application I/O budgets."""

import json
from dataclasses import replace
from decimal import Decimal
from io import BytesIO

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
    json_project,
    load_project,
    loads_project,
    save_project,
)
from assembly_fit_analyzer.ui.workspace import (
    capture_draft,
    draft_from_project,
    project_from_draft,
    project_from_upload,
)
from assembly_fit_analyzer.validation import ValidationError
from assembly_fit_analyzer.validation.resources import (
    MAX_DECIMAL_TEXT_CHARS,
    MAX_DIMENSION_ID_CHARS,
    MAX_DIMENSIONS,
    MAX_JSON_BYTES,
    MAX_LABEL_CHARS,
    MAX_PDF_DIMENSIONS,
    MAX_PDF_TEXT_CHARS,
    MAX_PERSISTENCE_ERROR_CHARS,
    MAX_PROJECT_NAME_CHARS,
)


def project(count=1, *, label="Label", name="Project"):
    return AnalysisProject(
        name,
        "mm",
        [DimensionContribution(str(i), label, 1, 0, 0, 1) for i in range(count)],
        AcceptanceLimits(0, count),
    )


def raw_draft(document):
    p = document["project"]
    return capture_draft(
        p["name"],
        p["unit"],
        p["acceptance_limits"]["lower"],
        p["acceptance_limits"]["upper"],
        [dict(d, sign="+1" if d["sign"] == 1 else "-1") for d in p["contributions"]],
    )


@pytest.mark.parametrize("level", ["root", "project", "dimension", "limits"])
@pytest.mark.parametrize("key", ["\ud800", "bad\udfff"])
def test_unicode_keys_at_all_schema_levels_are_safe(level, key):
    document = json.loads(dumps_project(project()))
    target = {
        "root": document,
        "project": document["project"],
        "dimension": document["project"]["contributions"][0],
        "limits": document["project"]["acceptance_limits"],
    }[level]
    target[key] = 1
    with pytest.raises(PersistenceError, match="key: invalid Unicode") as caught:
        loads_project(json.dumps(document))
    assert str(caught.value).encode("utf-8")


@pytest.mark.parametrize(
    "text",
    [
        '{"schema_version":1,"project":{},"\\ud800":1}',
        '{"schema_version":"\\ud800","project":{}}',
        '"\\ud800"',
        '{"\\ud800":1,"\\ud800":2}',
        '{"schema_version":1,"project":{},"bad\ud800":1}',
    ],
)
def test_every_persistence_diagnostic_is_utf8(text):
    with pytest.raises(PersistenceError) as caught:
        loads_project(text)
    assert str(caught.value).encode("utf-8")


def test_diagnostics_are_safe_and_bounded_even_for_invalid_paths(tmp_path):
    message = str(PersistenceError("bad\ud800" + "x" * 5_000))
    assert "\\ud800" in message
    assert len(message) == MAX_PERSISTENCE_ERROR_CHARS
    assert message.endswith("…")
    with pytest.raises(PersistenceError) as caught:
        load_project(tmp_path / "bad\ud800" / "missing.json")
    assert str(caught.value).encode("utf-8")


@pytest.mark.parametrize("padding_char", [" ", "\t"])
def test_json_byte_boundary_and_local_file_reads(tmp_path, padding_char):
    original = project(name="Unicode é")
    text = dumps_project(original)
    exact = text + padding_char * (MAX_JSON_BYTES - len(text.encode("utf-8")))
    data = exact.encode("utf-8")
    assert len(data) == MAX_JSON_BYTES
    assert len(exact) < MAX_JSON_BYTES  # Limit measures UTF-8 bytes, not characters.
    assert loads_project(exact) == original
    assert project_from_upload(data) == original
    path = tmp_path / "boundary.json"
    path.write_bytes(data)
    assert load_project(path) == original
    for load, value in (
        (loads_project, exact + " "),
        (project_from_upload, data + b" "),
    ):
        with pytest.raises(PersistenceError, match="8388608 bytes"):
            load(value)
    path.write_bytes(data + b" ")
    with pytest.raises(PersistenceError, match="8388608 bytes"):
        load_project(path)


def test_size_rejected_before_decoding_or_json_parsing(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("The oversized document must not reach the JSON decoder")

    monkeypatch.setattr(json_project.json, "loads", forbidden)
    with pytest.raises(PersistenceError, match="8388608 bytes"):
        project_from_upload(b"\xff" * (MAX_JSON_BYTES + 1))
    with pytest.raises(PersistenceError, match="8388608 bytes"):
        loads_project(" " * (MAX_JSON_BYTES + 1))

    class BoundedRead(BytesIO):
        def read(self, size=-1):
            assert size == MAX_JSON_BYTES + 1
            return super().read(size)

    monkeypatch.setattr(
        type(tmp_path),
        "open",
        lambda *a, **kw: BoundedRead(b" " * (MAX_JSON_BYTES + 2)),
    )
    with pytest.raises(PersistenceError, match="8388608 bytes"):
        load_project(tmp_path / "large.json")


@pytest.mark.parametrize(
    ("field", "maximum"),
    [
        ("name", MAX_PROJECT_NAME_CHARS),
        ("dimension_id", MAX_DIMENSION_ID_CHARS),
        ("label", MAX_LABEL_CHARS),
        ("nominal", MAX_DECIMAL_TEXT_CHARS),
        ("lower_deviation", MAX_DECIMAL_TEXT_CHARS),
        ("upper_deviation", MAX_DECIMAL_TEXT_CHARS),
        ("lower", MAX_DECIMAL_TEXT_CHARS),
        ("upper", MAX_DECIMAL_TEXT_CHARS),
    ],
)
def test_field_boundaries_in_json_drafts_and_exports(field, maximum, tmp_path):
    for extra in (0, 1):
        document = json.loads(dumps_project(project()))
        p = document["project"]
        if field == "name":
            target = p
        elif field in ("lower", "upper"):
            target = p["acceptance_limits"]
        else:
            target = p["contributions"][0]
        numeric = field not in ("name", "dimension_id", "label")
        target[field] = (
            "1." + "0" * (maximum + extra - 2) if numeric else ("x" * (maximum + extra))
        )
        if field == "lower_deviation":
            target["upper_deviation"] = target[field]
        draft = raw_draft(document)
        if not extra:
            restored = loads_project(json.dumps(document))
            assert project_from_draft(draft) == restored
            assert loads_project(dumps_project(restored)) == restored
        else:
            with pytest.raises(PersistenceError, match=f"{maximum} characters"):
                loads_project(json.dumps(document))
            with pytest.raises(ValidationError, match=f"{maximum} characters"):
                project_from_draft(draft)
            assert raw_draft(document) == draft
            # Domain models remain general; I/O boundaries enforce these budgets.
            item = p["contributions"][0]
            direct = AnalysisProject(
                p["name"],
                p["unit"],
                [DimensionContribution(**item)],
                AcceptanceLimits(**p["acceptance_limits"]),
            )
            path = tmp_path / "existing.json"
            path.write_bytes(b"previous work")
            with pytest.raises(PersistenceError, match=f"{maximum} characters"):
                save_project(direct, path)
            assert path.read_bytes() == b"previous work"
            assert list(tmp_path.iterdir()) == [path]


def test_dimension_count_boundary_and_early_rejection(monkeypatch):
    exact = project(MAX_DIMENSIONS)
    assert loads_project(dumps_project(exact)) == exact
    assert project_from_draft(draft_from_project(exact)) == exact
    over = project(MAX_DIMENSIONS + 1)
    with pytest.raises(PersistenceError, match="1000 dimensions"):
        dumps_project(over)
    draft = replace(draft_from_project(exact), rows=draft_from_project(exact).rows * 2)
    with pytest.raises(ValidationError, match="1000 dimensions"):
        project_from_draft(draft)
    document = json.loads(dumps_project(exact))
    document["project"]["contributions"].append(document["project"]["contributions"][0])

    def forbidden(*args, **kwargs):
        pytest.fail("Too many dimensions must be rejected before constructing models")

    monkeypatch.setattr(json_project, "DimensionContribution", forbidden)
    with pytest.raises(PersistenceError, match="1000 dimensions"):
        loads_project(json.dumps(document))


def test_joint_serialized_byte_budget_preserves_existing_file(tmp_path):
    # All individual fields fit; JSON escaping still exceeds the document budget.
    large = project(MAX_DIMENSIONS, label="x" + "\n" * (MAX_LABEL_CHARS - 2) + "x")
    path = tmp_path / "existing.json"
    path.write_bytes(b"keep this")
    with pytest.raises(PersistenceError, match="8388608 bytes"):
        save_project(large, path)
    assert path.read_bytes() == b"keep this"
    assert list(tmp_path.iterdir()) == [path]


def test_application_budgets_preserve_engine_precision_boundary():
    p = AnalysisProject(
        "Arithmetic boundary",
        "mm",
        [DimensionContribution("A", "Boundary", "1e4999", 0, "1e-4999", 1)],
        AcceptanceLimits(0, "1e5000"),
    )
    expected = analyze_project(p)
    restored = project_from_draft(draft_from_project(loads_project(dumps_project(p))))
    assert analyze_project(restored) == expected
    assert len(str(expected.maximum)) <= MAX_DECIMAL_TEXT_CHARS
    assert expected.maximum.as_tuple() == analyze_project(restored).maximum.as_tuple()


def test_pdf_dimension_boundary_and_pre_render_rejection(monkeypatch):
    pytest.importorskip("reportlab")
    from assembly_fit_analyzer.reporting import ReportError, generate_pdf_report, pdf

    assert generate_pdf_report(analyze_project(project(MAX_PDF_DIMENSIONS))).startswith(
        b"%PDF-"
    )
    over = analyze_project(project(MAX_PDF_DIMENSIONS + 1))
    # The larger project remains eligible for JSON and engine analysis.
    assert loads_project(dumps_project(over.project)) == over.project

    def forbidden(*args, **kwargs):
        pytest.fail("Over-budget reports must not reach verification or rendering")

    monkeypatch.setattr(pdf, "analyze_project", forbidden)
    monkeypatch.setattr(pdf, "_render", forbidden)
    with pytest.raises(ReportError, match="250 dimensions"):
        generate_pdf_report(over)


def test_pdf_dynamic_text_boundary_and_early_rejection(monkeypatch):
    pytest.importorskip("reportlab")
    from assembly_fit_analyzer.reporting import ReportError, generate_pdf_report, pdf

    # Seven name characters, 8 assessment/total value characters, 11 input
    # characters and 6 trace characters: exactly 32 dynamic characters.
    result = analyze_project(project())
    monkeypatch.setattr(pdf, "MAX_PDF_TEXT_CHARS", 32)
    assert generate_pdf_report(result).startswith(b"%PDF-")
    too_large = analyze_project(project(name="Project!"))
    monkeypatch.setattr(
        pdf, "_render", lambda *args: pytest.fail("Budget must precede rendering")
    )
    with pytest.raises(ReportError, match="32 dynamic text characters"):
        generate_pdf_report(too_large)


def test_full_pdf_text_limit_is_independent_from_json():
    pytest.importorskip("reportlab")
    from assembly_fit_analyzer.reporting import ReportError, generate_pdf_report

    large = project(13, label="x" * MAX_LABEL_CHARS)
    assert 13 * MAX_LABEL_CHARS > MAX_PDF_TEXT_CHARS
    assert loads_project(dumps_project(large)) == large
    result = analyze_project(large)
    assert result.nominal == Decimal(13)
    with pytest.raises(ReportError, match="100000 dynamic text characters"):
        generate_pdf_report(result)
