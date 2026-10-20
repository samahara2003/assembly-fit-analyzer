# Engineering specification

## Status and engineering problem

This document defines the intended V1 behavior of Assembly Fit & Tolerance
Analyzer. Immutable input models, input validation, deterministic worst-case
calculations, inclusive acceptance evaluation, and per-dimension traces are
implemented. Versioned local JSON persistence and a local Streamlit workspace
are implemented, along with deterministic engineering PDF reporting.

An assembly's functional dimension, such as a clearance or interference, can be
represented as a signed sum of component dimensions. Given each dimension's
nominal value and permitted deviations, determine the nominal assembly result
and its deterministic worst-case interval. Compare that complete interval with
user-defined functional acceptance limits and preserve enough input and result
detail to reproduce the analysis.

## Scope, assumptions, and limitations

V1 covers linear 1D additive chains, asymmetric dimensional deviations, signed
contributions, deterministic worst-case analysis, functional acceptance limits,
local JSON project files, PDF engineering reports, and a Streamlit interface.

- Every dimension and acceptance limit uses the project's single consistent
  unit, restricted to `mm` or `in`. Automatic unit conversion and dimensional
  inference are outside V1.
- Dimensional limits are independently attainable, including the simultaneous
  extremes used for worst-case analysis. Shared or correlated dimensions must
  not be modeled as independent contributions without engineering justification.
- Contributions are fixed coefficients of +1 or -1. Nonlinear geometry,
  angular stacks, thermal effects, elastic deformation, and multi-axis behavior
  are outside the model.
- There are no probabilities, distributions, statistical yield estimates,
  Monte Carlo calculations, GD&T, AI/ML, CAD integrations, authentication,
  databases, or cloud infrastructure.
- Mathematical consistency does not establish physical suitability, compliance
  with any standard, or engineering validation. Users must verify that the
  chain and assumptions represent their assembly.

## Data model

The implemented input models are frozen, slotted Python dataclasses exported
from `assembly_fit_analyzer.domain`. Their constructors validate every field;
stored numeric fields are `Decimal` values. Calculation outputs are frozen,
slotted dataclasses exported from `assembly_fit_analyzer.calculations`.
The V1 project file format is defined below.

| Entity | Required information |
| --- | --- |
| `AnalysisProject` | `name`, `unit`, `contributions`; optional `acceptance_limits` (default `None`) |
| `DimensionContribution` | `dimension_id`, `label`, `nominal`, `lower_deviation`, `upper_deviation`, `sign` |
| `AcceptanceLimits` | `lower`, `upper` functional limits in project units |
| `WorstCaseResult` | `nominal`, `minimum`, `maximum`, `passes`, `traces`, `acceptance_limits`, optional `project` snapshot |
| `ContributionTrace` | Original `dimension`, physical `minimum` and `maximum`, signed `nominal_contribution`, `minimum_contribution`, `maximum_contribution` |

Dimension and AcceptanceLimits constructor arguments remain mandatory.
`AnalysisProject` accepts a sequence of
validated contributions and stores an immutable tuple snapshot in input order.
Its optional assessment is an `AcceptanceLimits` instance or `None` for
analysis only. No schema version or serialization
behavior is attached to the domain models at this stage.

Dimension IDs allow validation errors and report rows to reference the original
inputs. Labels explain what each dimension represents. Optional project notes
may document engineering assumptions and the chain's positive reference
direction. A contribution's dimension limits are derived, not independent inputs.

JSON preserves project inputs and schema version. Loading validates the file
through these domain constructors before calculation. Derived results are not
stored and must be recomputed from the loaded project.

## Versioned JSON project format

New saves use schema version **2**. Version **1** remains readable and retains
its mandatory complete acceptance interval. In version 2, `acceptance_limits`
is either that same complete object or JSON `null` for analysis only. Its key
is always required. Missing fields, partial intervals, empty objects and
nonfinite bounds are rejected; no bounds are synthesized.

Old version-1-only applications cannot read version-2 saves; upgrade the reader.
Loading a version-1 document and saving it emits version 2 with the same values
and assessment. This changes canonical input hashes, not dimensional results.

### V1 JSON project format

The original shape below remains accepted unchanged:

The document is a UTF-8 JSON object with integer `schema_version: 1` and a
`project` object. The following defines its complete shape:

```json
{
  "schema_version": 1,
  "project": {
    "name": "Housing clearance",
    "unit": "mm",
    "contributions": [
      {
        "dimension_id": "A",
        "label": "Housing",
        "nominal": "10.0000",
        "lower_deviation": "-0.100",
        "upper_deviation": "0.2000",
        "sign": 1
      },
      {
        "dimension_id": "B",
        "label": "Insert",
        "nominal": "4.000",
        "lower_deviation": "0.000",
        "upper_deviation": "0.100",
        "sign": -1
      }
    ],
    "acceptance_limits": {
      "lower": "5.8000",
      "upper": "6.5000"
    }
  }
}
```

- Every field shown is required; additional fields are rejected at every object
  level. The root, project, each contribution, and acceptance limits must be
  objects (except the explicit version-2 null acceptance interval). Contributions must be a nonempty JSON array; its order is preserved.
- Names, units, IDs, and labels must be strings and satisfy the domain rules.
  Unicode text is supported; unpaired surrogate characters are rejected.
- All five types of dimensional fields (nominal, both deviations, both
  acceptance bounds) must be **JSON strings**, following the Decimal grammar
  in this specification. JSON numeric values are rejected for these fields,
  including integers.
  Finite values, deviation ordering, nonnegative physical lengths, and ordered
  acceptance limits are validated by the existing domain constructors.
- `sign` must be a JSON integer of `1` or `-1`; booleans and fractional numbers
  are rejected. `schema_version` must be the JSON integer `1` or `2`; booleans, strings
  and floating-point numbers are not valid versions. Unsupported versions are rejected without
  attempting migration. No migrations exist yet.
- Duplicate object keys, duplicate dimension IDs (after domain normalization),
  malformed JSON, nonstandard NaN/Infinity constants, and non-UTF-8 files are
  rejected. Comments, trailing commas, and a leading UTF-8 BOM are not accepted.

Serialization uses Decimal strings without conversion through float. This
preserves each Decimal's sign, coefficient digits (including trailing zeros),
and exponent on round trip. Original input spellings such as a leading `+`,
lowercase `e`, and whitespace are not preserved. Loading applies normal domain
text normalization to names, labels, and IDs. Domain-valid values beyond the
calculation resource envelope can be saved and loaded; calculation remains a
separate step that may raise `CalculationError`.

The writer uses sorted object keys, two-space indentation, unescaped Unicode,
uppercase Decimal exponent notation, LF newlines, and one trailing newline.
Identical domain inputs produce identical bytes independently of caller Decimal
context settings. Contribution arrays are never sorted. There are no generated
timestamps, cached results, traces, or application-specific UI state in files.

## Public persistence API and file behavior

The `assembly_fit_analyzer.persistence` package exports:

- `save_project(project, path) -> None`: save an `AnalysisProject` to a local path.
- `load_project(path) -> AnalysisProject`: read UTF-8 and validate/reconstruct inputs.
- `dumps_project(project) -> str`: generate deterministic V1 JSON text.
- `loads_project(text) -> AnalysisProject`: validate a JSON string without file I/O.
- `PersistenceError`: the common error type for document and file failures.
- `SCHEMA_VERSION`: the current write version, `2`; the reader also accepts version `1`.

Paths accept strings and string-valued path-like objects. Parent directories
must already exist. Errors identify the file where available, the affected JSON
location or field, and dimension ID where appropriate; malformed JSON includes
line and column. Underlying validation and I/O causes are retained as chained
exceptions. Missing Python function arguments use the usual `TypeError`.

Saving serializes and UTF-8 encodes before touching the destination. It writes
to a uniquely named temporary file in the destination directory, flushes and
`fsync`s the file, closes it, then uses `os.replace` to replace the destination.
Failures before replacement leave the old destination unchanged (or absent if
new). Temporary files are removed on handled failures; cleanup failures are
reported with their paths. Saving to an existing path overwrites it.

Atomic replacement depends on the local filesystem's rename guarantees. No
directory `fsync`, backup, file locking, or conflict detection is performed;
full durability through sudden power loss is not guaranteed, and concurrent
saves follow last-successful-replacement wins. Replacement uses the temporary
file's permissions rather than preserving existing metadata. It replaces a
destination symlink itself, rather than writing through it. A forcibly killed
process may leave a temporary file. JSON files are limited to 8 MiB; local reads
are bounded before decoding. Application field/count/report budgets and their
compatibility implications are specified in [resource limits](resource-limits.md).
Invalid Unicode keys and values are rejected with UTF-8-safe diagnostics.
These I/O budgets are independent of the arithmetic resource envelope below.

