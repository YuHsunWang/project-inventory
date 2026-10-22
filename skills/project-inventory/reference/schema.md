# File formats

## inventory.json

```json
{
  "title": "專案總覽",
  "lang": "zh-TW",
  "timezone": "Asia/Taipei",          // optional IANA timezone; default UTC
  "publish": {"to": "local"},
  "auto_refresh": {"model": "none"}, // optional; no schedule unless explicitly installed
  "writing_skill": "sepia",          // optional installed skill; absent = no polishing
  "projects": [
    {
      "key": "app",                       // short id, used in page URLs (#app)
      "name": "My App",
      "color": "#C4452C",
      "tag": "One sentence: what this project is for.",
      "links": [["Live site", "https://example.com"]],
      "sources": {
        "linear":   {"project_id": "confirmed-project-UUID", "project": "My App"},
        "notion":   {"url": "https://www.notion.so/...", "status_map": {"Done": "done", "In progress": "open"}},
        "github_issues": ["owner/repo"],                        // explicitly opted-in tickets (gh CLI)
        "github":   ["owner/repo"],                              // open PRs (gh CLI)
        "local":    [{"label": "main checkout", "path": "~/code/my-app"}],
        "obsidian": [{"path": "/vault/Projects/My App"}]          // unique tasks from `- [ ]` / `- [x]` lines
      },
      "data": [
        {"label": "orders", "path": "~/code/my-app/data/orders.jsonl", "kind": "jsonl", "column": "created_at", "max_age_days": 2}
      ],
      "nodes": [
        {"id": 1, "zone": "Every hour", "title": "Fetch", "sub": "API → orders.jsonl",
         "detail": "Longer text shown when the step is opened.", "paths": ["fetch.py"], "tickets": ["DEV-12"]},
        {"id": 2, "on": 1, "side": "r", "title": "Dedupe", "sub": "drops repeated orders", "icon": "check",
         "media": [
           {"shot": "shots/dedupe.png", "caption": "What a duplicate order looks like", "phone": false},
           {"math": ["s = \\frac{n_{good}}{n_{good}+n_{bad}}"], "p": "Plain-words reading of the formula"},
           {"mock": [{"text": "in   12 orders\n"}, {"text": "out  9 orders", "emphasis": "bold"}], "cap": "A run's input and output", "real": true},
           {"link": ["Live site", "https://example.com"]}
         ]}
      ],
      "notes": [["Tests", "pytest -q (16 files)"]]   // optional static rows on the 基本資料 tab
    }
  ]
}
```

- `writing_skill` (optional): name of an installed writing/rewriting skill, such as
  `sepia` or `sepia:sepia`. A nonempty string matching `[A-Za-z0-9_:-]+`: ASCII letters,
  digits, hyphens, underscores and colons only; no spaces, paths or commands. Omit it to
  disable polishing (default); existing inventories need no changes. In conversation runs,
  the agent passes weekly summary and diagram step drafts through it once, verifies facts,
  numbers, dates, names, links and JSON structure are identical, and discards the pass if any
  changed. An unavailable skill is reported once and skipped; skills are never installed
  automatically. Unattended `auto_refresh.py` / `step_refresh.py` CLI runs do not use it.
- `nodes` without `on` form the spine, top to bottom, in list order. A node with `on: <spine id>`
  hangs off that spine step, `side` `l` or `r` (default `r`). `zone` on a spine node starts a new
  labelled section. `tickets` ties ticket ids to a step (shown on the step and in its panel).
- `draft` (optional boolean on a node; absent/false = reviewed): Quick start sets `true`
  on every generated diagram step. The page labels it “AI draft” / “AI 草稿” using
  `.ai-updated`. Remove the field only after the user reviews that node in full Setup
  step 5 or explicitly confirms it later. It is independent of `auto_updated`; existing
  inventories need no migration.
- `icon` (optional; missing or unknown values render a gear): spider, brain, box, gear, shield, clock, truck, globe, eye, flame, check, dice,
  table, hand, cards, play, coin, quiz, scale, pipe, lake, flask, chart, book, plug.
