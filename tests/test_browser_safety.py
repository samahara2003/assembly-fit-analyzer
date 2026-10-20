"""Opt-in Chrome regressions against a running local Streamlit application.

Set AFA_BROWSER_URL after launching the app; install the dev, ui, browser extras
and Google Chrome. No browser dependency or server is needed for core tests.
"""

import copy
import hashlib
import json
import os
import re
from io import BytesIO

import pytest

from assembly_fit_analyzer.calculations import analyze_project
from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.persistence import dumps_project, loads_project
from assembly_fit_analyzer.validation.resources import (
    MAX_DECIMAL_TEXT_CHARS,
    MAX_DIMENSION_ID_CHARS,
    MAX_DIMENSIONS,
    MAX_JSON_BYTES,
    MAX_LABEL_CHARS,
    MAX_PDF_DIMENSIONS,
    MAX_PROJECT_NAME_CHARS,
)


@pytest.fixture
def browser_page():
    url = os.environ.get("AFA_BROWSER_URL")
    if not url:
        pytest.skip("Set AFA_BROWSER_URL to run the opt-in Chrome checks")
    api = pytest.importorskip("playwright.sync_api")
    api.expect.set_options(timeout=20_000)
    with api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1024, "height": 1100})
        page.set_default_timeout(20_000)
        page.goto(url)
        page.get_by_role("button", name="Analyze", exact=True).wait_for()
        page.get_by_text("Create or load a project", exact=True).click()
        page.get_by_role("button", name="Use worked example", exact=True).click()
        page.get_by_role("button", name="Replace workspace", exact=True).wait_for()
        ready(page, api.expect)
        page.get_by_role("button", name="Replace workspace", exact=True).click()
        name = page.get_by_role("textbox", name="Project name", exact=True)
        api.expect(name.last).to_have_value("Housing clearance")
        api.expect(name).to_have_count(1)
        ready(page, api.expect)
        yield page, api.expect
        browser.close()


def ready(page, expect):
    expect(page.locator('[data-testid="stApp"]')).to_have_attribute(
        "data-test-script-state", "notRunning"
    )


def download_json(page, tmp_path):
    api = pytest.importorskip("playwright.sync_api")
    page.get_by_role("button", name="Export project", exact=True).click()
    with page.expect_download() as download:
        page.get_by_role("button", name="Download JSON", exact=True).click()
    path = tmp_path / "snapshot.json"
    download.value.save_as(str(path))
    page.keyboard.press("Escape")
    api.expect(
        page.get_by_role("button", name="Download JSON", exact=True)
    ).to_have_count(0)
    # Popover closure/upload completion schedules a frontend rerun asynchronously.
    # Allow that event to arrive before testing the server's idle indicator.
    page.wait_for_timeout(700)
    ready(page, api.expect)
    return path.read_text(encoding="utf-8")


def upload(page, payload, name="project.json"):
    api = pytest.importorskip("playwright.sync_api")
    file = {"name": name, "mimeType": "application/json", "buffer": payload}
    if len(payload) > MAX_JSON_BYTES:
        page.locator('input[type="file"]').set_input_files(file)
        return
    # A previous rejected file can leave Load enabled during the next upload.
    # Wait for the new PUT and filename before clicking the server-side action.
    with page.expect_response(
        lambda response: (
            "/_stcore/upload_file/" in response.url and response.request.method == "PUT"
        )
    ) as response:
        page.locator('input[type="file"]').set_input_files(file)
    assert response.value.ok
    page.get_by_text(name, exact=True).wait_for()
    page.wait_for_timeout(700)
    ready(page, api.expect)


def edit_nominal(page, expect, value):
    editor = page.locator('[data-testid="stDataFrame"]').first.locator(".dvn-scroller")
    editor.scroll_into_view_if_needed()
    for _ in range(4):
        box = editor.bounding_box()
        page.mouse.dblclick(box["x"] + 570, box["y"] + 55, delay=100)
        if page.locator(".gdg-input").count():
            break
    cell = page.locator(".gdg-input")
    expect(cell).to_be_visible()
    cell.fill(value)
    expect(cell).to_have_value(value)
    cell.press("Enter")


