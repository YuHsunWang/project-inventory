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
        {"id": 2, "on": 1, "side": "r", "title": "Dedupe", "sub": "drops reposts"}
      ],
      "notes": [["Tests", "pytest -q (16 files)"]]   // optional static rows on the 基本資料 tab
    }
  ]
}
```

- `nodes` without `on` form the spine, top to bottom, in list order. A node with `on: <spine id>`
  hangs off that spine step, `side` `l` or `r` (default `r`). `zone` on a spine node starts a new
  labelled section. `tickets` ties ticket ids to a step (shown on the step and in its panel).
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
  "cvs": {
    "read": ["linear"],
    "tickets": [
      {"id": "DEV-12", "title": "…", "state": "done", "url": "https://linear.app/…",
       "source": "linear", "created": "2026-09-01", "completed": "2026-09-20", "benefit": "optional plain-words note"}
    ],
    "prs": [],          // only when gh is missing: [{"number", "title", "url", "createdAt", "repo"}]
    "errors": []        // "linear: <message>" / "notion: <message>"
  }
}
```

`state` is one of `done`, `wait` (finished, waiting for the user's review/merge), `open`, `dead`
(canceled). Notion rows use the page URL as `url` and a short id (e.g. the row's ID property or
the first 8 chars of the page id) as `id`.

## facts/&lt;date&gt;.json (written by collect.py)

Per project: `tickets` (copied from gathered), `repos` (branch, upstream, ahead, behind, dirty,
last_commit, weekly commit counts for 12 weeks, recent commits for 14 days), `prs`,
`obsidian` (open/done counts, first 50 open items), `data` (newest, age_days, stale, or error),
`errors`.
