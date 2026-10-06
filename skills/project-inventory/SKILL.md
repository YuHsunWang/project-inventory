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
HOME/summaries.json          one plain-words summary per project-week   (you write it)
HOME/out/index.html          the page                                   (build.py)
HOME/out/artifact.html       same page for a claude.ai Artifact          (build.py)
```

`SCRIPTS` = the `scripts/` folder next to this file. Not running in Claude Code? Everything works
the same except the Artifact publish option and `/schedule`; MCP steps need the matching
connector in your own tool, and without one, say which source was not read. Schemas for every file: `reference/schema.md`.
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
   For Linear, confirm and save `sources.linear.project_id` (project UUID) and `project`
   (display name), including archived projects. Same names can span teams: show the candidate
   IDs/team names and let the user choose; never merge them. Legacy name-only settings work
   only with one match; migrate by saving its confirmed UUID, especially before a rename.
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
   Give every step an `icon` from this list: spider brain box gear shield clock truck globe eye flame check dice table hand cards play coin quiz scale pipe lake flask chart book plug.
   Then offer what a step can open to (`media`, see schema): a `mock` (a few lines showing what
   goes in and out, copied from real code/output; mark `real: true` only when it is real output),
   a `math` formula the code actually computes, a `link`, or a `shot` screenshot — ask the user
   for screenshot files; never invent one. Skip media the user does not want.
5. Save `HOME/inventory.json`. Pick distinct `color`s that read in light and dark mode.

## Refresh (every run)

1. **Gather through MCP** what scripts cannot reach, into `HOME/gathered/<today>.json`.
   Get `<today>` by running `date +%F` — collect.py looks for this computer's local date, which
   can differ from the date you believe it is (time zones, runs near midnight).
   - Linear: skip this if `LINEAR_API_KEY` is set in the environment — collect.py then reads
     Linear itself (faster, exact). Otherwise: every issue of the project, archived ones included (`list_issues` with the
     confirmed project UUID (resolve legacy names uniquely first), `includeArchived: true`, `limit: 250`; it returns one page at a time — pass the
     returned `cursor` back until there is no next page).
     Map exactly as collect.py does: status type completed → `done`, canceled → `dead`, status
     name containing "review" → `wait`, everything else → `open`. Ask for the `createdAt`,
     `completedAt` and `canceledAt` fields and keep them as `created` / `completed` / `canceled`
     (the page's ticket chart is rebuilt from these dates).
   - Notion: follow the connector playbook in `reference/schema.md#notion-connector-playbook`.
     Resolve database versus data source identity before querying; paginate every query and
     recursively paginate child blocks until `has_more: false`. Normalize raw statuses using
     the saved `sources.notion.status_map`; to-do `checked` maps to done/open. Preserve full
     page/block IDs, raw status, date availability and date coverage. Unknown statuses or any
     unread page/child make the source partial/failed, never a complete current list.
     This contract has offline mock coverage only; validate it in an authorized workspace
     before claiming a real Notion integration succeeded.
   - GitHub PRs: scripts paginate every open PR with `gh api graphql`. If `gh` is missing,
     not logged in (`gh auth status` fails), or cannot read the repo, use GitHub MCP instead.
     Follow every returned cursor, put normalized `number`, `title`, `url`, `createdAt`,
     `isDraft`, `headRefName`, and `repo` under `prs`. Mark the per-repo source `ok` and
     `complete: true` only after the final page, including zero PRs. A denied later page is
     `failed`/`partial` with its error, never a complete short list. A fresh MCP gather takes
     precedence even when `gh` is installed; collect.py otherwise reports CLI failures.
   - Create a unique `_run.run_id` for this gather. For each source write
     `run_id`, `attempted_at`, `fetched_at`, `status`, `complete`, and `error` under `sources`
     (see schema). Track MCP PRs per `github:<owner/repo>`. Never reuse a gather run.
   - List every source you read in `read`. If a source fails, write the error into `errors`
     (start the text with the source name) — never drop it silently.