def download_pdf_text(page, tmp_path):
    from pypdf import PdfReader

    page.get_by_role("button", name="Download PDF report", exact=True).click()
    with page.expect_download() as download:
        page.get_by_role("button", name="Download PDF", exact=True).click()
    path = tmp_path / "snapshot.pdf"
    download.value.save_as(str(path))
    text = "\n".join(
        p.extract_text() for p in PdfReader(BytesIO(path.read_bytes())).pages
    )
    page.keyboard.press("Escape")
    api = pytest.importorskip("playwright.sync_api")
    api.expect(
        page.get_by_role("button", name="Download PDF", exact=True)
    ).to_have_count(0)
    ready(page, api.expect)
    return text


def rejection_documents(base):
    # Original audit payload: ASCII/UTF-8 bytes, invalid Unicode after decoding.
    yield b'{"schema_version":1,"project":{},"\\ud800":1}'
    for level in ("root", "project", "dimension", "limits"):
        doc = copy.deepcopy(base)
        target = {
            "root": doc,
            "project": doc["project"],
            "dimension": doc["project"]["contributions"][0],
            "limits": doc["project"]["acceptance_limits"],
        }[level]
        target["bad\udfff"] = 1
        yield json.dumps(doc).encode()
    for field, count in (
        ("name", MAX_PROJECT_NAME_CHARS + 1),
        ("dimension_id", MAX_DIMENSION_ID_CHARS + 1),
        ("label", MAX_LABEL_CHARS + 1),
        ("nominal", MAX_DECIMAL_TEXT_CHARS + 1),
    ):
        doc = copy.deepcopy(base)
        target = (
            doc["project"] if field == "name" else (doc["project"]["contributions"][0])
        )
        target[field] = "1" * count if field == "nominal" else "x" * count
        yield json.dumps(doc).encode()
    doc = copy.deepcopy(base)
    doc["project"]["contributions"] = [
        dict(base["project"]["contributions"][0], dimension_id=f"D{i}")
        for i in range(MAX_DIMENSIONS + 1)
    ]
    yield json.dumps(doc).encode()
    yield b"\xff"
    yield b"{"
    yield b'{"schema_version":3,"project":{}}'
    yield b'{"schema_version":1,"schema_version":2,"project":{}}'


def test_rejected_uploads_keep_numeric_edits_and_confirmation(browser_page, tmp_path):
    page, expect = browser_page
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator('[data-testid="stMetricValue"]')).to_have_count(3)
    ready(page, expect)
    exact = "10.123456789012345678901234567890000"
    editor = page.locator('[data-testid="stDataFrame"]').first.locator(".dvn-scroller")
    editor.scroll_into_view_if_needed()
    # At this desktop width the nominal cell is in the first visible row.
    # Glide's initial click can focus the grid before opening its editor.
    for _ in range(3):
        box = editor.bounding_box()
        page.mouse.dblclick(box["x"] + 570, box["y"] + 55, delay=100)
        if page.locator(".gdg-input").count():
            break
    cell = page.locator(".gdg-input")
    expect(cell).to_have_value("10.000")
    cell.fill(exact)
    cell.press("Enter")
    name = page.get_by_role("textbox", name="Project name", exact=True)
    lower = page.get_by_role("textbox", name="Lower functional limit", exact=True)
    name.fill("Unsaved release review")
    lower.fill("5.9000000")
    before = download_json(page, tmp_path)
    original = loads_project(before)
    assert original.name == "Unsaved release review"
    assert str(original.acceptance_limits.lower) == "5.9000000"
    assert str(original.contributions[0].nominal) == exact
    for index, payload in enumerate(rejection_documents(json.loads(before))):
        upload(page, payload, f"rejected-{index}.json")
        page.get_by_role("button", name="Load uploaded project", exact=True).click()
        page.get_by_text("Could not load this file:", exact=False).wait_for()
        expect(name).to_have_value(original.name)
        expect(lower).to_have_value("5.9000000")
        expect(
            page.get_by_role("button", name="Replace workspace", exact=True)
        ).to_have_count(0)
        expect(page.locator('[data-testid="stException"]')).to_have_count(0)
        expect(page.locator('[data-testid="stMetricValue"]')).to_have_count(0)
        assert download_json(page, tmp_path) == before
    page.get_by_role("button", name="New project", exact=True).click()
    page.get_by_role("button", name="Keep editing", exact=True).click()
    assert download_json(page, tmp_path) == before
    # A valid upload still requires explicit replacement confirmation.
    upload(page, before.encode(), "valid.json")
    page.get_by_role("button", name="Load uploaded project", exact=True).click()
    expect(
        page.get_by_role("button", name="Replace workspace", exact=True)
    ).to_be_visible()
    expect(name).to_have_value(original.name)
    page.get_by_role("button", name="Keep editing", exact=True).click()
    assert download_json(page, tmp_path) == before


