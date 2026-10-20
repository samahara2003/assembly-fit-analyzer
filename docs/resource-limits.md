# V1 application resource limits

These are local application I/O and rendering budgets. They do not change the
domain models, worst-case equations, Decimal context, or acceptance comparisons.
The constants live in `validation/resources.py`.

| Resource | Inclusive maximum | Rationale |
| --- | ---: | --- |
| JSON document/upload | 8 MiB (8,388,608 UTF-8 bytes) | Ample space for ordinary 1D chains while bounding parser and browser payloads. |
| Dimensions per project | 1,000 | Supports substantial linear chains with bounded validation/editor work. |
| Project name | 512 characters | Keeps metadata practical without constraining normal descriptive names. |
| Dimension ID | 128 characters | Allows descriptive stable identifiers. |
| Dimension label | 8,192 characters | Allows detailed descriptions and existing long-label reports. |
| Each decimal input string | 10,032 characters | Accommodates the engine's 10,000-digit working envelope plus sign, point, and exponent notation. |
| Persistence diagnostic | 2,000 characters | Bounds browser diagnostics; longer messages end in an ellipsis. |
| Dimensions per PDF | 250 | Bounds report tables and pagination; larger projects retain analysis and JSON export. |
| Dynamic PDF text | 100,000 characters | Bounds long-number/label layout independently of row count. |

All limits apply together; satisfying every field limit does not guarantee that
the entire serialized document or report fits its aggregate budget. Character
limits count Python Unicode characters, not UTF-8 bytes. Raw JSON/editor field
lengths are checked before trimming or Decimal parsing. Export checks the stored
Decimal string representation. Redundant leading zeros, whitespace, and other
overlong spellings can therefore be rejected even if their numeric value is small.
No input is silently truncated, rounded, or removed to satisfy a resource budget.

## Enforcement and compatibility

- The browser file picker is limited to 8 MiB. The server checks uploaded byte
  length before decoding. `loads_project()` checks UTF-8 size before JSON parsing.
  `load_project()` reads at most 8 MiB plus one byte, including files that grow
  during the read. Deep/malformed JSON still receives a handled decoder error.
- JSON keys are checked for invalid Unicode before becoming diagnostics. Every
  `PersistenceError` message is UTF-8-safe, including errors containing unusual
  local file paths. Valid Unicode names/labels remain supported by JSON.
- Decoded contribution count and field lengths are checked before domain model
  construction. The UI applies the same limits to raw editor inputs before
  Decimal parsing. Invalid drafts stay editable; validation blocks analysis/export
  until corrected. Rows or text are never deleted to enforce a limit.
- JSON export applies the same project limits and counts encoded bytes during
  serialization. Over-budget saves fail before touching the destination; existing
  atomic-save guarantees remain in effect.
- PDF budgets are checked before engine consistency verification, font loading,
  table construction, and rendering. Dynamic text counts the project name, three (analysis-only) or five
  assessment values, three totals, six fields per input row (including sign),
  and six fields per trace row. Repeated values/IDs count at each occurrence.
  Fixed headings, units, provenance fields, and boilerplate are template-bounded.
  A PDF rejection leaves analysis and eligible JSON exports available.
- New saves use schema version `2`; version `1` remains readable with its original
  mandatory acceptance object. Version `2` also allows explicit null limits for
  analysis only. Public save/load/report signatures and resource budgets are unchanged.
  Previously accepted files or programmatically constructed projects exceeding
  these budgets are now rejected at application boundaries. Core domain and
  calculation APIs remain more general. PDF generation has a smaller workload
  envelope than project editing/JSON; JSON preserves the complete chain when a
  report exceeds its budget.

The separate arithmetic guards remain 10,000 working digits and operand
exponents in [-10,000, +10,000]. Passing an application budget does not establish
arithmetic eligibility, and arithmetic eligibility does not bypass aggregate
file/report budgets. The maximum supported working-precision example is covered
by an exact JSON/editor round-trip regression. These budgets are practical
workload bounds, not operating-system memory quotas or execution timeouts.

## Browser regression checks

Install the optional test extra and Google Chrome:

```sh
python -m pip install -e '.[dev,ui,browser]'
python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8507
```

In another activated terminal, run:

```sh
AFA_BROWSER_URL=http://127.0.0.1:8507 python -m pytest tests/test_browser_safety.py -v
```

These checks use headless Chrome, fresh browser sessions, actual downloads and
canvas edits. They cover Unicode errors, rejected uploads, numeric edit recovery,
replacement confirmation, literal metadata, blocked external resource attempts,
and PDF-budget failure with working JSON export. Without `AFA_BROWSER_URL`, these
six opt-in checks skip; the remaining suite needs no browser/server. Playwright
is a test-only extra and is not required to run the application.
