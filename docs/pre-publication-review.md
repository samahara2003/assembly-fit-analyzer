# Final local pre-publication review

Review date: 20 October 2026. The owner approved public GitHub publication, MIT
licensing, English documentation, version 1.0.0 and publication of Case Study 01
as a preliminary engineering example. **No staging, commit, push, tag, release,
remote modification or visibility change was performed.**

## Confirmed licensing

[LICENSE](../LICENSE) contains the standard MIT terms and the owner-confirmed
notice **Copyright (c) 2026 Samahara Aguilar**. The exact name was requested and
confirmed by the owner because existing metadata did not establish a holder.
The GitHub username and effective Git author identity were not used to infer
legal ownership. The permission, notice and warranty paragraphs have no
additional restrictions; README identifies MIT licensing and links the file.
Canonical reference: [SPDX MIT text](https://spdx.org/licenses/MIT.html).

Package metadata declares `license = "MIT"` and `license-files = ["LICENSE"]`.
The build floor is now `setuptools>=77.0.3`, matching support for SPDX license
expressions and license-file metadata; CI already pins setuptools 84.2.0.
See [setuptools packaging documentation](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html).
The final verification wheel includes the exact confirmed LICENSE file and MIT
SPDX expression. No author email or unconfirmed authorship metadata was added.

## Git state and proposed initial commit

- Current branch: `main`; no commits; no tracked/staged files.
- Fetch and push origin: `https://github.com/samahara2003/assembly-fit-analyzer.git`.
  It matches the project name and package repository URL, appears to be the
  intended target, and has no embedded credentials. It was not modified.
- Remote repository contents, visibility and authenticated ownership were not
  queried or changed. Confirm those before any push; public approval alone is
  not evidence of the repository's current visibility.
- The exact proposed paths are in [initial-commit-files.txt](initial-commit-files.txt).
  It includes itself and this review; no paths were staged. Recheck that list
  after edits. Local environments, caches, egg-info, `build/`, `dist/`, credential
  files and agent configuration are excluded by the existing ignore rules.
- Effective Git author name/email are configured outside project files. The
  email is **not a GitHub noreply address**. No private address was copied here.
  Confirm consent to publishing that email, or select the owner's verified
  GitHub noreply address before creating the first commit or annotated tag.

The inventory contains **63 files**: 19 package sources, 12 test files, 23
documentation/example/screenshot files, five root files, and one file each for
GitHub CI, Streamlit configuration, dependency pins and the artifact verifier.
The five root files are LICENSE, README.md, pyproject.toml, streamlit_app.py and
.gitignore. All eight case-study artifacts and the screenshot are included.

## Security, privacy and artifact review

The publishable files were scanned for common private-key headers, AWS keys,
GitHub tokens, credential assignments, personal email addresses and machine-
specific absolute filesystem paths. No such content was found. The confirmed
copyright-holder name and GitHub username are intentional public identity data.
No symlinks,
environment/credential files, local caches or binary over 1 MiB appears in the
proposed set. GitHub username/URL and manufacturer names are intentional public
references. This is a bounded local review, not a comprehensive vulnerability
scan or a guarantee that every possible secret format has been recognized.

The four JSON examples contain assumed/qualified engineering inputs and null
acceptance limits. All four PDFs have two pages and retain their original
version-0.1.0 provenance. Their metadata identifies the application, with no
personal author/path. Every page was checked: no annotations, automatic actions,
JavaScript names, forms or embedded files were found. Exact values, input rows,
trace totals and JSON SHA-256 references passed production-API/text verification.
The four PDF sizes are 46,434–46,627 bytes; these are intentional example assets.

The screenshot is a 1440 × 1900 PNG, 142,140 bytes, with no metadata. Its actual
worked-example display contains generic housing/insert inputs and results, not
personal/project data. The SVG has no scripts, event handlers or external
resource references. No manufacturer catalogue PDF or proprietary dataset is
bundled. Case-study source qualifications and preliminary limitations remain.

Protected-file hashes cover application sources, tests, theme, launcher, case-
study files and screenshot. Those files were not changed. No potentially useful
local artifact was deleted. README/license/release documentation and packaging
metadata are the only intended publication-preparation changes.

## Configuration and compatibility

Version remains 1.0.0. The package declares Python >=3.11 and keeps the existing
optional-extra dependency ranges. CI remains Python 3.14/Ubuntu 24.04, with
immutable action references and separate non-browser and six-test Chrome jobs.
The server is health-checked and stopped on exit; no private credentials or
application services are required. Hosted CI is still pending the authorized
first push. Workflow validation passed with actionlint 1.7.12, with external
ShellCheck/Pyflakes integrations disabled.

Python 3.11 was provisioned into a temporary directory, without changing system
Python or adding a project dependency. A clean Python 3.11.17 environment installed
`.[dev,ui,browser]` successfully using the declared ranges. It resolved NumPy
2.4.6 and pyee 13.0.1, instead of the Python-3.14-only NumPy 2.5.4/pyee 14 pins.
The existing `requirements/ci.txt` is explicitly a Python 3.14 snapshot; it must
not be installed unchanged on Python 3.11. Both environments use Streamlit
1.66.0, ReportLab 4.5.1 and pytest 9.1.1. Pip check passed for Python 3.11.

Python 3.11.17 passed the complete browser-enabled suite. This supports the
declared minimum with its compatible dependency resolution on macOS, without
implying that every 3.11 patch or dependency combination was tested. No Windows
execution or hosted Linux run is claimed.

## Verification commands and outcomes

Commands use the corresponding activated environment, from the repository root.
Dedicated test servers ran on 8512 (Python 3.14) and 8513 (Python 3.11):

```sh
python -m streamlit run streamlit_app.py --server.headless true --server.address 127.0.0.1 --server.port 8512 --server.fileWatcherType none
```

```sh
AFA_BROWSER_URL=http://127.0.0.1:8512 python -m pytest
```

Python 3.14.0: **754 passed in 120.83 seconds, no skips/failures**. All six Chrome
tests executed. The Python 3.11 run uses the same commands with port 8513.
Python 3.11.17: **754 passed in 98.87 seconds, no skips/failures**, including all
six Chrome tests.

```sh
python -m pip check
python -m ruff check .
python -m ruff format --check .
python docs/case-studies/01-bearing-axial-clearance/verify_calculations.py
python tools/verify_case_study_artifacts.py
python -m pip wheel --no-build-isolation --no-deps --wheel-dir dist .
python -m zipfile -t dist/assembly_fit_analyzer-1.0.0-py3-none-any.whl
```

The independent worksheet and JSON/PDF verifier passed on both Python versions:
five chains / 26 corners plus supporting checks, and all four example pairs.
Wheel ZIP, version, MIT expression, embedded license and all 19 packaged Python
sources passed inspection. Final packaging and lint outcomes appear below.

- Ruff lint passed; format check reported **46 files already formatted**.
- Pip check passed in both interpreter environments.
- Actionlint passed for the unchanged workflow. The local documentation/image
  links resolve, and no machine-specific absolute paths appear in public docs.
- The final wheel is **37,578 bytes**, with SHA-256
  `0f2d0dd7e88b63c964269eca579b5548973584d69ce582f71c2e2bcdb9958df0`.
  Its packaged LICENSE exactly matches the confirmed notice and standard terms.
- A new isolated environment installed that final wheel without dependencies;
  outside the source tree, exact assessed and analysis-only calculations, package
  metadata and packaged licensing passed a smoke test.
- Final index/remote checks confirm no staging or remote modification. Protected
  source/test/theme/case-study/screenshot hashes remain unchanged.

The earlier release-preparation wheel digest is historical; this MIT-bearing
wheel supersedes it. Rebuilds may differ in ZIP timestamps. The remaining gates
are owner approval of the initial contents/public Git identity and permission to
commit/push, then both hosted CI jobs before any tag or release. Visibility and
remote history must be confirmed without silently changing them.

## Proposed publication sequence — publishing steps not executed

Read-only local inspection was performed; no staging, commit, push, tag or
release command below was executed. Stop at each authorization gate.
The GitHub CLI is not installed in the tested
environment; install/authenticate it separately if using the `gh` commands below,
or inspect the same repository/run/release in GitHub's web interface. Do not put
tokens in command history or project files. No repository/visibility creation
command is included.

### 1. Read-only review and confirm public Git identity

```sh
git status --short --untracked-files=all
git remote -v
git branch --show-current
git ls-files --cached --others --exclude-standard
cat docs/initial-commit-files.txt
git config --get user.name
git config --get user.email
```

The copyright notice is finalized with the owner-confirmed name. Choose the
intended public commit identity locally if the effective identity is unsuitable.
Any later license/metadata change requires a new wheel build and inspection.
Review the actual files, not just the filenames. After installing GitHub CLI:

```sh
gh auth status
gh repo view samahara2003/assembly-fit-analyzer --json nameWithOwner,visibility,url
git ls-remote --heads --tags origin
```

These commands read remote state. Stop if the target is wrong, visibility is not
the approved state, or remote history requires reconciliation. Do not change
visibility or force-push as part of this sequence. Confirm a clean initial remote
or agree a separate history-reconciliation plan.

### 2. Only after explicit authorization: stage the reviewed paths and commit

```sh
git add --dry-run --pathspec-from-file=docs/initial-commit-files.txt
git add --pathspec-from-file=docs/initial-commit-files.txt
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git diff --cached
```

Stop and compare the staged filenames with the approved inventory; inspect binary
assets separately. Include only reviewed files, and check the author email again.
Then, if the review is satisfactory:

```sh
git commit -m "Initial release: Assembly Fit & Tolerance Analyzer 1.0.0"
git show --stat --oneline HEAD
git status --short
```

### 3. Only after explicit push authorization: push to the existing origin

```sh
git push --dry-run origin main
git push --set-upstream origin main
```

Do not use `--force`, replace the remote, or automatically merge unrelated history.

### 4. Require both GitHub Actions jobs for the exact pushed commit

```sh
git rev-parse HEAD
gh run list --repo samahara2003/assembly-fit-analyzer --workflow ci.yml --branch main --event push --limit 5 --json databaseId,headSha,status,conclusion
```

Select the run whose `headSha` exactly matches the reviewed commit. Substitute its
numeric run ID for RUN_ID in the following commands:

```sh
gh run watch RUN_ID --repo samahara2003/assembly-fit-analyzer --exit-status
gh run view RUN_ID --repo samahara2003/assembly-fit-analyzer --json headSha,conclusion,jobs
```

Confirm both the core/build job and six-Chrome-test job completed successfully.
If code or documentation changes, repeat review and require CI for the new commit.

### 5. Only after separate tag authorization: tag that reviewed commit

```sh
git status --short
git rev-parse HEAD
git tag --list v1.0.0
git tag -a v1.0.0 -m "Assembly Fit & Tolerance Analyzer 1.0.0"
git show --no-patch v1.0.0
git push origin refs/tags/v1.0.0
```

Require a clean workspace and the same SHA that passed both jobs; stop if the tag
already exists. Do not move or replace it. Rebuild/inspect the final wheel from
the tagged state, and compare its installed sources to that state. The tag push
also triggers CI; wait for that run before publishing.

```sh
gh run list --repo samahara2003/assembly-fit-analyzer --workflow ci.yml --event push --limit 5 --json databaseId,headBranch,headSha,status,conclusion
gh run watch TAG_RUN_ID --repo samahara2003/assembly-fit-analyzer --exit-status
gh run view TAG_RUN_ID --repo samahara2003/assembly-fit-analyzer --json headBranch,headSha,conclusion,jobs
```

Replace TAG_RUN_ID with the numeric run whose branch/tag is `v1.0.0` and SHA
matches the reviewed commit. Both jobs must pass again.

### 6. Only after separate release authorization: publish the reviewed notes

```sh
gh release create v1.0.0 dist/assembly_fit_analyzer-1.0.0-py3-none-any.whl --repo samahara2003/assembly-fit-analyzer --verify-tag --title "Assembly Fit & Tolerance Analyzer v1.0.0" --notes-file docs/release-notes-v1.0.0.md
gh release view v1.0.0 --repo samahara2003/assembly-fit-analyzer
```

`--verify-tag` prevents the release command from creating a missing remote tag.
Review [proposed release notes](release-notes-v1.0.0.md) before this step. Confirm
the release targets the approved tag, has the intended visibility, includes the
inspected wheel and source archives, and preserves the preliminary case-study
wording. Neither release command was executed in this task.

CLI references: [run list](https://cli.github.com/manual/gh_run_list),
[run watch](https://cli.github.com/manual/gh_run_watch),
[release create](https://cli.github.com/manual/gh_release_create).
