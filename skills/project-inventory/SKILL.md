---
name: project-inventory
description: >
  Take stock of all the user's projects and build one dashboard page: per project a
  "how it works" diagram, tickets (Linear / Notion), GitHub PRs, git state, Obsidian
  note tasks, data freshness, recent activity and trends, plus a home list of what
  waits on the user. Use when the user says "inventory my projects", "project status",
  "盤點專案", "專案總覽", "/project-inventory", or asks which data is out of date
  across projects. First run sets up inventory.json with the user; later runs just refresh.
---

# project-inventory

All state lives in one folder, `HOME` = `~/.project-inventory` unless the user names another:

```
HOME/inventory.json          projects, sources, data checks, diagram   (you write it with the user)
HOME/gathered/<date>.json    tickets/PRs you fetched through MCP tools  (you write it each run)
HOME/facts/<date>.json       one snapshot per run                       (collect.py)
HOME/out/index.html          the page                                   (build.py)
```

`SCRIPTS` = the `scripts/` folder next to this file. Schemas for every file: `reference/schema.md`.
Talk to the user in their language and write page text (names, tags, diagram) in it too; set
`"lang"` in inventory.json (`zh-TW` and `en` have page labels; anything else falls back to `en`).

## Which run is this?

- `HOME/inventory.json` missing → **Setup** (below), then **Refresh**.
- Present → **Refresh**. If the user adds a project or a data source, edit inventory.json first.

## Setup (first run) — confirm each step with the user, one question at a time

1. **Projects.** Ask which projects to include. Offer what you can see: Linear projects
   (`list_projects` if a Linear MCP is connected), Notion databases/pages the user names,
   GitHub repos (`gh repo list` or GitHub MCP), local git checkouts under folders they name,
   Obsidian vault folders. Never include a project the user did not confirm.
2. **Sources per project.** Fill `sources` (see schema): `linear`, `notion`, `github`, `local`,
   `obsidian`. Check each one actually answers now (one MCP call / one `git -C <path> status`).
   A source with no connector: tell the user which connector to add, leave it out for now.
3. **Data to watch.** Look for data the project produces (data/, *.csv, *.parquet, *.sqlite,
   *.jsonl, generated JSON). Show the candidates; for each one the user keeps, find the
   **date column inside the data** (never use file modification times — they lie after copies
   and rebuilds) and ask how many days old counts as stale. Run `collect.py` once to prove each
   check reads.
4. **Diagram.** Read each project's README and entry points, draft `nodes` (5–10 steps: the
   real order of work as the spine, inputs/alternatives on the left, checks/helpers on the
   right), with `paths` to the code for each step. Show the draft as a short list; fix what the
   user corrects. Facts in `detail` must come from code or docs, not guesses.
5. Save `HOME/inventory.json`. Pick distinct `color`s that read in light and dark mode.

## Refresh (every run)

1. **Gather through MCP** what scripts cannot reach, into `HOME/gathered/<today>.json`:
   - Linear: issues of the project (`list_issues` with the project). Map status type:
     completed → `done`, canceled → `dead`, started with an open PR or "In Review" → `wait`,
     everything else → `open`.
   - Notion: query the database (or read the page's to-do blocks). Map its status property the
     same way; say which values you mapped how the first time and save that in inventory.json
     (`sources.notion.status_map`).
   - GitHub PRs only if `gh` is not installed: use the GitHub MCP, put them under `prs`.
   - List every source you read in `read`. If a source fails, write the error into `errors`
     (start the text with the source name) — never drop it silently.
2. `python3 SCRIPTS/collect.py HOME` — git (fetches origin first), PRs via `gh`, Obsidian tasks,
   data checks. Exit 1 = some source failed; the page shows it. Read the printed ERROR lines.
3. `python3 SCRIPTS/build.py HOME` → `HOME/out/index.html`.
4. **Check the page** before handing it over: open it in a headless browser if one is available
   (Playwright: every project tab at 390 px and 1280 px, click every diagram step, no JS errors,
   no sideways scroll). No browser → say UNVERIFIED for the layout.
5. **Report** in chat: first line = what failed, if anything. Then what waits on the user (the
   home list), which data is stale, and the page path / URL.
6. **Publish** only where the user chooses (ask once, remember it in inventory.json `publish`).

## Publish options (ask; default = local file)

| Option | How | Who can see it |
|---|---|---|
| Local file (default) | `HOME/out/index.html`, open in a browser | only this computer |
| claude.ai Artifact | Artifact tool, publish `HOME/out/index.html` (same file path every run keeps one URL) | private to the user |
| Vercel | `python3 SCRIPTS/publish_vercel.py HOME <project-name>` — creates the project, locks it (Vercel Authentication, all deployments) BEFORE deploying, then checks an anonymous visitor is turned away | only the user's logged-in Vercel account |
| GitHub Pages | see below | **everyone on the internet** |

**GitHub Pages is public**, also from a private repo on a free plan. The page lists project
names, tickets, branches, file paths and data locations. Before the first Pages publish, say
this in one plain sentence and get an explicit yes. Then: a repo the user names (create it with
`gh repo create <name> --private` if needed), copy `out/index.html` to the repo root, commit,
push, and enable Pages: `gh api -X POST repos/<owner>/<repo>/pages -f "source[branch]=main" -f "source[path]=/"`.
Each later run: copy, commit, push. Pushing and creating repos are outward-facing — confirm the
first time.

Never send the page anywhere the user did not choose.

## Rules

- Facts on the page come from tools and scripts. Your own words go only into names, tags,
  diagram text and ticket `benefit` notes, and those must be checkable against code/docs.
- If a run cannot read a source, the page must say so (collect.py does this) — do not fill the
  gap with yesterday's data or a guess.
- Re-runs on the same day overwrite that day's snapshot; trends need snapshots on 2+ days.
- Scheduling is not built in. If the user wants it nightly, point them to `/schedule` (or cron
  for the script-only part: collect.py + build.py run without Claude, but then Linear/Notion
  are not refreshed and the page says so).
