# Contributing

Read the current README and schema before changing collection or rendering. Keep
README.md and 說明書.md aligned, preserve existing run/source contracts, and use
small commits tied to the relevant issue. Do not include personal inventory data,
credentials or screenshots from a real home in changes or reports.

## Local verification

```sh
mkdir -p .tmp
export TMPDIR="$PWD/.tmp"
python3 tests/test_scripts.py
```

Expected final line: `OK`. Tests use Python stdlib fixtures and Node.js to execute
renderer assertions; they do not call external services. Some optional DuckDB cases
need the existing DuckDB package; report any skips explicitly. No new runtime dependency
is required by the docs/UI fixes.

Try the sample-only demo using the README commands. For browser checks, install the
optional Playwright package and Chromium, then run `check_page.py HOME`. Its final
line should be `OK`; capture desktop/mobile screenshots with `--shots DIR`.
Actual host skill loading, Notion workspace integration, Artifact import/publication,
and public deployment need separate authorized manual acceptance.

For changes touching real collection, copy `~/.project-inventory` to a new repo-local
home, then run BOTH collect.py and build.py before and after. Compare per-project
errors, source states and data reads, including DuckDB/SQLite/CSV/notes, and run the
browser check. Never write tests to the original inventory home.

## Issue report template

- Expected behavior and actual behavior.
- Repository commit, OS, Python/browser/tool versions.
- Exact command and exit status; final output lines (remove secrets and personal paths).
- Small sample-only inventory/input that reproduces the failure.
- For UI reports: language, theme, viewport and genuine browser screenshot.
- For source reports: source status/completeness and before/after error counts.

A LICENSE is an open owner decision; this file does not grant a license. CI is
planned separately in wave 4 (#26); no workflow is included here.
