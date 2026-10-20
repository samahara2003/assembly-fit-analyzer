# Analysis-only projects and committed-editor export correctness

## Diagnosis

The previous acceptance requirement was an application contract, not an
arithmetic dependency: domain projects required AcceptanceLimits, schema 1
required a complete limits object, and report validation/rendering assumed a
Boolean verdict. Standalone dimensional functions already worked without
limits. Supporting an optional assessment requires no new engineering model.

The stale export was reproduced as a real application race, not dismissed as
test flakiness. In a controlled 12-edit browser run, **9 exports contained the
previous input nominal**. Outgoing Streamlit widget-state frames showed a name
edit at approximately 48 ms and export opening at 105 ms; the newly committed
table cell appeared only at 174 ms. JSON stores inputs, so this was an old input
snapshot rather than an incorrect worst-case calculation.

Streamlit 1.66.0's default editor mode debounces widget-state synchronization
by 150 ms. The export panel's rerun cannot collect a cell absent from frontend
widget state yet. Its otherwise-correct raw-snapshot comparisons and PDF cache
invalidation cannot revoke an already downloaded older file. Sleeping longer
in the test would hide the race without preventing a real user's rapid action.

Source: [Streamlit 1.66.0, useWidgetState.ts](https://raw.githubusercontent.com/streamlit/streamlit/1.66.0/frontend/lib/src/components/widgets/DataFrame/hooks/useWidgetState.ts),
the editor synchronization constant and the `syncEditState` implementation.
Both the installed frontend bundle and that versioned primary source were checked.

## Minimal corrections and contracts

- `AnalysisProject.acceptance_limits` defaults to `None`. A provided
  AcceptanceLimits object still requires two finite, ordered bounds; the object
  itself is not weakened. Invalid or partial objects remain errors.
- `analyze_project()` always returns exact dimensional values and traces.
  Without limits, both `acceptance_limits` and `passes` are `None`. This is not
  a Pass, Fail or a zero-width/synthetic acceptance interval. With limits, the
  existing inclusive comparison is unchanged. The legacy `analyze_worst_case`
  API still requires both bounds.
- Both blank UI limit fields (including whitespace) mean analysis only.
  Exactly one blank is an actionable validation error. Other malformed numeric
  input still passes through existing domain validation.
- Reports retain their existing visual layout. Analysis-only reports state
  **Acceptance: Not assessed** and **No functional acceptance assessment was
  performed; functional limits were not provided.** Bound rows say Not provided;
  their schematic has no invented functional interval. Dimensional tables,
  signed ranges and contribution traces are unchanged. A forged Boolean verdict
  without limits, or any inconsistent result snapshot, is rejected.
- The editor uses Streamlit's supported `on_change="ignore"` mode. That mode
  synchronizes committed cells to frontend widget state in a microtask without
  scheduling the debounced table rerun. The next explicit action submits those
  buffered values with the rest of the widgets. There is no production JavaScript
  injection, private widget-state manipulation, sleep, new dependency or form
  redesign.
- Table-only edits therefore do not automatically rerun the server. The table
  caption explains buffering and results are titled **Last analyzed results**.
  They are the previous analysis, not a claim about current unsynchronized edits.
  Analyze, export/report opening and other server actions collect committed
  inputs; changed snapshots invalidate the old PDF and hide old analysis.
  An active cell must be committed with Enter, Tab or leaving the field first.
- JSON/PDF download links exist only in their open panels. Opening them always
  refreshes/validates the input snapshot. A PDF for changed inputs requires
  reanalysis. Replacement confirmation, rejected-upload recovery and exact raw
  input preservation remain intact.

No dimensional equation, working Decimal context, input Decimal parsing,
resource constant or acceptance comparison was changed. The only engine change
is skipping the assessment and returning `None` when no limits were requested.

## JSON compatibility

| Document | Reader behavior |
| --- | --- |
| Version 1 with complete lower/upper object | Read unchanged, with the same dimensional values and Pass/Fail semantics |
| Version 1 with null/missing limits | Reject, preserving the original strict contract |
| Version 2 with complete lower/upper object | Read and assess with unchanged inclusive rules |
| Version 2 with `acceptance_limits: null` | Read as analysis only; no verdict |
| Either version with missing key, partial/empty object, invalid bounds or unknown fields | Reject |

All new saves use **schema version 2**; every existing key remains required.
Analysis-only status is explicit JSON null, never inferred from malformed fields.
All numbers remain exact decimal strings and contribution ordering is retained.
Loading version 1 and saving again writes version 2 without changing engineering
meaning. Version-1-only readers will reject new version-2 files and must be
upgraded; silently extending version 1 would obscure that incompatibility.

Canonical JSON now includes version 2, so input-reference hashes and PDF bytes
can change from earlier software for identical assessed dimensions. This is an
expected provenance change, not a calculation change. Repeated output is still
deterministic for the same inputs and software environment. Atomic saving and
application resource budgets remain unchanged.

## Regression evidence and reproduction

The original 12-sequence diagnostic, unchanged after correction, exported the
new exact nominal in **12 of 12** trials (formerly 3 of 12). No sleep was added
between cell commitment, metadata edits and export opening.

`tests/test_browser_safety.py` additionally holds the former 150 ms timer at
5 seconds in the test browser to expose the scheduling window deterministically.
The rapid-edit test immediately exports six successive high-precision changes,
compares JSON inputs, reanalyzes, extracts PDF values and checks the canonical
input SHA-256. It also opens a cached PDF action immediately after another cell
edit and requires reanalysis instead of offering the old download. The timer
control exists only in the test browser; production uses the supported mode.
Expected line wrapping is removed only from extracted PDF text during assertions.

Other checks cover domain defaults, partial inputs, exact round trips, old
version-1 documents, explicit analysis-only state, untouched assessed behavior,
signed ranges, no-assessment charts/reports, malformed/Unicode uploads, resource
budgets, and joint table/metadata snapshot changes. Browser PDF failures and
replacement cancellation are exercised alongside the new workflows.

From the repository root, install the existing `.[dev,ui,browser]` extras and
Google Chrome. Start a separate test server:

```sh
python -m streamlit run streamlit_app.py --server.headless true --server.address 127.0.0.1 --server.port 8509
```

In another activated terminal:

```sh
AFA_BROWSER_URL=http://127.0.0.1:8509 python -m pytest
python -m ruff check .
python -m ruff format --check .
python docs/case-studies/01-bearing-axial-clearance/verify_calculations.py
```

Without `AFA_BROWSER_URL`, the six opt-in browser checks skip. Explicitly record
that distinction rather than presenting skipped checks as passed. Analysis-only
support does not validate the physical assumptions of a bearing case study or
provide functional requirements on the engineer's behalf.

## Verification record

Verified 19 October 2026 in the existing macOS / Python 3.14 / Streamlit 1.66.0
environment with Google Chrome:

- Full suite with browser URL configured: **754 passed in 88.44 seconds**, no
  skips. All six Chrome checks executed. The two new browser workflows also
  passed separately before the complete run.
- Ruff lint: all checks passed. Format check: **41 files already formatted**.
- Independent audit worksheet: **1,207 exact rational reference projects**, their
  JSON/editor round trips, and **seven deterministic PDF cases** passed.
  The temporary audit script was adapted only to reject schema version 3 rather
  than the now-supported version 2; its numerical oracle was unchanged.
- The repository case-study worksheet: five chains / 26 corner combinations and
  its supporting thermal/counterexample assertions passed.
- All four bearing-case configurations additionally passed analysis-only JSON
  round trips and deterministic PDF generation/text extraction. Their reports
  contain Not assessed, the no-assessment statement and the exact documented
  results. Verification outputs were written to an external temporary directory;
  a rendered original Chain B
  first page was inspected. No production bearing validation is implied.
- AST/source comparisons confirm unchanged calculation functions (including
  Decimal working context, endpoint selection and inclusive comparisons), the
  Decimal input validator, resource-limit expressions, and project dependencies.
- Wheel command:
  `python -m pip wheel --no-cache-dir --no-deps --wheel-dir <temporary-wheel-directory> .`
  (the historical machine-specific destination is omitted here).
  Build succeeded; ZIP integrity and every packaged Python file matched source.
  Wheel size: 38,108 bytes. SHA-256:
  `83b9b7237207a8329a782f69497af439c81ff1cf0072605d41a871413def5e03`.
- `python -m pip check`: no broken requirements. Local documentation links resolve.

The previous stale-export failure was reproduced before correction and has not
recurred in the corrected controlled runs or final suite. This records the tested
environment, not a claim that every browser/Python combination was exercised.
No tests are knowingly failing. No Git commits or pushes were made.

## Changed files

```text
src/assembly_fit_analyzer/domain/models.py
src/assembly_fit_analyzer/calculations/worst_case.py
src/assembly_fit_analyzer/validation/resources.py
src/assembly_fit_analyzer/persistence/json_project.py
src/assembly_fit_analyzer/ui/workspace.py
src/assembly_fit_analyzer/ui/app.py
src/assembly_fit_analyzer/ui/visualization.py
src/assembly_fit_analyzer/reporting/pdf.py
src/assembly_fit_analyzer/reporting/visualization.py
tests/test_analysis_only.py                         (new)
tests/test_domain.py
tests/test_persistence.py
tests/test_streamlit_app.py
tests/test_browser_safety.py
README.md
docs/engineering-spec.md
docs/pdf-reporting.md
docs/resource-limits.md
docs/manual-acceptance.md
docs/release-corrections.md                         (new)
docs/case-studies/01-bearing-axial-clearance/README.md
docs/case-studies/01-bearing-axial-clearance/review.md
```

Case-study source qualifications and preliminary status are preserved. Its
historical review entries remain labeled as historical; current capability
instructions now explain truthful analysis-only export. No bearing drawing,
new engineering calculator, UI arrangement or PDF table/page design was changed.