def test_oversized_browser_upload_keeps_unsaved_limits(browser_page, tmp_path):
    page, expect = browser_page
    lower = page.get_by_role("textbox", name="Lower functional limit", exact=True)
    lower.fill("5.900000000")
    before = download_json(page, tmp_path)
    upload(page, b" " * (MAX_JSON_BYTES + 1), "oversized.json")
    expect(
        page.get_by_role("button", name="Load uploaded project", exact=True)
    ).to_be_disabled()
    expect(lower).to_have_value("5.900000000")
    assert download_json(page, tmp_path) == before


def test_metadata_is_literal_and_never_requests_external_resources(
    browser_page, tmp_path
):
    page, expect = browser_page
    attempted = []

    def block(route):
        attempted.append(route.request.url)
        route.abort()

    page.route("https://audit.invalid/**", block)
    payload = (
        "Review **bold** ![pixel](https://audit.invalid/pixel.png) "
        "[link](https://audit.invalid/site) https://audit.invalid/bare "
        '<img src="https://audit.invalid/html.png">'
    )
    page.get_by_role("textbox", name="Project name", exact=True).fill(payload)
    page.get_by_role("button", name="Export project", exact=True).click()
    expect(page.get_by_text(payload, exact=True)).to_be_visible()
    expect(page.locator('img[src^="https://audit.invalid"]')).to_have_count(0)
    expect(page.locator('a[href^="https://audit.invalid"]')).to_have_count(0)
    assert attempted == []
    page.keyboard.press("Escape")
    snapshot = download_json(page, tmp_path)
    assert loads_project(snapshot).name == payload
    # Include untrusted metadata in a persistence diagnostic as well.
    upload(page, json.dumps({payload: 1}).encode(), "metadata.json")
    page.get_by_role("button", name="Load uploaded project", exact=True).click()
    error = page.locator('[data-testid="stAlert"]').filter(has_text="Could not load")
    expect(error).to_contain_text(payload)
    expect(page.locator('img[src^="https://audit.invalid"]')).to_have_count(0)
    expect(page.locator('a[href^="https://audit.invalid"]')).to_have_count(0)
    assert attempted == []
    assert download_json(page, tmp_path) == snapshot


def test_pdf_budget_failure_preserves_analysis_and_json(browser_page, tmp_path):
    page, expect = browser_page
    project = AnalysisProject(
        "Large valid chain",
        "mm",
        [
            DimensionContribution(str(i), "Spacer", 1, 0, 0, 1)
            for i in range(MAX_PDF_DIMENSIONS + 1)
        ],
        AcceptanceLimits(0, MAX_PDF_DIMENSIONS + 1),
    )
    upload(page, dumps_project(project).encode())
    page.get_by_role("button", name="Load uploaded project", exact=True).click()
    page.get_by_role("button", name="Replace workspace", exact=True).wait_for()
    ready(page, expect)
    page.get_by_role("button", name="Replace workspace", exact=True).click()
    expect(
        page.get_by_role("textbox", name="Project name", exact=True).last
    ).to_have_value(project.name)
    expect(page.get_by_role("textbox", name="Project name", exact=True)).to_have_count(
        1
    )
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator('[data-testid="stMetricValue"]')).to_have_text(["251"] * 3)

    page.get_by_role("button", name="Download PDF report", exact=True).click()
    page.get_by_text("Could not generate the PDF report:", exact=False).wait_for()
    expect(page.get_by_role("button", name="Download PDF", exact=True)).to_have_count(0)
    page.keyboard.press("Escape")
    assert loads_project(download_json(page, tmp_path)) == project
    expect(page.locator('[data-testid="stMetricValue"]')).to_have_text(["251"] * 3)


