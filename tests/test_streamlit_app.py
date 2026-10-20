"""Integration tests using Streamlit's optional application test harness."""

import json
from pathlib import Path

import pytest

from assembly_fit_analyzer.persistence import dumps_project, loads_project
from assembly_fit_analyzer.ui.workspace import (
    draft_from_project,
    project_from_draft,
)

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception
    return app


@pytest.fixture
def app():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    return app


@pytest.fixture
def example(app):
    click(app, "Use worked example")
    click(app, "Replace workspace")
    return app


def test_empty_workspace_has_no_calculated_result(app):
    assert not app.metric
    click(app, "Analyze")
    assert any("row 1" in item.value for item in app.error)
    assert not app.metric
    assert not app.session_state["current_draft"].lower
    assert app.session_state["pdf_data"] is None


def test_analysis_only_ui_json_pdf_and_partial_limits(example):
    from io import BytesIO

    from pypdf import PdfReader

    example.text_input[1].set_value("")
    example.text_input[2].set_value("").run()
    click(example, "Analyze")
    assert [metric.value for metric in example.metric] == ["5.800", "6.000", "6.500"]
    assert example.session_state["result"].passes is None
    assert any(
        "No functional acceptance assessment performed" in info.value
        for info in example.info
    )
    assert not example.success and not example.error
    example.session_state[f"export_{example.session_state['revision']}"] = True
    example.run()
    assert loads_project(example.session_state["export_data"]).acceptance_limits is None
    example.session_state[f"pdf_{example.session_state['revision']}"] = True
    example.run()
    text = "\n".join(
        p.extract_text()
        for p in PdfReader(BytesIO(example.session_state["pdf_data"])).pages
    )
    assert "Acceptance: Not assessed" in text
    example.text_input[1].set_value("5.800").run()
    click(example, "Analyze")
    assert any(
        "provide both functional limits" in error.value for error in example.error
    )
    assert not example.metric
    assert example.session_state["pdf_data"] is None
    assert example.session_state["export_data"] is None


def test_joint_committed_table_metadata_edits_export_fresh_and_clear_pdf(example):
    click(example, "Analyze")
    revision = example.session_state["revision"]
    example.session_state[f"pdf_{revision}"] = True
    example.run()
    assert example.session_state["pdf_data"] is not None
    exact = "10.123456789012345678901234567890000"
    example.session_state[f"chain_{revision}"] = {
        "edited_rows": {0: {"nominal": exact}},
        "added_rows": [],
        "deleted_rows": [],
    }
    example.text_input[0].set_value("Latest metadata")
    example.session_state[f"export_{revision}"] = True
    example.run()
    restored = loads_project(example.session_state["export_data"])
    assert restored.name == "Latest metadata"
    assert str(restored.contributions[0].nominal) == exact
    assert example.session_state["pdf_data"] is None
    assert not example.metric and not example.exception


def test_explicit_analysis_and_exact_results(example):
    assert not example.metric
    click(example, "Analyze")
    assert [metric.value for metric in example.metric] == ["5.800", "6.000", "6.500"]
    assert any(item.value.startswith("Pass") for item in example.success)
    assert len(example.dataframe) == 3  # editor, summary, full trace
    summary = example.dataframe[1].value.to_dict("records")
    assert summary[-1] == {
        "Dimension": "Total",
        "Minimum": "5.800",
        "Nominal": "6.000",
        "Maximum": "6.500",
    }
    assert "5.800" in example.code[0].value


def test_metadata_edit_hides_results_and_units_do_not_convert(example):
    click(example, "Analyze")
    before = example.session_state["current_draft"].rows
    example.selectbox[0].select("in").run()
    assert not example.exception
    assert not example.metric
    assert any("Inputs changed" in message.value for message in example.warning)
    assert example.session_state["current_draft"].rows == before
    click(example, "Analyze")
    assert all("(in)" in metric.label for metric in example.metric)