- `media` (optional): what opens when a step is clicked, in order.
  - `capture`: a nonempty absolute HTTP/HTTPS URL (no credentials), or a local `.html`/`.htm`
    path (absolute, `~/…`, relative to HOME, or a local `file://` URI). Query strings and
    fragments are preserved when opening local files. This is source-only metadata;
    `build.py` omits it from both HTML outputs. Only configure this
    for a project UI that already exists; never start a server or run project/build code.
    `python3 SCRIPTS/capture_shots.py HOME` opens it in headless Chromium at 1280×800,
    saves `HOME/shots/<project>-<step>.png`, and sets `shot` to that HOME-relative path.
    After loading assets, capture waits at least 2 seconds, then for resource count and
    DOM size to stay unchanged for 1 second. It captures after 15 seconds even if still busy.
    Further captures on the same step use `-media2`, `-media3`, etc. in media order. Images are replaced
    atomically; identical PNG bytes are left untouched. Auto-refresh captures before its
    fingerprint/unchanged check, and manual Refresh does so before collect/build.
    A failed capture prints `WARN`, retains the previous image and `shot`, and never fails
    the run; on first failure no `shot` is added. No `capture` means existing `shot` files
    remain user-managed. Projects without a UI omit both fields: no screenshot placeholder
    or "no screenshot" text is rendered. Chromium is optional unless capturing/checking.
  - `captured_at`: UTC ISO timestamp written after each successful capture and shown in the
    caption. Failures keep the previous timestamp. Capture times alone do not trigger an
    automatic rebuild when the pixels are unchanged; the page retains its last rendered time.
    Captions must say whether the image shows the live site or a local build output.
    The capture source URL/path is omitted from both HTML outputs.
  - `shot`: a PNG, WebP or JPEG file (maximum 8 MiB and 16 million pixels) (absolute, `~/…`, or relative to HOME). `build.py` embeds it in the page;
    invalid or missing files show as missing and print a `WARN`; other formats (SVG, GIF, …) must be exported first.
    Only paths explicitly listed in `shot` are read (including approved external absolute paths);
    each embedded file is listed as `ASSET` with its resolved path, size and MIME for pre-publish review. `phone: true` keeps a tall phone shot narrow.
  - `math`: TeX strings; the page loads MathJax (cdnjs) only when some step has one. `p` explains it.
  - `mock`: text shown in a monospace box; columns line up when 2+ lines have double spaces. It is
    plain text (HTML is displayed literally). For emphasis, use an array of `{text, emphasis}`
    spans; `emphasis` is `bold`, `dim`, or `bad`. Text is always escaped.
    `real: true` labels it real output instead of a sketch.
  - `link`: `[text, url]`; only absolute HTTP/HTTPS URLs become links.
  - `src` is build output: only base64 PNG/JPEG/GIF/WebP data URIs are rendered; SVG is forbidden.
- `sources.linear.project_id` is the confirmed Linear project UUID; `project` is its display
  name and may change without changing identity. Setup and MCP reads must select that UUID.
  Legacy `{ "project": "name" }` configurations still work when exactly one accessible project
  matches, including archived projects. Multiple matches require choosing and saving a UUID;
  a renamed or inaccessible legacy project reports a migration/permission error. IDs are unique
  across teams, so no team filter is needed once the UUID is confirmed.
- `sources.github_issues`: optional list of `owner/repo` strings explicitly confirmed
  during full Setup as ticket repositories, or enabled by Quick start project selection
  only when authenticated discovery confirms Issues are enabled. Full Setup asks
  **Linear / Notion / GitHub Issues / none** per project, saves the corresponding source configuration, and saves no ticket-source
  keys for none. `sources.github` continues to mean PRs only; that key alone never enables Issues.
  Existing inventory files require no migration. The Issues connection excludes PRs.
  collect.py uses logged-in `gh api graphql`, follows every page of open and closed issues,
  and records each repo separately under `github_issues:owner/repo` in snapshot `sources`.
  Tickets use that same `source` value, with `id` and `source_id` = `owner/repo#number`
  so issue numbers cannot collide across repos. OPEN → `open`; CLOSED → `done`, except
  `stateReason: NOT_PLANNED` → `dead`. A missing/null reason on a closed issue means done.
  `createdAt` maps to `created`; `closedAt` to `completed` or `canceled`; `updatedAt` to
  `updated`. Dates feed the existing ticket trend/history. Full reopen event histories
  are not fetched. Any failed page marks that repo failed/incomplete and publishes none
  of its partial ticket list. Other successful repos remain visible; aggregate trends
  are withheld until all configured ticket sources are current and complete.
  Missing `gh`, login or repo permissions are visible errors, never a successful empty list.
  Scheduled refresh probes opted-in Issues and retries failures.