## Dimension limits and sign convention

For contribution `i`, let `n_i` be nominal, `l_i` lower deviation, `u_i` upper
deviation, and `s_i` sign:

```text
minimum_i = n_i + l_i
maximum_i = n_i + u_i
l_i <= u_i
s_i in {+1, -1}
```

Deviations are signed offsets, not absolute limits or unsigned tolerance widths.
They may be asymmetric and need not straddle zero. Equal deviations define a
zero-width dimensional interval. The nominal value need not fall in that interval
when both deviations are on the same side of zero.

V1 models physical lengths: nominal, minimum, and maximum must all be
nonnegative, including when the contribution sign is -1. Zero is permitted.
The sign describes chain orientation separately from the physical dimension;
it must not be encoded by making the physical length negative.

Choose one positive reference direction for the functional dimension. A positive
contribution adds the dimension along that direction; a negative contribution
subtracts it. The sign applies to the entire dimension interval, including its
deviations. The resulting chain value may be negative. Whether that means
clearance or interference depends on the user's explicitly documented chain.

## Worst-case calculation rules

```text
chain_nominal = sum(s_i * n_i)

contribution_min_i = minimum_i       if s_i == +1
                     -maximum_i    if s_i == -1

contribution_max_i = maximum_i       if s_i == +1
                     -minimum_i    if s_i == -1

chain_minimum = sum(contribution_min_i)
chain_maximum = sum(contribution_max_i)
```

Thus, the chain minimum uses a positive dimension's lower limit and a negative
dimension's upper limit, with the sign applied. The chain maximum uses a positive
dimension's upper limit and a negative dimension's lower limit, with the sign
applied. Subtraction reverses the interval endpoints. These bounds follow from
the linear additive model and independently attainable dimensional limits.

Example in millimeters: A has nominal 10, lower deviation -0.1, upper deviation
+0.2, and sign +1. B has nominal 4, lower deviation -0.3, upper deviation +0.1,
and sign -1. A spans [9.9, 10.2], and B spans [3.7, 4.1]. The chain A - B has
nominal 6, minimum `9.9 - 4.1 = 5.8`, and maximum `10.2 - 3.7 = 6.5`.

## Functional acceptance

Acceptance limits are user-defined absolute bounds on the functional result,
not deviations from its nominal value. Limits are inclusive:

```text
accepted = (chain_minimum >= acceptance_lower
            and chain_maximum <= acceptance_upper)
```

The complete worst-case interval must fit within the acceptance interval.
Nominal-only acceptance or partial overlap does not pass. For the example,
acceptance limits [5.8, 6.5] pass; [5.9, 6.5] fail. This outcome concerns the
stated dimensional model only, not overall assembly safety or suitability.
Acceptance bounds may be negative, positive, or zero. Both are mandatory when
assessment is requested. With no limits, `acceptance_limits` and `passes` are
`None`: dimensional results and traces are still produced, but no functional
assessment is performed. This state is neither Pass nor Fail. In the UI both
blank fields select analysis only; a single blank bound is rejected.
No rounding or hidden tolerance (epsilon) may affect acceptance comparisons.

## Input validation requirements

- Require a project name, a unit of exactly `mm` or `in`, and at least one contribution.
  An optional acceptance interval must contain both finite bounds. IDs must be nonempty and unique; labels nonempty.
- Nominal values, deviations, and acceptance limits must be finite `Decimal`
  values. Public constructors accept existing finite `Decimal` objects, integers
  (excluding booleans), or decimal strings. Reject binary floats, booleans, NaN
  (including signaling NaN), infinities, missing values, and malformed input;
  do not silently coerce invalid values or replace them with zero.
- Require `lower_deviation <= upper_deviation` for each dimension. Do not
  require a negative lower deviation or a positive upper deviation.
- Require each sign to be exactly the integer +1 or -1, excluding booleans.
- Require nominal physical lengths and both derived dimensional limits to be
  nonnegative. Deviations themselves may be negative.
- Require `acceptance_lower <= acceptance_upper`; equal limits are permitted.
- All inputs must share the declared unit; the application cannot infer or
  verify the units of bare numeric values.