def test_editor_edits_survive_other_widget_reruns_and_hide_results(example):
    click(example, "Analyze")
    key = f"chain_{example.session_state['revision']}"
    example.session_state[key] = {
        "edited_rows": {0: {"nominal": "10.123456789012345678901234567890"}},
        "added_rows": [],
        "deleted_rows": [],
    }
    example.run()
    assert not example.exception
    assert not example.metric
    assert (
        "10.123456789012345678901234567890"
        in example.session_state["current_draft"].rows[0]
    )
    example.text_input[0].set_value("Renamed project").run()
    example.run()
    assert (
        example.session_state["current_draft"].rows[0][2]
        == "10.123456789012345678901234567890"
    )
    click(example, "Analyze")
    assert example.session_state["result"].project.name == "Renamed project"


def test_invalid_edit_stays_visible_and_download_is_invalidated(example):
    example.session_state[f"export_{example.session_state['revision']}"] = True
    example.run()
    saved = example.session_state["export_data"]
    assert loads_project(saved).name == "Housing clearance"
    example.text_input[1].set_value("bad limit").run()
    click(example, "Analyze")
    assert any("acceptance_limits.lower" in message.value for message in example.error)
    assert example.text_input[1].value == "bad limit"
    assert example.session_state["export_draft"] is None
    assert not example.metric


def test_export_panel_refreshes_snapshot_and_has_no_closed_download_link(example):
    assert not example.get("download_button")
    key = f"export_{example.session_state['revision']}"
    example.session_state[key] = True
    example.run()
    assert not example.exception
    assert len(example.get("download_button")) == 1
    assert (
        example.session_state["export_draft"] == example.session_state["current_draft"]
    )
    example.session_state[key] = False
    example.run()
    assert not example.get("download_button")
    assert example.session_state["export_data"] is None
    example.text_input[0].set_value("Fresh export").run()
    example.session_state[key] = True
    example.run()
    assert loads_project(example.session_state["export_data"]).name == "Fresh export"


def test_explicit_row_actions_preserve_edits_and_invalidate_analysis(example):
    example.text_input[0].set_value("Unsaved metadata").run()
    click(example, "Analyze")
    before = example.session_state["current_draft"]
    click(example, "Add dimension")
    added = example.session_state["current_draft"]
    assert not example.metric
    assert added.name == before.name
    assert added.rows[:-1] == before.rows
    assert len(added.rows) == 3
    example.multiselect[0].set_value([2]).run()
    click(example, "Remove selected")
    assert example.session_state["current_draft"] == before
    # Returning to identical raw inputs makes the existing snapshot valid again.
    assert len(example.metric) == 3
    example.text_input[1].set_value("invalid lower bound").run()
    click(example, "Add dimension")
    assert example.text_input[1].value == "invalid lower bound"


def test_long_text_and_exact_values_survive_workspace_controls(example):
    name = "Housing and insert assembly " * 8
    label = "Housing reference dimension " * 12
    nominal = "10.123456789012345678901234567890000"
    example.text_input[0].set_value(name).run()
    key = f"chain_{example.session_state['revision']}"
    example.session_state[key] = {
        "edited_rows": {0: {"label": label, "nominal": nominal}},
        "added_rows": [],
        "deleted_rows": [],
    }
    example.run()
    click(example, "Add dimension")
    example.multiselect[0].set_value([2]).run()
    click(example, "Remove selected")
    click(example, "Analyze")
    result = example.session_state["result"]
    assert result.project.name == name.strip()
    assert str(result.traces[0].dimension.nominal) == nominal
    summary = example.dataframe[1].value.to_dict("records")
    assert label.strip() in summary[0]["Dimension"]
    for field in ("minimum", "nominal", "maximum"):
        assert summary[-1][field.title()] == str(getattr(result, field))
        assert str(getattr(result, field)) in example.code[0].value
    example.session_state[f"export_{example.session_state['revision']}"] = True
    example.run()
    restored = loads_project(example.session_state["export_data"])
    assert restored == result.project


