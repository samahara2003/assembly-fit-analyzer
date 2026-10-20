# Engineering PDF reports

## API and installation

Install `.[reports]` for the standalone PDF API, or `.[dev,ui]` for the full
workspace and tests. ReportLab is a reporting/UI extra; the core domain,
calculation engine, and JSON persistence still have no runtime dependencies.
pypdf is a development dependency for text-extraction tests.

```python
from datetime import datetime, timezone

from assembly_fit_analyzer.reporting import generate_pdf_report

pdf_bytes = generate_pdf_report(result)
# Optional, caller-supplied issue time:
issued_pdf = generate_pdf_report(
    result, generated_at=datetime(2026, 10, 19, 15, 30, tzinfo=timezone.utc)
)
```

`result` must come from `analyze_project(project)` and include its project,
optional acceptance limits, and complete ordered contribution traces. Analysis-only
results have `passes=None`; their reports say **Acceptance: Not assessed** and
**No functional acceptance assessment was performed**. Bound rows say Not provided,
and the chart retains its layout without an invented functional interval. Both
functional Pass and Fail results remain valid when limits are provided. Missing, nonfinite, wrongly typed,
or inconsistent result fields raise `ReportError`. Consistency verification
delegates to the existing engine; report layout never implements independent
engineering formulas or acceptance rules. The API returns complete PDF bytes;
callers choose their file/browser delivery mechanism.

## Contents and layout

The report uses portrait A4 pages with embedded regular/bold fonts, a repeated
application header, input-reference hash, units, and page-number footer.

1. **Assessment overview:** report title, full project name, application version,
   methodology, issue-time policy, canonical input SHA-256, explicit Pass/Fail or Not assessed,
   exact minimum/nominal/maximum and inclusive functional limits, signed-range
   interpretation, and a vector interval overview.
2. **Complete dimensional inputs:** original order, stable IDs, full labels,
   nominal values, signed deviations, and separate contribution signs.
3. **Auditable contribution trace:** physical minimum/maximum endpoints,
   signed minimum/nominal/maximum contributions, sign-selection explanation,
   and totals copied from the engine result.
4. **Assumptions and limitations:** 1D additivity, consistent units, independent
   and simultaneous attainability, model exclusions, inclusive comparisons,
   and the need to verify physical suitability. No standards certification or
   statistical probability is claimed.

All dimensional values are exact Decimal text, including trailing zeros,
negative results, and scientific notation. Table headings/introductions identify
the project units. Physical endpoints are separated from signed contributions.
The vector chart is schematic; only normalized page coordinates use floats.
If chart inputs exceed its display resource guard, the figure is omitted with
an explanation and all exact numerical values remain in tables.

Text wraps without shrinking to an unreadable size or truncating. Table headers
repeat on continued pages, and oversized rows can split within a cell. Blank
dimension cells on a continued row refer to the preceding identifier. Wrapped
numbers continue on the next line without changing their value; text extracted
from a PDF can contain layout line breaks within long numeric strings.

## Determinism and provenance

No automatic generation timestamp is inserted. By default the issue time is
explicitly shown as not supplied. Provide an aware `generated_at` datetime to
record a UTC issue time; equivalent timezones normalize to the same instant.
Naive datetimes are rejected. PDF internal dates use ReportLab's invariant
technical timestamp when no issue time is supplied; it is not an engineering
issue date. Explicit issue times also set PDF date metadata.

Identical input/result values, issue time, application version, and rendering
dependencies produce identical bytes. Byte identity across different ReportLab,
font, or Python versions is not promised. The SHA-256 identifies canonical JSON
project inputs; it is not a digital signature and does not certify the report.
Canonical JSON now uses schema version 2, so input-reference hashes can differ
from older reports for identical assessed dimensions; numeric results are unchanged.
Fonts are provided/embedded from the ReportLab distribution. Concurrent local
report requests are serialized around font subsetting/rendering.

## Streamlit behavior

Analyze first. **Download PDF report** opens a stateful panel, which verifies
the current input snapshot before showing **Download PDF**. Opening the panel
collects pending edits that have been committed by leaving their widgets. If
those edits differ from the analyzed draft, results/report controls disappear
and the engineer must Analyze again. A closed panel contains no download link.
Successful bytes are cached only for that raw analyzed draft; any synchronized input change
clears them. Generation errors show a message and leave the draft, calculation
result, and independent JSON export available.

## Limits and review checklist

The embedded Bitstream Vera font has limited Unicode coverage. Missing glyphs
and control characters are rejected explicitly with their field and code point;
they are never silently replaced by blank boxes. For unsupported labels, retain
the original JSON and use supported wording if a PDF is needed. Reports are
limited to 250 dimensions and 100,000 dynamic text characters, checked before
verification/rendering. See [resource limits](resource-limits.md) for exact counting
and compatibility. Over-budget reports leave analysis and JSON export available.
No PDF/A conformance, signatures,
certification, or physical engineering validation is claimed.

- [ ] Analyze the worked Housing/Insert example and download the PDF. Open it
  in a PDF viewer. Verify **6.000 mm nominal**, **5.800 mm minimum**, **6.500 mm
  maximum**, inclusive **5.800–6.500 mm** limits, and **Pass**.
- [ ] Verify every input row and sign. For Insert, verify physical endpoints
  **3.700/4.100 mm** and signed minimum/nominal/maximum
  **-4.100/-4.000/-3.700 mm**. Check totals against the assessment table.
- [ ] Clear both functional bounds, Analyze and download. Verify Not assessed,
  the explicit no-assessment statement, exact results and no functional interval.
  Supply only one bound and confirm validation prevents analysis/export.
- [ ] Tighten a functional bound to force Fail; verify it is reported explicitly.
  Review a negative range, a zero-crossing range, and a zero-width result.
- [ ] Review the chart against the numeric tables. Verify nominal and zero
  markers are distinct concepts and the physical interpretation is conditional.
- [ ] Edit any project field, including a pending name edit immediately before
  opening the report panel. Verify the old PDF cannot be downloaded and Analyze
  is required again. Reanalyze and verify the updated report metadata.
- [ ] Load a long chain with long labels/decimals. Check repeated headers,
  numbered footers, continuation, and that final rows/characters are present.
- [ ] Try an unsupported character and verify a field/code-point error. Confirm
  that JSON export and the current workspace remain usable.
- [ ] Generate the same report twice without an issue time and compare bytes.
  Optionally supply an aware issue time through the API and verify its UTC text.
