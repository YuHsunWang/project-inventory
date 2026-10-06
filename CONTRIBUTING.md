# Contributing

Read the current README and schema before changing collection or rendering. Keep
README.md and 說明書.md aligned, preserve existing run/source contracts, and use
small commits tied to the relevant issue. Do not include personal inventory data,
credentials or screenshots from a real home in changes or reports.

## Local verification

```sh
python3 tests/release_gate.py
```

The gate creates repo-local temporary files in `.tmp/` and runs the named unit and
contract cases, Node.js renderer assertions, clean-install fixtures, a zero-service
demo with a fixture-only local Git commit for the Progress tab, browser failure regressions, and demo `check_page` at 390/1280 px in light/dark.
The last line reports passed/skipped counts and failed stages; any failure exits
non-zero. Optional DuckDB tests print `SKIPPED` with a reason when unavailable.
CI installs DuckDB so `test_real_duckdb` runs there. Python code uses stdlib only.
Node.js and headless Chromium are required; missing browser fails the gate.
Set `CHROMIUM_BIN` to its executable, or use the cached Chromium from
`python3 -m playwright install --with-deps chromium` after installing the optional
Playwright test tool. CI uses that installer; `check_page` does not import Playwright.

Run just the existing suite with `TMPDIR="$PWD/.tmp" python3 tests/test_scripts.py`
after `mkdir -p .tmp`. Browser checks: `python3 skills/project-inventory/scripts/check_page.py HOME`
(optionally `--shots DIR`); expected final line: `OK`. The checker waits for
images, fonts and MathJax, checks visible panels and overflow, uses mouse hit testing,
and exercises Enter/Escape keyboard navigation. Console/browser errors fail it.

CI verifies offline fixtures and sample rendering. Real authenticated Linear,
GitHub, Notion and Vercel integrations, host skill loading, Artifact host import,
external font CDN availability, and public deployment are **UNVERIFIED**: they require separately authorized manual
acceptance with the actual accounts/hosts. Browser fixtures remove Google Fonts links and check the local fallback fonts.
Mock publisher checks do not prove a
live deployment or access control. No CI step contacts or publishes to those services.

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

Contributions are accepted under the [MIT License](LICENSE).