- `sources.obsidian[]`: `path` is the vault folder to scan recursively for `*.md`.
  Optional `exclude` lists folder paths relative to that configured vault path, using `/`
  (for example `{"path":"/vault", "exclude":["templates","marp",".superpowers"]}`).
  An excluded folder and all descendants are skipped, but similarly prefixed names are not.
  `.obsidian` and `.trash` are always excluded. Without `exclude`, all non-internal folders are scanned.
  Task lines use `-`, `*`, `+` or numbered lists with `[ ]` / `[x]` / `[X]`; fenced code
  blocks and checkboxes with blank text are ignored. Within each source, identical full task
  text after `strip()` counts once, using exact matching only. Any checked copy makes the
  task done; otherwise it is open. Listed `file` / `line` point to the newest file holding
  an open copy, using the existing lexicographic path order, not parsed dates or modification
  times. Counts include all unique tasks; only the first 50 open tasks are listed.
  Existing configurations need no new key.
  Choose task folders during Setup; template/article checkboxes otherwise count too.
  Scheduled change detection uses the same exclusions.
- `sources.local[]` supports two optional Git settings. Existing entries need no changes:
  - `"fetch": true` (default): collect runs `git fetch -q origin` when origin exists.
    This writes remote refs and `.git/FETCH_HEAD` in that checkout. `"fetch": false`
    skips fetch and still reads HEAD, branch, dirty files and history. Ahead/behind and
    unpushed comparisons against the remote are unknown (`null`), even if cached refs exist;
    the page labels that uncertainty. The previous successful fetch time is retained.
  - `"history": "all"` (default): `git log --all`, across every local ref, including other
    branches and cached remote refs. `"history": "head"`: commits reachable from HEAD only
    (including merged ancestry). Both recent activity and weekly/history counts use this
    scope; the page labels it per checkout as All branches / Current branch (HEAD).
    Mixed scopes across checkouts are allowed; project aggregates deduplicate full hashes.
  Example: `{"label": "read-only checkout", "path": "~/code/app", "fetch": false, "history": "head"}`.
- Every `sources` key is optional. A project with none of them still shows its diagram.
- `data[].kind` and what `column` means:

| kind | column | extra |
|---|---|---|
| `csv` | header name | — |
| `jsonl` | field of each line | — |
| `json` | dotted path to one value, e.g. `meta.generated_at` | — |
| `sqlite` | column | `"table"` |
| `parquet` | column; `path` may be a folder (reads `**/*.parquet`, hive partitions) | needs `pip install duckdb` |
| `duckdb` | column | `"table"`, needs duckdb |

  Values must be ISO calendar dates or timestamps. `timezone` is an IANA name
  (default `UTC`, e.g. `Asia/Taipei`). Offset timestamps (`Z`, `+08:00`) are
  converted to that timezone before comparison; naive timestamps use that zone.
  Pure dates keep their calendar day and compare as midnight in that zone.
  Newest means the latest normalized instant, including for database columns
  containing mixed formats; offsets are retained in output. Null/empty rows are
  ignored; an all-empty column or any nonempty invalid date reports an error.
  `age_days` uses calendar days in the inventory timezone. Future dates beyond
  today have zero tolerance and report an error (unknown freshness), never a
  negative fresh age. Times later within today remain age 0.
  `max_age_days` defaults to 1: stale exactly when `age_days > max_age_days`;
  equality remains fresh. Ticket timestamps are kept intact during collection
  and use the same timezone for chart, recent-completion and history dates.

## gathered/&lt;date&gt;.json (written by Claude each run)

```json
{
  "_run": {"run_id": "unique UUID for this gather"},
  "app": {
    "sources": {"linear": {"run_id": "same UUID", "attempted_at": "ISO timestamp with offset",
      "fetched_at": "ISO timestamp with offset", "status": "ok", "complete": true, "error": null}},
    "read": ["linear"],
    "tickets": [
      {"id": "DEV-12", "title": "…", "state": "done", "url": "https://linear.app/…",
       "source": "linear", "source_id": "full-provider-issue-UUID", "created": "2026-09-01", "completed": "2026-09-20", "canceled": null, "reopened": null,
       "benefit": "optional plain-words note"}
    ],
    "prs": [],          // only when gh is missing: [{"number", "title", "url", "createdAt", "repo"}]
    "errors": []        // "linear: <message>" / "notion: <message>"
  }
}
```