def test_rapid_commits_export_latest_json_and_reject_cached_pdf(browser_page, tmp_path):
    page, expect = browser_page
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator('[data-testid="stMetricValue"]')).to_have_count(3)
    baseline = download_pdf_text(page, tmp_path)
    assert "6.000" in baseline
    # Hold the framework's former 150-ms editor sync timer well beyond export.
    # This deterministically exposes the old race; no sleep is inserted between
    # committing a cell and opening export/report. Buffered microtasks bypass it.
    page.evaluate("""() => {
        const schedule = window.setTimeout.bind(window);
        window.setTimeout = (callback, delay, ...args) =>
            schedule(callback, delay === 150 ? 5000 : delay, ...args);
    }""")
    expected_name, expected_lower = "Housing clearance", "5.800"
    for index in range(6):
        exact = f"10.{index + 1:030d}000"
        edit_nominal(page, expect, exact)
        if index % 2:
            expected_name, expected_lower = f"Rapid {index}", "5.9000000"
            page.get_by_role("textbox", name="Project name", exact=True).fill(
                expected_name
            )
            page.get_by_role("textbox", name="Lower functional limit", exact=True).fill(
                expected_lower
            )
        snapshot = download_json(page, tmp_path)
        restored = loads_project(snapshot)
        assert str(restored.contributions[0].nominal) == exact
        assert restored.name == expected_name
        assert str(restored.acceptance_limits.lower) == expected_lower
        expect(
            page.get_by_role("button", name="Download PDF report", exact=True)
        ).to_have_count(0)
        page.get_by_role("button", name="Analyze", exact=True).click()
        expect(page.locator('[data-testid="stMetricValue"]')).to_have_count(3)
        text = download_pdf_text(page, tmp_path)
        assert exact in re.sub(r"\s+", "", text)
        assert str(analyze_project(restored).nominal) in text
        assert hashlib.sha256(snapshot.encode("utf-8")).hexdigest() in text
    # Exercise the PDF opening action directly, while an older PDF is cached.
    edit_nominal(page, expect, "10.987654321000")
    page.get_by_role("button", name="Download PDF report", exact=True).click()
    expect(page.get_by_role("button", name="Download PDF", exact=True)).to_have_count(0)
    expect(
        page.get_by_text("Inputs changed. Analyze again", exact=False)
    ).to_be_visible()


def test_analysis_only_upload_json_pdf_and_partial_limits(browser_page, tmp_path):
    page, expect = browser_page
    p = AnalysisProject(
        "Preliminary analysis only",
        "mm",
        [
            DimensionContribution("H", "Housing", "14.500", "-0.100", "0.100", 1),
            DimensionContribution("W", "Outer ring", "14.000", "-0.060", "0.000", -1),
        ],
    )
    upload(page, dumps_project(p).encode(), "analysis-only.json")
    page.get_by_role("button", name="Load uploaded project", exact=True).click()
    page.get_by_role("button", name="Replace workspace", exact=True).wait_for()
    ready(page, expect)
    page.get_by_role("button", name="Replace workspace", exact=True).click()
    name = page.get_by_role("textbox", name="Project name", exact=True)
    expect(name.last).to_have_value(p.name)
    expect(name).to_have_count(1)
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator('[data-testid="stMetricValue"]')).to_have_text(
        ["0.400", "0.500", "0.660"]
    )
    expect(
        page.get_by_text(
            "Analysis only · No functional acceptance assessment performed.", exact=True
        )
    ).to_be_visible()
    assert loads_project(download_json(page, tmp_path)) == p
    text = download_pdf_text(page, tmp_path)
    assert "Acceptance: Not assessed" in text
    assert "Acceptance: Pass" not in text and "Acceptance: Fail" not in text
    assert "0.400" in text and "0.500" in text and "0.660" in text
    page.get_by_role("textbox", name="Lower functional limit", exact=True).fill("0")
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(
        page.get_by_text("provide both functional limits", exact=False)
    ).to_be_visible()
    expect(page.locator('[data-testid="stMetricValue"]')).to_have_count(0)