- Reject nonfinite derived values or arithmetic overflow; verify ordered
  dimension and chain bounds before returning a successful result.
- Validation errors must identify the field and contribution ID where relevant.
  Invalid data must prevent calculation and successful report generation.

`ValidationError` is a `ValueError` with `field` and optional `dimension_id`
attributes, also included in its message. Missing constructor arguments produce
Python's `TypeError` naming the missing fields. Errors fail at the first invalid
field. An invalid or missing dimension ID cannot provide dimension context.
Names, IDs, and labels are stripped of surrounding whitespace and must remain
nonempty strings. Duplicate IDs are checked after this normalization. Unit
labels are exact and are not normalized.

## Decimal policy

Use Python `Decimal` for all dimensional calculations. Parse strings and
integers directly with `Decimal`, without converting through binary floats.
Decimal strings allow an optional sign, decimal point, and scientific exponent
with ASCII digits; surrounding whitespace is stripped. Grouping separators,
underscores, embedded whitespace, and non-ASCII digits are rejected. Preserve
input digits and scale; do not quantize or round inputs. Numerically negative
zero is treated as zero.

Input comparisons are exact and independent of the ambient Decimal context's
precision. In particular, physical-limit validation checks `nominal >= -deviation`
using exact sign reversal instead of computing a potentially rounded sum.

Calculations use an isolated Decimal context with precision sized to the
actual inputs. Let `E` be the smallest stored exponent and `A` the largest
adjusted exponent (position of the most significant digit) among all nominal
values and deviations, including zero values. For `N` contributions:

```text
working_precision = max(1, A - E + 1) + number_of_digits(2 * N)
```

The aligned digit span preserves all input places. Additional carry digits
cover the absolute sum of at most `2 * N` operands per chain endpoint, including
intermediate sums before cancellation. Sign reversal uses `copy_negate()`,
which does not round. Precision, exponent range, rounding mode, traps, and flags
are isolated from the caller; the caller's Decimal context is not modified.
The internal rounding mode is half-even, but all Decimal signals, including
`Rounded` and `Inexact`, are trapped: successful results never rely on rounding.

The calculation resource envelope is at most **10,000 working digits** and
stored and adjusted operand exponents in **[-10,000, +10,000]**. The working
context has `Emin=-10000` and `Emax=10000`. These implementation limits are
resource guards, not engineering limits or a claim of supported measurement
precision. Inputs outside the envelope, or arithmetic signals such as overflow,
raise `CalculationError` without returning a result. Input trailing zeros count
toward the envelope; there is no implicit normalization to bypass it. Domain
input parsing remains more general; a valid project can exceed the engine's
resource envelope. Acceptance limits only participate in exact comparisons and
are not subject to these arithmetic workspace guards.

Use unrounded values for calculation and acceptance checks. There is no
quantization, hidden tolerance, or clamping of negative results. Nonfinite or
unordered chain bounds cannot produce a successful result. Display precision
remains a future presentation decision and must not change outcomes.

## Public calculation API

`analyze_project(project: AnalysisProject) -> WorstCaseResult` is the preferred
entry point. The result retains the immutable project (including name, unit,
ordered inputs, and acceptance limits) and a tuple of traces in input order.
Each trace contains the original dimension's ID, label, nominal, deviations,
and sign through `trace.dimension`, alongside derived physical bounds and
signed contributions. The three signed contribution columns sum to the
corresponding three chain results.

The existing `analyze_worst_case(contributions, lower_limit, upper_limit)` API
remains available. It reuses domain chain validation and `AcceptanceLimits`,
returns the same calculated fields and traces, and sets `result.project` to
`None` because no project identity or unit was supplied. Callers must ensure
consistent units. `calculate_nominal`, `calculate_minimum`, and
`calculate_maximum` remain available and use the same validated arithmetic
path. Calling all three separately repeats analysis; use a full analysis when
all results are needed.

`meets_acceptance_limits(minimum, maximum, lower_limit, upper_limit)` validates
both intervals and performs inclusive containment checks. Its inputs follow
the same finite Decimal/string/integer rules as the domain models. Empty
chains, invalid members, duplicate IDs, and reversed intervals raise
`ValidationError`; a wrong project type also raises `ValidationError`. Missing
arguments use Python's normal `TypeError`. Result dataclasses are output
containers, not additional public input-validation boundaries.

