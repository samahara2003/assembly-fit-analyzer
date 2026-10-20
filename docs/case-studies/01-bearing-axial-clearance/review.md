# Case Study 01 — Engineering and numerical review record

Review date: 19 October 2026. **Disposition: preliminary engineering case study;
not a validated production-ready bearing assembly.**

This record separates an independent numerical method and checked manufacturer
sources from unresolved mechanical design approval. It does not represent a
second human reviewer or SKF approval. Source IDs refer to the
[self-contained study and bibliography](README.md#sources).

## Engineering review

| Question | Evidence / conclusion | Release gate |
| --- | --- | --- |
| Can B be a deep-groove bearing? | S1 lists this type for non-locating service using ring-on-seat sliding. The study specifies a retained inner ring and sliding outer ring. | Confirm actual load direction, fits and free movement through operating temperatures. Type suitability alone is not a complete selection. |
| Is the width interval supported? | S1 p. 270 shows the exact plain 6204 in blue, with the Explorer legend. S1 p. 250 gives the special 0/−60 µm width tolerance for its diameter band. Both rendered pages were inspected, not inferred from another brand or suffix. The outer-ring width relation was checked on p. 39. | Obtain current exact-product drawing/tolerance confirmation. This is catalogue verification, not verification of a purchased part. |
| Do two end stops define float? | H − W is total end space, independent of the ring's position. The 0.500 total / 0.020 right-gap counterexample disproves a directional guarantee. | Keep both end features outside required normal travel and verify full seat support. Otherwise revise the architecture. |
| Is the cold position established? | P = 0.200 ± 0.050 is prominently identified as an added illustrative assumption. A bearing's inner/outer faces are not assumed flush. | Replace P with an assembled-position stack/measurement including A/B axial freedom. |
| Does the thermal estimate establish hot clearance? | Uniform station expansion yields +0.054. The report separately defines ΔP, ΔH and ΔW. The simplified residual calculation is explicitly conditional, not a qualified hot margin. | Define face paths, grades, temperature profiles, local growth, friction, axial play, loads and allowances. Check reverse motion and transients. |
| Is a cylindrical roller alternative worth considering? | NU 204 ECP boundary dimensions are manufacturer-supported. NU permits internal displacement; the 6204 pocket-space chain cannot certify that displacement. | Check exact internal travel/offset, load, speed, lubrication, fits and abutments before selection. |
| Does recessing the cover help? | Moving H_R alone by +0.200 increases all right-gap and total-space bounds by +0.200; left gap is unchanged. | Approve required directional travel and review cover/package/retention geometry. Largest clearance is not an optimization objective. |
| Can the application declare Pass? | No justified functional acceptance interval exists. No artificial acceptance band, project JSON or case-study PDF was created. | Approve functional limits before using AnalysisProject and report generation. |

The study explicitly excludes radial fit design, bearing load/life selection,
elastic contact, form errors, statistical yield and certification. Unknowns are
not assigned zero uncertainty to obtain a mechanical approval. In the illustrative
thermal allocation only, local width changes are deliberately frozen and labeled.

## Independent numerical method

`verify_calculations.py` converts decimal text directly to exact rational
numbers and enumerates physical endpoints. It establishes expected bounds
without calling the application's endpoint-selection formulas. Only after
those bounds are established does it compare the existing engine's three
public standalone calculation functions.

| Chain | Endpoint combinations | Minimum / nominal / maximum (mm) |
| --- | ---: | --- |
| Original H − W | 4 | 0.400 / 0.500 / 0.660 |
| Alternative H − W | 4 | 0.600 / 0.700 / 0.860 |
| Original H − W − P | 8 | 0.150 / 0.300 / 0.510 |
| Alternative H − W − P | 8 | 0.350 / 0.500 / 0.710 |
| Left gap P | 2 | 0.150 / 0.200 / 0.250 |

All **five chains / 26 endpoint combinations** agree with the engine.
Additional exact assertions verify the thermal difference, both conditional
right-gap intervals, the conditional left-gap interval, the positioning
counterexample, and the shared-P identity at all eight original H/W/P corners.
No binary floating-point arithmetic is used in these reference calculations.
These checks verify arithmetic and the stated model, not the physical inputs.

## Initial study verification

Executed from the repository root in the existing Python 3.14 virtual environment:

```sh
.venv/bin/python docs/case-studies/01-bearing-axial-clearance/verify_calculations.py
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

- Worksheet: all reference/engine comparisons and supporting assertions passed.
- Existing pytest suite: **700 passed, 4 skipped in 6.55 seconds**, 704 collected.
  The four opt-in Chrome application tests skipped because `AFA_BROWSER_URL`
  was not configured. They were not represented as executed in this task.
- Ruff lint: all checks passed. Final format check: 39 files already formatted.
- SHA-256 comparisons: all **33 pre-existing application, configuration and test
  files** match their pre-task hashes. No application code, engineering formulas,
  Decimal policy, persistence schema, resource limits, UI or PDF template changed.
- SVG XML parsed successfully. Chrome rendered the SVG embedded in HTML; all
  text bounds fit the viewBox and the screenshot was inspected. The diagram
  contains no image/script elements or external assets. A generic PDF/SVG
  renderer did not honor its CSS reliably; browser rendering is the reviewed
  presentation. No PDF report or new rendering dependency was added.
- The manufacturer catalogue and maintenance handbook were downloaded to
  temporary files for direct source verification. Manufacturer PDFs and their
  screenshots were not added to the repository. The catalogue hash and exact
  printed/PDF page mapping are recorded in the study.

Only documentation, the original SVG, its reproduction worksheet and the root
README's discovery link were added/changed. No Git commit or push was made.

## Historical documentation finalization verification

The follow-up task changed only the case-study README, SVG annotations and this
review record. The root README, reproduction worksheet, application, tests,
configuration, persistence schema, PDF layout and resource budgets are unchanged.
SHA-256 comparisons verified all **35 protected pre-existing files** captured
before this follow-up. Manufacturer references and their catalogue-execution
qualification are preserved; no new current-procurement verification is claimed.

### Drawing review findings

- H_L / H_R are housing stop planes; R_L / R_R are faces of the **outer ring**.
  W spans R_L → R_R, rather than an assumed assembled inner/outer-ring envelope.
- P spans H_L → R_L and g_R spans R_R → H_R. Chain A is H − W;
  Chain B is H − W − P. No surface or dimensional-arrow corrections were needed.
- A is the locating support; B's inner ring is retained and its outer ring is
  intended to slide. The two support roles remain distinct.
- The existing assumed-P footnote is retained. Annotations now explicitly say
  that fit and initial position are unverified and that this is a preliminary
  case study, schematic/not to scale, not a manufacturing drawing. Geometry,
  styling and numerical values are unchanged.
- Chrome rendering was inspected. All labels fit the viewBox; XML and local
  documentation links validated. No external image/script assets were added.

### JSON and PDF generation decision

There is no established repository example-project convention. Before creating
an `examples/` directory, the actual schema and report contracts were checked:

| Layer | Current requirement | Consequence for this preliminary study |
| --- | --- | --- |
| V1 JSON | `project.acceptance_limits` is mandatory, with finite decimal-string lower/upper bounds | No valid analysis-only JSON representation |
| AnalysisProject | Requires an AcceptanceLimits instance | Cannot construct a truthful project without justified limits |
| PDF | Requires a project-backed engine result, acceptance limits and Boolean Pass/Fail; verifies consistency | No supported analysis-only report |

All four H/W/P configurations were probed **in memory** through `loads_project()`
with missing, null and empty acceptance limits: **12 expected rejections**.
The errors identify `acceptance_limits`; null limits are rejected after the
dimension rows have passed reconstruction. The missing-analysis PDF input was
also rejected with `ReportError`. No invalid sample documents were saved.

**JSON validation of generated examples: not applicable — zero generated. PDF
content verification: not applicable — zero generated.** Generation stopped at
the unsupported analysis-only boundary as requested. No threshold was invented
and no expected result bound was recast as a functional requirement. The README
provides the exact four input configurations, current Streamlit limitation, and
conditional instructions for future use after real limits are approved.

### Commands and results

```sh
.venv/bin/python docs/case-studies/01-bearing-axial-clearance/verify_calculations.py
AFA_BROWSER_URL=http://127.0.0.1:8508 .venv/bin/python -m pytest
AFA_BROWSER_URL=http://127.0.0.1:8508 .venv/bin/python -m pytest tests/test_browser_safety.py::test_rejected_uploads_keep_numeric_edits_and_confirmation -v
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

- Worksheet: five chains / 26 endpoint combinations matched the independent
  rational reference. All four requested chain results, supporting left gap,
  +0.054 thermal estimate, conditional residuals and counterexample passed.
- Full pytest run: **703 passed, 1 failed in 37.35 seconds; no skips**. Chrome
  was installed, and all four existing browser tests executed against a temporary
  local server on port 8508. All 700 non-browser tests and three browser tests
  passed. No test code was changed.
- The failure was `test_rejected_uploads_keep_numeric_edits_and_confirmation`
  at `tests/test_browser_safety.py:164`: immediately following a rapid canvas
  cell edit and metadata edits, downloaded JSON contained `10.000` instead of
  `10.123456789012345678901234567890000`. This occurred before its rejected-upload
  loop. The unchanged test's isolated rerun **passed in 36.90 seconds**.
  This is an observed intermittent edit/export failure, not a diagnosed test-only
  problem or a confirmed new application regression. Its cause was not resolved
  in this documentation task. Do not describe the full-suite run as clean;
  investigate separately before claiming consistent browser edit/export behavior.
- Ruff lint: all checks passed. Format check: **39 files already formatted**.

## Subsequent release corrections

The software limitations and intermittent export observed above were subsequently
investigated; see [release correction evidence](../../release-corrections.md).
Analysis-only projects now use null limits and no verdict, persist in schema
version 2, and generate explicitly unassessed reports. The rapid-edit export
failure was reproduced and traced to the editor synchronization debounce; it
was not dismissed as a flaky test. The correction buffers committed edits
immediately before explicit actions collect the complete widget snapshot.
The records above retain the exact historical test results; the linked release
record contains current verification. No physical bearing assumptions or
manufacturer qualifications were changed by these software corrections.

## Reproducible analysis-only artifacts — 19 October 2026

Four schema-version-2 projects and four corresponding engineering PDFs are now
bundled in [examples/](examples/), superseding the historical absence of exports
recorded above. They retain the preliminary designation and use explicit null
acceptance limits. No functional requirement or acceptance threshold was added.
The [study artifact table](README.md#analysis-only-json-and-pdf-support) links
every project and report.

### Artifact verification

- Generated JSON with `save_project()` and reloaded every file with
  `load_project()`. Checked canonical serialization and a second in-memory
  `dumps_project()` / `loads_project()` round trip.
- Checked schema version 2, `mm`, explicit null limits, dimension order, IDs,
  labels and signs. Compared every input Decimal's `as_tuple()` with its exact
  source string, including trailing zeros. Both project limits and result
  verdicts are `None` in all four cases.
- Original C: **0.400 / 0.500 / 0.660 mm**; original g_R:
  **0.150 / 0.300 / 0.510 mm**. Alternative C:
  **0.600 / 0.700 / 0.860 mm**; alternative g_R:
  **0.350 / 0.500 / 0.710 mm**. Order is minimum / nominal / maximum.
- Generated reports only with `generate_pdf_report(analyze_project(project))`.
  Extracted every PDF with pypdf: verified project names, units, complete input
  rows, exact results, contribution totals and the matching JSON SHA-256.
  Every report states **Acceptance: Not assessed** and explicitly says no
  functional assessment was performed. No standalone Pass or Fail word appears.
- All four reports have two pages. Rendered all eight pages with PyMuPDF and
  visually inspected representative result and input/trace pages: labels wrap,
  numeric values remain readable, and no layout correction was required.
  Regeneration produced identical PDF bytes in the verification environment.
- The original schematic, independent worksheet, application sources, tests,
  project configuration and manufacturer-reference section were retained.

### Commands and results for this artifact completion

```sh
.venv/bin/python docs/case-studies/01-bearing-axial-clearance/verify_calculations.py
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

- Independent worksheet: **five chains / 26 endpoint combinations passed**;
  thermal arithmetic, conditional residuals, shared-P identity and the position
  counterexample also passed. The worksheet itself does not generate artifacts.
- Pytest: **748 passed, 6 skipped in 6.79 seconds**. The six opt-in browser tests
  were not enabled for this artifact-only task; no new browser verification is
  claimed. Persistence, PDF, analysis-only and UI state tests passed.
- Ruff lint: **all checks passed**. Ruff format: **41 files already formatted**.
- These checks verify reproducibility and internal consistency, not current
  manufacturer procurement data or complete mechanical suitability.

## Publication decision

The material can be presented as a **preliminary feasibility and tolerance-modeling
exercise**. It demonstrates a useful design-review finding: a valid stack-up
equation is insufficient when the physical freedom and datum paths are wrong
or missing. It is not ready to claim a validated bearing assembly or operating
clearance guarantee. Complete the seven engineering gates in the study and
obtain a separate engineering review before removing the draft designation.
