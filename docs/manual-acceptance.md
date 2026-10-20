# Streamlit V1 manual acceptance checklist

Install `.[dev,ui]`, run `python -m streamlit run streamlit_app.py` from the
repository root, and open the localhost address. This checklist is for reviewer
reproduction; automated tests cover the related adapters and state transitions.

- [ ] Open a fresh workspace. Confirm optional functional limits are empty
  and no calculated result appears before Analyze.
- [ ] Select Create or load a project → Use worked example → Replace workspace.
  Analyze and verify nominal **6.000 mm**, minimum **5.800 mm**, maximum
  **6.500 mm**, and **Pass** at the inclusive limits.
- [ ] Inspect all five chart labels, expand exact results, and review both
  contribution summary rows and the Total row. Verify totals match the metrics.
  Open Complete engineering trace and review all original inputs/endpoints.
  Verify the subtractive dimension uses its upper physical limit for the signed
  minimum and its lower limit for the signed maximum.
- [ ] Edit the name, unit, either functional limit, and a table cell in turn.
  Commit each edit and trigger a server action. Verify old results disappear and
  Analyze is required again. Buffered table edits alone leave the clearly labeled
  last-analyzed snapshot visible until the next action.
- [ ] Switch mm to inches. Confirm every entered number remains unchanged.
- [ ] Confirm dimension ID and sign appear first at the left. Scroll horizontally
  to reach other columns where needed. Verify sign help distinguishes addition/subtraction
  from physical lengths.
- [ ] Use Add dimension, edit the new row, and use Remove dimensions to delete
  it. Repeat using native table controls. Confirm remaining raw data and edited
  metadata survive structural actions and unrelated reruns, including invalid
  fields that have not yet been corrected.
- [ ] Paste a high-precision decimal string such as
  `10.123456789012345678901234567890`. Commit it, change the project name, and
  verify the full decimal string remains intact in the editor and exported JSON.
- [ ] Enter a malformed decimal, negative physical nominal, reversed deviations,
  duplicate ID, or blank required field. Analyze and verify actionable field/row
  errors while all edits remain present. Delete every row and verify the empty
  chain cannot be analyzed or exported.
- [ ] For a zero-crossing example, set A nominal to **4.000**, A deviations
  to **-0.100/+0.200**, B nominal to **4.000**, B deviations to **-0.300/+0.100**,
  and limits to **-0.200/+0.500**. Verify nominal **0**, range **[-0.200, 0.500]**,
  Pass, and a possible transition between clearance and interference.
- [ ] Change A nominal to **3.000** and functional limits to **-1.200/-0.500**.
  Verify negative gaps are retained, the range is entirely negative, and Pass.
- [ ] Test zero deviations and equal functional limits. Verify a point interval
  can pass and the chart remains visible. Test an interval that merely touches
  zero and verify it is not described as crossing zero.
- [ ] Tighten either functional limit just beyond a calculated endpoint.
  Verify Fail and a red out-of-limit segment on the appropriate side of the
  chart. Repeat with both endpoints outside and with the entire interval outside.
  No display rounding or hidden acceptance tolerance is used.
- [ ] Open Export project and select Download JSON. Inspect schema_version 2,
  decimal strings with trailing zeros, sign integers, and contribution order.
  Close the panel, edit a field without pressing Tab, then open Export project.
  Download and confirm the latest edit is included. There must be no download
  link while the panel is closed. Enter an invalid value and verify export shows
  an error instead of a previous valid file.
- [ ] Clear both functional limits, Analyze and verify analysis-only status.
  Download JSON and verify schema version 2 with null acceptance_limits. Download
  a PDF and verify Not assessed and the explicit no-assessment statement. Supply
  only one limit and verify rejection; load an existing version-1 assessed project
  and confirm its numerical values and Pass/Fail are unchanged.
- [ ] Commit a table cell then immediately edit metadata and open export; verify
  the exact latest value. Repeat against a cached PDF: opening its action must
  require Analyze again, never download an older snapshot.
- [ ] Upload that file and select Load uploaded project. Cancel replacement and
  verify unsaved edits remain. Load again and confirm replacement; verify exact
  inputs return and results await a new Analyze action.
- [ ] Upload malformed JSON, an unsupported version, an invalid UTF-8 file, or
  a file with unknown fields. Verify a clear error and unchanged workspace.
- [ ] Commit a new project name, lower limit `5.9000000`, and a long-precision
  table edit. Download JSON to verify these edits. Upload the exact UTF-8 text
  `{"schema_version":1,"project":{},"\ud800":1}` and select Load uploaded project.
  Verify a handled Unicode error, the editor stays visible, and all raw edits
  remain. Select New project then Keep editing; export again and compare inputs.
  Repeat with invalid Unicode keys inside project, a dimension, and acceptance limits.
- [ ] Try over-budget JSON files and fields from the [resource policy](resource-limits.md).
  Verify rejection preserves edits and does not offer replacement confirmation.
  Confirm a valid upload still requires approval before replacing the workspace.
- [ ] Use Markdown-like project names/labels, including image/link syntax and
  bare URLs. Verify literal display and no external images, links, or requests
  from metadata in the export panel or validation errors.
- [ ] Analyze a valid 251-dimension project. Verify the PDF action explains its
  250-dimension budget while analysis and full JSON export still work.
- [ ] Create a new project, cancel replacement, and verify work remains. Repeat
  and confirm replacement; verify the blank draft and cleared results.
- [ ] Inspect desktop and narrow-window layouts. Verify controls are readable,
  the table scrolls horizontally, and the chart scales to the viewport. At
  ordinary desktop widths the four-column summary should not require scrolling.
- [ ] Test very small and large dimensions. Verify compact metric labels,
  available exact values, offset labels when absolute values coincide in compact
  notation, and an actionable error if the engine resource
  envelope is exceeded. A chart display guard must not alter engineering results.
- [ ] Download work before refresh/restart. Confirm the application does not
  promise autosave or persistent recovery of an unfinished session.
- [ ] Follow the [PDF reporting review checklist](pdf-reporting.md), including
  exact values, physical/signed endpoints, multipage continuation, and stale
  report prevention. PDF generation failures must not block JSON export.