## Expected output and traceability

### Streamlit workspace behavior

The local launcher is `streamlit_app.py`; install the optional `ui` extra and
run it from the repository root. `ui/app.py` orchestrates widgets and calls the
existing domain, calculation, and persistence APIs. `ui/workspace.py` contains
framework-independent adapters for immutable raw input snapshots, domain
construction, and uploaded UTF-8 bytes. `ui/visualization.py` handles display
normalization only. The engineering engine has no Streamlit dependency.

Nominal values, deviations, and acceptance limits are text inputs, including
text columns in the dynamic dimensional editor. Signs use explicit +1/-1
selections. No binary float conversion occurs in domain construction. A draft
can retain missing or malformed values; validation uses the existing domain
constructors and annotates dimension errors with editor row numbers. The first
error is shown after Analyze; invalid rows are retained for correction. Project
units are labeled millimeters or inches and never converted automatically.

The editor's source rows and widget identity remain stable throughout ordinary
reruns; returning edited values are captured separately as an immutable raw
snapshot. ID and sign columns appear first and use explicit widths; they are
not pinned and the table can scroll horizontally. Add dimension
and Remove dimensions provide visible structural controls alongside native
table editing. Explicit structural actions rebase from the complete current raw
draft and advance only the editor identity; metadata widget keys remain stable.
New suggested IDs avoid those already present; new physical values remain blank
until the user enters them. Removing rows never parses or normalizes other edits.
An explicit Analyze action calls `analyze_project()`. Results are shown only
when the current raw snapshot matches the analyzed snapshot, including metadata,
limits, row order, and all cells. Pending edits inside an active widget must be
committed with Enter, Tab, or leaving the field. `on_change="ignore"` writes
committed editor data to frontend widget state in a microtask instead of the
default 150 ms debounce. The next server action collects those buffered values.
Displayed results are explicitly the last analyzed snapshot until that action,
not an assessment of unsynchronized edits. Report/export opening always collects
current committed widget state before validating snapshots.

Creating a new project, selecting the worked example, or loading an uploaded
project first stages a replacement and asks for explicit confirmation. The
current draft remains available until replacement is confirmed. Invalid uploads
never replace the draft. Uploads use `loads_project()` via a UTF-8 bytes adapter;
exports use `dumps_project()`, without assuming browser access to server paths.
Export project opens a stateful panel and triggers a server rerun to collect
current widget/editor values. Only an open panel may render Download JSON,
using a freshly validated and serialized snapshot. A closed panel has no
download link; invalid inputs clear the export snapshot and show an error.
There is no separate Prepare action. Opening and downloading remain two browser
gestures: a direct download button can race a pending widget update. The panel
provides the synchronization boundary without reading private Streamlit state or
generating files on background threads. Committed edits while open are validated
again on rerun. No result or UI-only state is persisted in the JSON document.

Results show nominal and worst-case bounds, exact values, and traces. Complete
limits add inclusive Pass/Fail and acceptance bounds; absent limits show analysis
only with no functional assessment. Charts omit acceptance regions for that mode. Range descriptions use exact comparisons:
entirely positive, entirely negative, crosses zero, touches zero on either side,
or a zero-width interval at zero. A range crosses zero only when its minimum
is strictly negative and its maximum strictly positive. This means a possible
transition between clearance and interference for an appropriately defined
chain, not guaranteed interference. Touching zero is identified separately.

The interval overview labels acceptance bounds, calculated bounds, nominal,
and zero when zero lies within its data domain. Markers share one signed axis.
The allowed interval is shaded; relevant outside regions and out-of-limit
portions of the calculated interval are red. Equal acceptance bounds and point
results remain visible as markers and boundary guides. The domain also includes
nominal even when same-side deviations put nominal outside the result interval.
Positions are normalized using exact rational offsets from Decimal outputs;
only bounded position ratios are converted to floats for SVG coordinates.
This avoids cancellation from large shared offsets or absolute float overflow.
The chart is an overview: narrow intervals can overlap, and long displayed
numbers use compact notation. If distinct absolute values have identical
compact labels, endpoint labels explicitly switch to offsets from nominal.
Offset-label subtraction uses a separate isolated presentation context sized
for exact subtraction before compact formatting. No engine precision rule or
result is changed. Exact Decimal strings remain available separately and in
traces. Inputs beyond the chart's +/-10,000 stored/adjusted exponent guard omit
the overview without changing the result or acceptance decision.

