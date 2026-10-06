# File formats

## inventory.json

```json
{
  "title": "專案總覽",
  "lang": "zh-TW",
  "publish": {"to": "local"},
  "projects": [
    {
      "key": "cvs",                       // short id, used in page URLs (#cvs)
      "name": "CVS Radar",
      "color": "#C4452C",
      "tag": "One sentence: what this project is for.",
      "links": [["Live site", "https://example.com"]],
      "sources": {
        "linear":   {"project": "CVS Radar"},
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
- `icon` (optional): spider, brain, box, gear, shield, clock, truck, globe, eye, flame, check, dice,
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

  The newest value must start with an ISO date (`2026-10-02…`). `max_age_days` default 1.

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
       "source": "linear", "created": "2026-09-01", "completed": "2026-09-20", "canceled": null,
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
(canceled). Notion rows use the page URL as `url` and a short id (e.g. the row's ID property or
the first 8 chars of the page id) as `id`.

## summaries.json (written by Claude, kept across runs)

```json
{"cvs": {"2026-09-28": {"n": 14, "text": "Two or three plain sentences about that week."}}}
```

Keys are the Monday of each week. `n` is the number of items the summary was written for;
build.py lists a week in `out/summaries-needed.json` again when its count changes.

## facts/&lt;date&gt;.json (written by collect.py)

Per project: `tickets` (copied from gathered), `repos` (branch, upstream, remote URL, ahead,
behind, dirty, last_commit, weekly commit counts for 12 weeks, recent commits for 14 days),
`weekly` (the project's commits per week across all its checkouts, each commit counted once),
`commits` (the whole history, newest 3000 per checkout, deduped), `prs`,
`obsidian` (open/done counts, first 50 open items), `data` (newest, age_days, stale, or error),
`errors`.
