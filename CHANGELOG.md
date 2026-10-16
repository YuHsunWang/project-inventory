# Changelog

## Unreleased — cold-start fixes (#48–#49)

- #49: name only configured ticket providers in the bilingual footer and Facts hint,
  including GitHub Issues; show a neutral no-source message and hide empty progress scaffolding.

- #48: skip Obsidian checkboxes with blank text without counting them as open or done;
  retain strict validation of collected task text.

## Unreleased — cold-start fixes (#41–#46)

- #46: collect explicitly configured GitHub Issues through paginated `gh` reads,
  excluding PRs, with per-repo failures, completed/canceled lifecycles and ticket trends.
  Setup asks and saves each project's ticket source; PR-only inventories remain unchanged.

- #45: add validated per-source Obsidian folder exclusions, shared by collection
  and scheduled change detection; ask for real task folders during Setup.

- #44: refresh CLI credentials with `vercel whoami` before reading auth.json;
  stop clearly on refresh failure and skip the CLI refresh with VERCEL_TOKEN.

- #43: scroll to the top and wait for layout before every full-page evidence capture.

- #42: preserve mobile project-menu width, truncate long titles and fail page checks
  when menu control text is clipped.

- #41: label capture provenance in captions and show successful capture timestamps,
  retaining last-good metadata on failure and omitting source URLs from HTML.

## Unreleased — project screenshots (#39)

- PR #40: omit capture source URLs and paths from both HTML outputs; preserve
  local HTML query strings and fragments when resolving file URIs.
- PR #40: discover Playwright Chromium in macOS and Windows caches. Wait for
  resource/DOM activity to settle before screenshots, with a 2s minimum and 15s limit.

- Capture existing UI URLs or local HTML files with shared Chromium discovery and
  stdlib CDP; save HOME-relative screenshots atomically and validate `media.capture`.
- Setup proposes sources and previews captured images before saving; supplied shots
  still work. No UI means no screenshot placeholder. No project servers/builds run.
- Manual and automatic refresh re-capture sources; failures warn and keep previous
  images. Automatic capture precedes fingerprints so changed images rebuild the page.

## Unreleased — cold-start fixes (#34–#37)

- #34: allow per-checkout `fetch: false`; preserve local Git facts and mark remote
  comparisons unknown. Document the default fetch and its checkout writes.
- #35: keep all-ref history by default, add `history: "head"`, and label each
  checkout's history scope on the Progress tab.
- #36: show unread/disconnected Git history with reasons on cards and the home
  list; keep collected history visible when only some checkouts fail.
- #37: explain diagram auto-refresh limits during Setup and show a manual new-step
  example. No automatic step discovery is added.

## Unreleased — unattended refresh (PR 1)

- Add opt-in cron / Windows schedules, source fingerprints with day rollover,
  a shared crash-safe refresh lock and an unattended script entry point.
- Optionally batch plain-words week summaries and cached commit/PR notes through
  Claude Haiku or Codex gpt-6-luna; default none sends nothing.
- Add a bilingual Needs Claude banner and hash-gated protected Vercel deployment.
  GitHub Pages and Artifact publication remain manual; diagram text is unchanged.
- Add offline regressions for skip/failure/lock/model/cache/schedule/publish behavior.

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