2. `python3 SCRIPTS/collect.py HOME --refresh` — collect and build this run's exact snapshot.
   Exit 0 = success; 1 = partial, with visible errors; 2 = fatal, retaining last-good data/time
   with a failure summary. On exit 2 fix the input or permissions and rerun; do not publish.
3. `python3 SCRIPTS/build.py HOME` rebuilds only the snapshot in `refresh.json` → `HOME/out/index.html`.
   It prints `SUMMARIES n weeks need a summary: HOME/out/summaries-needed.json` when a week has
   no summary yet or got new work since its summary was written (the current week, usually; on
   the first run, every past week). For each listed week write 2–3 short sentences in the page
   language: what changed that week and why it matters, from the listed commits/tickets/PRs
   only — no guesses. Save them in `HOME/summaries.json` as
   `{"<key>": {"<week>": {"n": <n from the list>, "text": "…"}}}` (keep the other weeks), then
   run build.py again. Many weeks on a first run: do them in batches; weeks not yet written
   show "no summary" on the page.
4. **Check the page** before handing it over: open it in a headless browser if one is available
   (Playwright: every project tab at 390 px and 1280 px, click every diagram step, no JS errors,
   no sideways scroll). No browser → say UNVERIFIED for the layout. `check_page.py` cannot
   start because the temp folder is read-only (some sandboxes, e.g. Codex)? Re-run it with
   `TMPDIR` set to a writable folder, e.g. `mkdir -p HOME/tmp && TMPDIR=HOME/tmp python3 ...`.
5. **Report** in chat: first line = what failed, if anything. Then what waits on the user (the
   home list), which data is stale, and the page path / URL.
6. **Publish** only where the user chooses (ask once, remember it in inventory.json `publish`).

## Publish options (ask; default = local file)

| Option | How | Who can see it |
|---|---|---|
| Local file (default) | `HOME/out/index.html`, open in a browser | only this computer |
| claude.ai Artifact (Claude Code only) | Artifact tool, publish `HOME/out/artifact.html` (build.py writes it without the html/head/body wrapper the host adds; the same file path every run keeps one URL) | private to the user |
| Vercel | `python3 SCRIPTS/publish_vercel.py HOME <project-name>` (refuses an existing project it did not create; `--reuse` only after the user confirms that project is for this page) — creates the project, locks it (Vercel Authentication, all deployments) BEFORE deploying, then checks an anonymous visitor is turned away | Vercel-authorized users; actual access depends on team/project membership, granted access, sharing and bypass settings |
| GitHub Pages | see below | **everyone on the internet** |

**GitHub Pages is public**, also from a private repo on a free plan. The page lists project
names, tickets, branches, file paths and data locations. Before the first Pages publish, say
this in one plain sentence and get an explicit yes. Then: a repo the user names (create it with
`gh repo create <name> --private` if needed), copy `out/index.html` to the repo root, commit,
push, and enable Pages on the repo's default branch (`gh repo view <owner>/<repo> --json defaultBranchRef -q .defaultBranchRef.name`;
it is not always `main`): `gh api -X POST repos/<owner>/<repo>/pages -f "source[branch]=<branch>" -f "source[path]=/"`.
Each later run: copy, commit, push. Pushing and creating repos are outward-facing — confirm the
first time.

Never send the page anywhere the user did not choose.

## Rules

- Facts on the page come from tools and scripts. Your own words go only into names, tags,
  diagram text, ticket `benefit` notes and week summaries, and those must be checkable against code/docs.
- If a run cannot read a source, the page must say so (collect.py does this) — do not fill the
  gap with yesterday's data or a guess.
- Re-runs on the same day overwrite that day's snapshot. The ticket chart is rebuilt from ticket
  dates and the commit chart from git history, so both show on the first run.
- `build.py` prints `WARN` lines (a screenshot not found, a page over 8 MB). Report them.
- Scheduling is not built in. If the user wants it nightly, point them to `/schedule` in Claude Code (or cron
  for the script-only part: `collect.py HOME --refresh --script-only`; partial failures still build,
  fatal failures stop and retain last-good data with a warning.
  Cron has a bare environment: set `PATH` so it finds git and gh, and `LINEAR_API_KEY` if used).