def test_new_project_can_be_cancelled_without_discarding_edits(example):
    example.text_input[0].set_value("Unsaved work").run()
    before = example.session_state["current_draft"]
    click(example, "New project")
    assert example.session_state["current_draft"] == before
    click(example, "Keep editing")
    assert example.session_state["current_draft"] == before
    click(example, "New project")
    click(example, "Replace workspace")
    assert example.text_input[0].value == "Untitled project"
    assert example.session_state["result"] is None


def test_browser_upload_replacement_and_bad_file_preserves_edits(example):
    before = example.session_state["current_draft"]
    example.file_uploader[0].upload("bad.json", b"{", "application/json").run()
    click(example, "Load uploaded project")
    assert any("malformed JSON" in error.value for error in example.error)
    assert example.session_state["current_draft"] == before
    assert example.session_state["pending"] is None
    project = project_from_draft(before)
    example.file_uploader[0].set_value(
        ("saved.json", dumps_project(project).encode(), "application/json")
    ).run()
    click(example, "Load uploaded project")
    assert example.session_state["current_draft"] == before
    click(example, "Replace workspace")
    assert example.session_state["current_draft"] == draft_from_project(project)
    assert not example.metric


def test_engine_resource_error_is_actionable_and_does_not_show_old_result(example):
    click(example, "Analyze")
    key = f"chain_{example.session_state['revision']}"
    example.session_state[key] = {
        "edited_rows": {0: {"nominal": "1e10001"}},
        "added_rows": [],
        "deleted_rows": [],
    }
    example.run()
    click(example, "Analyze")
    assert not example.metric
    assert any("Analysis could not complete" in error.value for error in example.error)


def test_pdf_requires_current_analysis_and_invalidates_after_edit(example):
    from io import BytesIO

    PdfReader = pytest.importorskip("pypdf").PdfReader
    assert example.session_state["pdf_data"] is None
    click(example, "Analyze")
    key = f"pdf_{example.session_state['revision']}"
    assert not example.get("download_button")
    example.session_state[key] = True
    example.run()
    assert not example.exception
    data = example.session_state["pdf_data"]
    assert data.startswith(b"%PDF-")
    assert example.session_state["pdf_draft"] == example.session_state["current_draft"]
    assert len(example.get("download_button")) == 1
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    assert "Housing clearance" in text and "5.800" in text
    example.text_input[0].set_value("Updated project").run()
    assert not example.exception
    assert example.session_state["pdf_data"] is None
    assert not example.get("download_button")
    click(example, "Analyze")
    example.session_state[key] = True
    example.run()
    updated = example.session_state["pdf_data"]
    assert updated != data
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(updated)).pages)
    assert "Updated project" in text


def test_functional_failure_still_has_a_valid_pdf_report(example):
    from io import BytesIO

    PdfReader = pytest.importorskip("pypdf").PdfReader
    example.text_input[2].set_value("6.400").run()
    click(example, "Analyze")
    example.session_state[f"pdf_{example.session_state['revision']}"] = True
    example.run()
    assert not example.exception
    text = "\n".join(
        page.extract_text()
        for page in PdfReader(BytesIO(example.session_state["pdf_data"])).pages
    )
    assert "Acceptance: Fail" in text
    assert "6.400" in text


def test_pdf_generation_error_is_graceful_and_json_export_is_independent(
    example, monkeypatch
):
    from assembly_fit_analyzer.reporting import ReportError
    from assembly_fit_analyzer.ui import app as ui_app

    def failed(*args, **kwargs):
        raise ReportError("unsupported report text")

    monkeypatch.setattr(ui_app, "generate_pdf_report", failed)
    click(example, "Analyze")
    example.session_state[f"pdf_{example.session_state['revision']}"] = True
    example.run()
    assert not example.exception
    assert example.session_state["pdf_data"] is None
    assert any(
        "Could not generate the PDF report" in message.value
        for message in example.error
    )
    example.session_state[f"export_{example.session_state['revision']}"] = True
    example.run()
    assert (
        loads_project(example.session_state["export_data"]).name == "Housing clearance"
    )
    assert len(example.get("download_button")) == 1