Each source uses `run_id / attempted_at / fetched_at / status / complete / error`.
Use `linear`, `notion`, and `github:<owner/repo>` as source keys (PRs are tracked per repo).
Create a new `_run.run_id` for each gather and copy it into every source record. A successful
read, including zero rows, is `ok` and `complete: true`; failures are `failed` or `partial`,
with an error and the last successful `fetched_at` (null if never read).
Collect consumes a gather run once; a second collect marks reused results stale. Legacy `read`
without metadata is stale, never fresh. Linear with an API key is re-read on every collect.
Only fresh tickets/PRs feed counts and trends; old tickets remain in `stale_tickets`.

`state` is one of `done`, `wait` (finished, waiting for the user's review/merge), `open`, `dead`
(canceled). Notion rows use the page URL as `url`, the full page UUID as `source_id`, and a short
display label as `id`. Never use a shortened Notion ID as the unique identity.

## Notion connector playbook

This is a connector contract, not a script-side Notion client. `collect.py` consumes normalized
rows; it does not apply `status_map`. Offline mock validation is in `tests/test_notion_contract.py`.
A real authorized workspace is still required to verify connector/API behavior.

1. Confirm `sources.notion.url` and the full database or page UUID. For database queries,
   retrieve the database and resolve its **data source** ID; database ID and data source ID
   are different identities. If several data sources exist, have the user select one.
   Save `database_id` and `data_source_id` in the source metadata. Legacy connectors that
   query database IDs must record that identity and API capability explicitly; never pass
   a database ID to a data-source query. Page/block mode records `page_id` instead.
2. Query the selected data source using its connector operation. For every result page,
   append `results`, pass `next_cursor` back as `start_cursor`, and continue until
   `has_more: false`. Missing/repeated cursors, permissions errors or interrupted pages
   mean partial/failed with `complete: false`, an error and the last successful fetch time.
   Zero rows after the final page is a successful complete read.
3. In page mode, list child blocks for the full page UUID. Paginate each child list by the
   same rule, then recursively visit **every** block with `has_children`, including toggles,
   list items and nested to-dos. Emit only `to_do` blocks; `checked: true` → `done`, false →
   `open`. Use the full block UUID as `source_id` and retain the full containing `page_id`;
   sibling tasks must not collapse to their parent page. Never emit code-block examples.
4. For database pages preserve `raw_status` (status/select property name) and use the exact
   saved `status_map` → `wait | open | done | dead`. Unknown or absent statuses retain
   `raw_status`, use `open` as a provisional state and report the source partial with an
   explicit error; these rows do not feed fresh metrics. Do not guess from translated labels.
   Use the full page UUID as `source_id`, its URL as `url`, and a short label only as `id`.
5. Preserve provider `created_time` as `created`. Map `completed`, `canceled`, `reopened`
   only from confirmed lifecycle properties/events. Never infer completion from
   `last_edited_time`, current status or checked state. Unavailable dates are null.
   Each row has `date_availability` mapping these four fields to booleans; the source has
   `date_coverage` mapping each field to `{known, total}`. Coverage counts date availability,
   not reliable history: build.py additionally excludes inconsistent/reopened lifecycles.
6. Gather output follows the source run/provenance contract above, plus source identity and
   `date_coverage`; normalized tickets include `raw_status` and `date_availability`.
   `status: ok, complete: true` is allowed only after all query/child pages and status mappings
   succeed. Record errors with `notion:` and include `notion` in `read` only after a read.

## summaries.json (written by Claude, kept across runs)

```json
{"app": {"2026-09-28": {"n": 14, "text": "Two or three plain sentences about that week."}}}
```

Keys are the Monday of each week. `n` is the number of items the summary was written for;
build.py lists a week in `out/summaries-needed.json` again when its count changes.

## facts/&lt;date&gt;.json (written by collect.py)

Top level: `date`, `generated_at`, `run_id`, and `gathered_run_id` (the offered MCP run,
retained even when stale so later collects cannot make it fresh again).

Per project: `sources` (source-level provenance/state), `tickets` (fresh rows only),
`stale_tickets` (previous or incomplete rows, excluded from current metrics), `repos` (head SHA, history scope, fetch_enabled, fetch_performed, branch, upstream, remote URL, ahead,
behind, dirty, last_commit, weekly commit counts for 12 weeks, recent commits for 14 days),
`weekly` (the project's commits per week across all its checkouts, each commit counted once),
`commits` (history in each checkout's selected scope, newest 3000 per checkout, deduped), `prs`,
`obsidian` (open/done counts, `total` open tasks, `shown` items, first 50 open items with
relative `file` and 1-based `line`; fenced code is skipped, nested lists are included), `data` (newest, age_days, stale, or error),
`errors`.


`fetch_performed` records whether a fetch was attempted this run (errors stay in
`fetch_error`); it is false with `fetch: false` or no origin. Git source read failures
are recorded as `failed` under `sources["git:<path>"]`. Missing/failed Git history is
labelled as not collected on project cards and the home list, including the source error;
no connected Git source is a separate not-connected reason. A failed remote fetch alone
still leaves local history available. With multiple checkouts, missing ones are labelled
while collected history remains visible.

`build.py` shows tickets as empty, not connected, failed, partial, stale, or ready.
A complete read must belong to this run and be at most 24 hours old to feed current metrics.
Legacy snapshots lacking source provenance are shown as stale, with their rows retained.
`fetched_at` is the last successful source read; it is carried across daily snapshots.

`refresh.json` records `run_id`, `attempted_at`, `status` (`running`, `ok`, `partial`, `fatal`),
`snapshot` (the exact absolute snapshot path), and `error`. `collect.py HOME --refresh` runs
collection and build together; fatal failures stop rebuilding and mark last-good output.

## Machine validation

`collect.py` validates inventory and the consumed gathered file before reading sources;
`build.py` validates inventory and snapshot ticket/PR rows before rendering. Invalid
input exits 2 with a field path, such as `projects[3].key: duplicate "app"`.
The shared `validation.py` uses only Python's standard library.

Project keys are unique and contain only ASCII letters, digits, `_` and `-`.
DOM IDs `home`, `projects`, `brand`, `menubtn`, `menulabel`, `stamp`, `menu`,
`menuitems`, `foot`, and prefixes `d-`/`t-` are reserved. Node IDs are unique
integers within a project; `on` must reference a spine node (no self/branch references).
States use the enum above. Supplied dates must be ISO calendar dates or timestamps;
null/empty ticket lifecycle dates mean unknown, not zero. URLs must be absolute
HTTP/HTTPS URLs. Data kinds use the table above and `max_age_days` is nonnegative.

Tickets dedupe by `(source, source_id)` and PRs by `(repo, number)`, keeping the
first valid row. Legacy Linear identifiers and full Notion page URLs provide stable
fallback identities; a short Notion display ID alone is rejected. Missing lifecycle
dates are allowed so the chart can report incomplete history.

## Ticket history coverage

The 90-day curve is **estimated from available dates**, not an exact event history.
Every ticket needs `created`; `done` also needs `completed`, and `dead` needs
`canceled`. Missing dates, future dates, reversed lifecycle dates, or conflicting
completion/cancellation dates go into `unknown` and a coverage reason count.
`reopened` is an optional ISO date/timestamp indicating a reopen. An open/review
ticket retaining a completed/canceled date also signals a reopen; either case
requires unknown history because the current state cannot reconstruct transitions.
Adapters should supply `reopened` when the provider exposes it; a reopen that clears
all old dates is undetectable without that signal. No event-sequence system is assumed.

Dated cancellations have their own cumulative series. Unknown rows are excluded
from done/open/canceled estimates and shown as a constant current unknown pool
across the window; this does not claim they existed on every historical day.
The chart, tooltip and number table show all four series, alongside known/total
coverage and missing-date/reopen counts. On the snapshot day their sum equals
the ticket total. Current-state counters still include all tickets.

## Unattended refresh (optional, backward compatible)

`auto_refresh.model`: `none` (default, sends nothing), `claude`, or `codex`.
`auto_refresh.schedule`: absent/null by default; configuring it does not install anything.
After explicit Setup consent, save for example:

```json
{"auto_refresh": {"model": "none", "schedule": {"every_hours": 2, "start_hour": 8, "end_hour": 22}}}
```

Hours are inclusive, 0–23, in the scheduler computer's local time; start <= end,
`every_hours` is 1–24. `schedule.py print/install/remove HOME` reads these defaults;
`--every`, `--start`, `--end` override them for that command. Install replaces this
home's marked entry/task; remove preserves unrelated jobs. `--crontab-file FILE`
is an offline test target and never invokes real crontab. PATH is captured on install.
No schedule is installed merely by collecting/building or opening the skill.

For unattended Vercel use `{"publish":{"to":"vercel","project":"chosen-project","team":"optional-team"}}`.
Local/absent publish settings never deploy. GitHub Pages never publishes automatically;
`{"publish":{"to":"artifact"}}` adds a manual publish reminder. An unknown existing
Vercel project is still refused by publish_vercel.py; no automatic `--reuse`.

State files (all under HOME, not the project checkout):

- `state/fingerprints.json`: `{fingerprints: {day, sources}, cacheable}` after a successful
  build (and any configured deploy). Each source has independent git refs/counts, PR
  numbers/updatedAt, script-side Linear data digest, or `[file_count,total_bytes,newest_mtime_ns]`.
  Day uses inventory timezone. Settings/gathered files/summaries/notes/step state/history are also fingerprinted.
  A failed probe or failed script source prevents unchanged skipping. MCP-only gaps may
  be cached but remain visible. Values/dates are always collected from the data itself.
- `state/steps.json`: `{ "<project key>": {"last_session_date": "YYYY-MM-DD",
  "steps": {"<node id>": {"<resolved checkout path>": {"checked_commit": "<SHA>"}}}} }`.
  First sight only records HEAD. Later commits touching node `paths` trigger one project
  rewrite session per calendar day (inventory timezone). Invalid/failed/skipped steps
  retain their checked commit; an explicit empty per-step object accepts no change.
  Relative paths resolve against each checkout; absolute/`~` paths outside it are ignored.
- `step_history.json`: append-only history list (revert marks entries `reverted: true`).
  Each entry has `project`, `step_id`, `date`, `old`, `new` text-field objects and `commit`
  (checkout path to SHA). Only `title`, `sub`, `zone` can change. A changed node receives
  `auto_updated: "YYYY-MM-DD"`, validated as a calendar date and rendered as a localized
  AI-updated label. `auto_refresh.py HOME --revert-step PROJECT_KEY STEP_ID` restores the
  latest unreverted text only if all current text equals `new`, removes `auto_updated`,
  and retains other node settings. Run refresh afterwards to rebuild the page.
- `state/notes.json`: `{ "<full commit SHA or PR URL>": "one plain sentence" }`.
  Existing keys are never sent again for individual notes; relevant listed work may still
  occur in a missing week's summary input. Notes appear in existing history note rows.
- `summaries.json`: unchanged format. Optional CLI summaries preserve build.py's exact `n`;
  invalid/failed results leave the week in `out/summaries-needed.json` and the banner.
- `state/deployed.json`: `{project,team,hash}`; SHA-256 of the exact last successfully
  deployed index.html. Failed deployment/protection verification never advances it.
- `state/refresh.lock`: shared OS lock, not an age-based sentinel. A dead process releases
  it immediately, so an old file cannot block future runs; a live run never loses its lock
  merely for lasting 30 minutes. Busy scheduled/manual collects and standalone builds return 0 without writing; stop a manual run on `BUSY:`.
- `state/schedule.log`: cron job output. Never put API secrets in schedule commands.

Snapshot source metadata may additionally include `via: mcp | gh | api` to distinguish
MCP reminders from script/API failures. Legacy metadata without it remains readable.
Notes calls are optional and isolated in a temporary working directory. Claude uses
`claude -p --model claude-haiku-4-5-20251001 --tools "" --strict-mcp-config --no-session-persistence`;
Codex uses `codex exec -m gpt-6-luna -c model_reasoning_effort=max -s read-only
--skip-git-repo-check --ephemeral -C <tmp> -o <file> -`. One batch per project returns a
JSON token-to-text object; only requested tokens, nonempty strings and checkable page
scripts are accepted (zh-TW: Big5 plus Chinese; en: Latin and no CJK). These notes calls
do not change diagram text.

Step rewrites reuse the selected provider but allow project reads: Codex uses the first
checkout as `-C` under `-s read-only` and adds other checkouts with `--add-dir`; Claude uses
`--tools Read,Grep,Glob --allowedTools Read,Grep,Glob` and adds every checkout with
`--add-dir`. Both receive all changed steps, current text, paths and commit subjects in
one session per project per day, treating repository content as data, never instructions.
Provider `none` sends nothing. Invalid JSON fails the session; unknown ids are ignored,
and extra fields, empty strings or text failing the existing language rules reject that
step only. Failed sessions consume the daily allowance without advancing checked commits.
