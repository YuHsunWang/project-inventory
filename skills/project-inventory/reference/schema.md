# File formats

## inventory.json

```json
{
  "title": "專案總覽",
  "lang": "zh-TW",
  "timezone": "Asia/Taipei",          // optional IANA timezone; default UTC
  "publish": {"to": "local"},
  "projects": [
    {
      "key": "cvs",                       // short id, used in page URLs (#cvs)
      "name": "CVS Radar",
      "color": "#C4452C",
      "tag": "One sentence: what this project is for.",
      "links": [["Live site", "https://example.com"]],
      "sources": {
        "linear":   {"project_id": "confirmed-project-UUID", "project": "CVS Radar"},
        "notion":   {"url": "https://www.notion.so/...", "status_map": {"Done": "done", "In progress": "open"}},
        "github":   ["owner/repo"],                              // open PRs (gh CLI)
        "local":    [{"label": "main checkout", "path": "~/code/cvs-radar"}],
        "obsidian": [{"path": "/vault/Projects/CVS Radar"}]       // counts `- [ ]` / `- [x]` lines
      },
      "data": [
        {"label": "posts", "path": "~/code/cvs-radar/data/posts.jsonl", "kind": "jsonl", "column": "posted_at", "max_age_days": 2}
      ],
      "nodes": [
        {"id": 1, "zone": "Every hour", "title": "Crawl", "sub": "PTT board → posts.jsonl",
         "detail": "Longer text shown when the step is opened.", "paths": ["crawler.py"], "tickets": ["DEV-12"]},
        {"id": 2, "on": 1, "side": "r", "title": "Dedupe", "sub": "drops reposts", "icon": "check",
         "media": [
           {"shot": "shots/dedupe.png", "caption": "What a duplicate looks like", "phone": false},
           {"math": ["s = \\frac{n_{good}}{n_{good}+n_{bad}}"], "p": "Plain-words reading of the formula"},
           {"mock": [{"text": "in   12 posts\n"}, {"text": "out  9 posts", "emphasis": "bold"}], "cap": "A run's input and output", "real": true},
           {"link": ["Live site", "https://example.com"]}
         ]}
      ],
      "notes": [["Tests", "pytest -q (16 files)"]]   // optional static rows on the 基本資料 tab
    }
  ]
}
```

- `nodes` without `on` form the spine, top to bottom, in list order. A node with `on: <spine id>`
  hangs off that spine step, `side` `l` or `r` (default `r`). `zone` on a spine node starts a new
  labelled section. `tickets` ties ticket ids to a step (shown on the step and in its panel).
- `icon` (optional; missing or unknown values render a gear): spider, brain, box, gear, shield, clock, truck, globe, eye, flame, check, dice,
  table, hand, cards, play, coin, quiz, scale, pipe, lake, flask, chart, book, plug.
- `media` (optional): what opens when a step is clicked, in order.
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
  "cvs": {
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
{"cvs": {"2026-09-28": {"n": 14, "text": "Two or three plain sentences about that week."}}}
```

Keys are the Monday of each week. `n` is the number of items the summary was written for;
build.py lists a week in `out/summaries-needed.json` again when its count changes.

## facts/&lt;date&gt;.json (written by collect.py)

Top level: `date`, `generated_at`, `run_id`, and `gathered_run_id` (the offered MCP run,
retained even when stale so later collects cannot make it fresh again).

Per project: `sources` (source-level provenance/state), `tickets` (fresh rows only),
`stale_tickets` (previous or incomplete rows, excluded from current metrics), `repos` (branch, upstream, remote URL, ahead,
behind, dirty, last_commit, weekly commit counts for 12 weeks, recent commits for 14 days),
`weekly` (the project's commits per week across all its checkouts, each commit counted once),
`commits` (the whole history, newest 3000 per checkout, deduped), `prs`,
`obsidian` (open/done counts, `total` open tasks, `shown` items, first 50 open items with
relative `file` and 1-based `line`; fenced code is skipped, nested lists are included), `data` (newest, age_days, stale, or error),
`errors`.


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
input exits 2 with a field path, such as `projects[3].key: duplicate "cvs"`.
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