def test_invalid_row_edit_discards_cached_pdf(example):
    click(example, "Analyze")
    example.session_state[f"pdf_{example.session_state['revision']}"] = True
    example.run()
    assert example.session_state["pdf_data"]
    click(example, "Add dimension")
    assert example.session_state["pdf_data"] is None
    assert not example.get("download_button")


@pytest.mark.parametrize("level", ["root", "project", "dimension", "limits"])
def test_unicode_upload_rejection_keeps_rendered_editor_and_raw_edits(example, level):
    example.text_input[0].set_value("Unsaved Unicode review").run()
    example.text_input[1].set_value("5.9000000").run()
    key = f"chain_{example.session_state['revision']}"
    exact = "10.123456789012345678901234567890000"
    example.session_state[key] = {
        "edited_rows": {0: {"nominal": exact}},
        "added_rows": [],
        "deleted_rows": [],
    }
    example.run()
    before = example.session_state["current_draft"]
    revision = example.session_state["revision"]
    document = json.loads(dumps_project(project_from_draft(before)))
    target = {
        "root": document,
        "project": document["project"],
        "dimension": document["project"]["contributions"][0],
        "limits": document["project"]["acceptance_limits"],
    }[level]
    target["\ud800"] = 1
    example.file_uploader[0].upload(
        "unicode.json", json.dumps(document).encode(), "application/json"
    ).run()
    click(example, "Load uploaded project")
    # The original bug also broke exception rendering: checking exception alone
    # would miss the disappearing editor. Assert the actual widgets and recovery.
    assert len(example.text_input) == 3
    assert any("invalid Unicode" in error.value for error in example.error)
    assert example.text_input[1].value == "5.9000000"
    assert example.session_state["pending"] is None
    assert example.session_state["revision"] == revision
    assert example.session_state["current_draft"] == before
    click(example, "New project")
    click(example, "Keep editing")
    assert example.session_state["current_draft"] == before
    assert example.text_input[0].value == before.name


def test_oversized_upload_keeps_editor_and_existing_analysis(example):
    from assembly_fit_analyzer.validation.resources import MAX_JSON_BYTES

    click(example, "Analyze")
    before = example.session_state["current_draft"]
    result = example.session_state["result"]
    example.file_uploader[0].upload(
        "oversized.json", b" " * (MAX_JSON_BYTES + 1), "application/json"
    ).run()
    click(example, "Load uploaded project")
    assert len(example.text_input) == 3
    assert any("8388608 bytes" in error.value for error in example.error)
    assert example.session_state["current_draft"] == before
    assert example.session_state["result"] == result
    assert len(example.metric) == 3
    assert example.session_state["pending"] is None


def test_export_name_is_literal_text_and_alert_metadata_is_escaped(example):
    payload = (
        "Review ![pixel](https://audit.invalid/image.png) [link](https://audit.invalid)"
    )
    example.text_input[0].set_value(payload).run()
    example.session_state[f"export_{example.session_state['revision']}"] = True
    example.run()
    assert any(text.value == payload for text in example.text)
    assert not any(payload in text.value for text in example.markdown)
    assert loads_project(example.session_state["export_data"]).name == payload
    example.file_uploader[0].upload(
        "metadata.json", json.dumps({payload: 1}).encode(), "application/json"
    ).run()
    click(example, "Load uploaded project")
    assert any(
        payload in error.value and error.value.startswith("```text\n")
        for error in example.error
    )
    assert example.session_state["current_draft"].name == payload
