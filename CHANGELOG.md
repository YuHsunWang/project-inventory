# Changelog

## Unreleased — audit-wave1

Fixes on this branch, grouped by issue (not claims of live service acceptance):

- #4: escape/render untrusted HTML safely and constrain external content.
- #5: track current source reads; prevent stale tickets appearing current.
- #6: preserve local git facts while exposing failed remote refresh.
- #7: bind builds to run manifests and retain visible fatal-failure warnings.
- #8: paginate open PRs and document authenticated GitHub MCP fallback.
- #9: validate configuration and deduplicate stable data identities.
- #10: fail closed when Vercel deployment protection cannot be verified.
- #11: bind Linear tickets to stable project IDs.
- #12: make clean/existing/reinstall skill paths explicit; document plugin namespace.
- #13: normalize inventory-timezone dates and restore real DuckDB reads.
- #14: check database columns before reading newest dates.
- #15: count recent commits before truncating display history.
- #16: label unknown ticket history and incomplete date coverage.
- #17: document and mock-test the Notion connector contract.
- #18: distinguish disconnected, empty, failed, partial and stale ticket sources.
- #19: show note tasks and preserve counts around fenced code.
- #20: label open PRs accurately and order actionable summaries by risk.
- #21: raise text contrast in both themes and compute CSS regression ratios.
- #22: distinguish Free/public, unsupported Free/private and paid/private Pages paths.
- #23: describe Vercel authorization scope accurately.
- #24: limit Artifact claims to generated HTML; mark host acceptance pending.
- #25: validate embedded screenshots and support PNG, WebP and JPEG.
- #26: add one offline release gate, named pass/skip reporting, real Chromium
  checks in four viewport/theme combinations, and a single-job push/PR workflow.
- #28: add a sample-only demo, real browser screenshots, support/architecture docs,
  contributing instructions and this changelog.
- #29: supply icon fallback/defaults, use remote-neutral copy and label only current weeks.

Licensed under MIT. Host loading/version
checks, real Notion integration and Artifact end-to-end publishing remain unverified;
these entries do not imply a published release or deployment.