A compact contribution summary contains dimension ID/label and signed minimum,
nominal, and maximum columns. Its Total row copies the existing engine outputs,
without recalculating sums in the UI. Complete engineering trace retains all
original inputs, deviations, physical endpoints, and signed contributions in an
expander. The default metric order is minimum, nominal, maximum. Functional
acceptance and signed-range classification are presented as separate concepts.

Drafts live only in the active Streamlit session. Reruns preserve them; browser
refresh, connection loss, and server restarts may not. There is no autosave or
cross-session recovery. The application asks users to download
valid work before leaving or replacing it.

A successful analysis will provide the chain nominal, minimum, and maximum;
any provided acceptance limits and their assessment (or `None` for both absent
limits and verdict). It will
include the project units and a per-contribution trace containing its ID, label,
nominal, deviations, sign, derived dimension limits, signed nominal contribution,
and selected signed minimum and maximum contributions.

PDF reports include that trace, project identity, input snapshot, assumptions,
application version, and an explicit optional issue time so a reviewer can
reproduce the result. JSON round trips must preserve input meaning. The UI, persistence,
and reporting layers should consume domain data and calculation results without
duplicating engineering rules. Calculation code should remain independent of
Streamlit, filesystem operations, and PDF libraries.

Engine tests cover worked examples, mixed signs, asymmetric, unilateral and
same-side deviations, zero-width intervals, inclusive acceptance, negative
gaps, invalid inputs, and resource limits. Independent rational-arithmetic
endpoint enumeration checks mixed-sign chains. Precision and determinism tests
exercise cancellation, reordered contributions, caller contexts, and immutable
traces. Passing software tests does not establish physical engineering
suitability or standards compliance.

### Engineering PDF reporting

`reporting.generate_pdf_report(result, *, generated_at=None) -> bytes` consumes
a complete `WorstCaseResult` with project, optional acceptance limits, and ordered
traces. Missing limits require `passes=None`; any Boolean verdict without limits
is rejected. Analysis-only reports say **Acceptance: Not assessed** and explicitly
state that no functional acceptance assessment was performed. They retain the
existing report layout, numeric tables, and traces.
`ReportError` reports invalid/inconsistent snapshots and rendering failures.
Legacy results without project context are rejected because project identity
and units cannot be inferred. Output containers are verified against
`analyze_project(result.project)` using the existing engine; there are no
independent tolerance formulas in reporting. Display values and totals are
copied from the supplied result. Signed-range wording is shared between UI and
reporting through `domain.interpretation`, with its old UI import preserved.

Reports use exact Decimal strings, including trailing zeros and exponents,
without quantization. They contain project metadata, methodology, explicit
inclusive Pass/Fail, signed-range interpretation, all dimensional inputs,
physical endpoints, signed per-dimension contributions and engine totals,
assumptions, and limitations. A vector overview shows functional/calculated
intervals, nominal, and zero where relevant. Only page coordinates use floats;
large display ranges may omit the figure without changing numeric outputs.

The project-input SHA-256 is a reproducibility reference for the canonical version-2
JSON input document, not a signature or certification. Application version is
recorded. No current time is read. A supplied timezone-aware `generated_at` is
printed in UTC and used for PDF date metadata. Without one, issue time is
explicitly not supplied; internal PDF timestamps use ReportLab's invariant
technical date (2000-01-01). Repeated inputs, issue time, and software/font
versions produce identical bytes. Rendering uses embedded fonts and serializes
ReportLab font-subsetting access across report requests.

A4 pages use repeated application/reference/unit headers, numbered footers,
wrapped text cells, and repeated column headers on continued tables. Very tall
rows may continue across pages; blank dimension cells carry the preceding
identifier. Unsupported font characters are rejected with field/code-point
errors, rather than being lost. Full details and manual review steps are in
[PDF reporting](pdf-reporting.md).

The Streamlit PDF action appears only for a completed current analysis (whether
analysis only, functional Pass or Fail). Opening the stateful report panel collects committed
widget changes before exposing a download link. No link exists while the panel
is closed. Input changes clear cached PDF bytes and hide reporting until
reanalyzed. Generation is explicit and failures leave inputs, analysis, and
JSON export intact. JSON input persistence and PDF result reporting are separate.
