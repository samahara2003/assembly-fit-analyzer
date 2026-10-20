# V1.0 release preparation

Prepared 20 October 2026. Package metadata is **1.0.0**. No commit, remote
repository, tag or published release was created during this preparation.

This records the initial release-preparation run. The subsequent
[pre-publication review](pre-publication-review.md) supersedes its licensing,
Python-minimum compatibility and final artifact status. Historical verification
results and wheel digests below are retained as evidence of that earlier run.

## Repository audit

- Git branch `main` has no commits. All project files are initially untracked;
  an ordinary tracked-file diff is therefore insufficient for review. Review
  the complete publishable file list before the first commit.
- An existing HTTPS `origin` points to `samahara2003/assembly-fit-analyzer` on
  GitHub and contains no embedded credentials. It was neither created nor
  modified. Its visibility and hosted state were not queried.
- No license exists. None was selected or added. **Owner approval of a license
  and its scope is a publication gate**, not a completed action. Do not describe
  this repository as licensed open-source software until that is resolved.
- No existing GitHub workflows or repository screenshots were present. The new
  workflow and actual worked-example screenshot address those gaps.
- The local virtual environment, Python/pytest/Ruff caches, egg-info, build
  output and wheels are generated local artifacts. They remain on disk and are
  ignored; none was deleted. Agent configuration and common credential paths
  are now ignored as well. Ignore rules are not a substitute for reviewing files.
- The four case-study PDFs are intentional published evidence and remain
  included alongside their JSON inputs. They are not build caches. Their
  original application-version provenance is preserved; they record version
  0.1.0, while new V1.0 reports record the installed 1.0.0 metadata.
- A scan of publishable files found no common credential signatures or
  credential-like filenames. This is a bounded review, not a comprehensive
  security certification or dependency-vulnerability audit. No application
  source, test, theme, schema, calculation or case-study artifact was changed.
- Historical machine-specific temporary paths were replaced with portable
  descriptions in the release-correction record. Public documentation contains
  no hardcoded user home or machine-specific absolute filesystem paths.
- Package repository metadata uses that existing configured origin. Author
  metadata was not invented. Confirm the target before pushing; approve
  licensing before adding license metadata or a LICENSE file.

## Verification environment and CI

The package retains `requires-python = ">=3.11"`. This release was verified on
macOS with CPython **3.14.0**, Streamlit **1.66.0**, ReportLab **4.5.1**, pytest
**9.1.1**, Ruff **0.17.1** and Chrome **155.0.8059.85**. The declared Python 3.11
minimum was not executed in this task; do not imply a complete Python/OS matrix.

`requirements/ci.txt` pins Python dependencies and build tools for Python 3.14
macOS/Linux verification. It includes the Linux-only watchdog dependency.
Pins were installed into a fresh environment, and a separate Linux/Python 3.14
wheel-resolution dry run succeeded, explicitly including watchdog. These pins
are not a universal Windows/Python-version lock or a guarantee of byte-identical
whole environments. Package extras retain their existing compatibility ranges.

[GitHub Actions](../.github/workflows/ci.yml) runs on pushes and pull requests:

1. **Tests, artifacts and wheel:** Ruff lint/format, all non-browser tests, the
   independent case-study worksheet, JSON/PDF integrity verification, wheel
   build/ZIP inspection and an installed-wheel smoke test outside the source tree.
2. **Six Chrome regressions:** install Chrome and its system dependencies, start
   a dedicated localhost Streamlit process, poll its health endpoint, run the
   browser test file, and stop the owned server on exit. Playwright imports and
   the Chrome version are checked explicitly. The browser URL is always set;
   these tests are not silently omitted from CI.

Both jobs use Ubuntu 24.04/Python 3.14, exact dependency pins and immutable
official action commits: checkout v7.0.1 and setup-python v7.0.0, verified against
their official GitHub release refs. Permissions are read-only and checkout does
not retain credentials. There are no publishing steps, secret inputs, private
services or external application backends. Public package/browser downloads are
required; Chrome, interpreter patches and OS packages can change externally.

Workflow validation passed with actionlint 1.7.12 (external ShellCheck and
Pyflakes integrations disabled). **Hosted GitHub execution remains unverified**
until the owner authorizes a push and both jobs complete on GitHub. Local Chrome
success and Linux wheel availability do not substitute for that first hosted run.

## Initial verification record

Use an activated fresh Python 3.14 virtual environment from the repository root:

```sh
python -m pip install -r requirements/ci.txt
python -m pip install --no-build-isolation -c requirements/ci.txt -e '.[dev,ui,browser]'
python -m pip check
python -m ruff check .
python -m ruff format --check .
python docs/case-studies/01-bearing-axial-clearance/verify_calculations.py
python tools/verify_case_study_artifacts.py
python -m pip wheel --no-build-isolation --no-deps --wheel-dir dist .
python -m zipfile -t dist/assembly_fit_analyzer-1.0.0-py3-none-any.whl
```

Fresh installation succeeded; pip check reported **no broken requirements**.
Ruff lint passed and the final format check reported **44 files already formatted**.
The worksheet passed **five chains / 26 physical-endpoint combinations**, plus
the thermal arithmetic, shared-position identity and counterexample assertions.
All **four schema-v2 JSON / PDF pairs passed** the new integrity helper: exact
Decimal representations and order/signs, null limits, `passes=None`, expected
results, full PDF input rows, totals and input SHA-256, and no acceptance verdict.
Fresh report generation was deterministic without changing bundled reports.

For the complete suite, a dedicated test server was started in that environment:

```sh
python -m streamlit run streamlit_app.py --server.headless true --server.address 127.0.0.1 --server.port 8511 --server.fileWatcherType none
```

In another activated terminal:

```sh
AFA_BROWSER_URL=http://127.0.0.1:8511 python -m pytest
```

Result: **754 passed in 173.49 seconds; no skips or failures**. All six Chrome
tests executed against the fresh V1.0 installation. A preceding full run in the
original environment also passed **754 tests in 123.93 seconds**. No test timing
or assertions were relaxed. The new screenshot is an actual browser capture.

An existing external independent audit harness was rerun separately: **1,207
exact-rational reference projects**, their JSON/UI adapter round trips and
**seven deterministic PDF cases passed**, along with malformed/resource-input
checks and an actual atomic save/load. That temporary audit harness is not a
bundled CI command; the repository worksheet and pytest suite are the supported
repeatable checks. These are numerical/software checks, not physical validation.

Wheel inspection passed: ZIP integrity, package version, Python requirement,
extras and all **19 packaged Python sources** matched the repository. No local
caches, credentials or environment paths were packaged. A second fresh
environment installed the wheel without dependencies and successfully imported
and calculated an exact analysis-only result **outside the source tree**.

Final inspected wheel (build output, intentionally ignored):

```text
assembly_fit_analyzer-1.0.0-py3-none-any.whl
36,562 bytes
SHA-256 1c39d3c4af90eebf866193488e2c957f6f227cddc26c10771ee2eb74f688310b
```

The wheel packages the Python library. The Streamlit launcher, theme,
documentation and example projects are used from the repository checkout;
installation/launch instructions make this boundary explicit. A future rebuild
can differ in ZIP timestamps or metadata; verify the final release artifact and
record its own digest. Documentation links and protected-file hashes are checked
again before handoff.

## Short release checklist

- [ ] Owner approves licensing; add the approved license and matching metadata.
- [ ] Review all initially untracked files, including PDF/screenshot provenance;
      rerun a credential scan and inspect the exact files selected for publication.
- [ ] Confirm the existing origin, repository visibility, description and URLs.
- [ ] Repeat the commands above after any release edits; review the
      [manual acceptance checklist](manual-acceptance.md), launch and downloads.
- [ ] Authorize the initial commit and push to the confirmed origin separately.
- [ ] Confirm **both** hosted CI jobs pass, including all six Chrome tests.
- [ ] Build and inspect the final 1.0.0 wheel; record its digest and verify the
      repository source archive includes the launcher, docs and all eight examples.
- [ ] Review the suggested notes below; only then authorize tag/release creation.

No engineering gate for a production bearing assembly is closed by this
software release. Case Study 01 must retain its preliminary designation.

## Suggested V1.0 release notes — draft, not published

Assembly Fit & Tolerance Analyzer provides local deterministic worst-case
analysis for signed linear 1D dimensional chains, using exact Decimal arithmetic
and traceable per-dimension endpoints and contributions.

- Streamlit workspace for editing, explicit analysis and interval visualization.
- Optional inclusive functional limits; analysis-only projects receive no verdict.
- Schema-v2 JSON projects preserve Decimal strings and contribution ordering;
  existing version-1 assessed projects remain readable.
- Engineering PDFs include input snapshots, traces, exact values and provenance.
- Preliminary bearing axial-clearance study with four reproducible JSON/PDF pairs.

Limits: consistent units and independently attainable endpoints are assumed.
No statistical analysis, GD&T, thermal simulation, CAD integration, bearing-life
validation or standards-compliance certification is provided. No licensing or
hosted-CI claims should be added until the corresponding checklist gates close.
