---
name: project-inventory
description: >
  Take stock of all the user's projects and build one dashboard page: per project a
  "how it works" diagram, tickets (Linear / Notion / GitHub Issues), GitHub PRs, git state, Obsidian
  note tasks, data freshness, recent activity and trends, plus a home list of what
  waits on the user. Use when the user says "inventory my projects", "project status",
  "盤點專案", "專案總覽", "/project-inventory", "/project-inventory:project-inventory", or asks which data is out of date
  across projects. First run uses Quick start; "full setup" / "完整設定" opens the full
  eight-step setup. Later runs just refresh.
---

# project-inventory

Installed plugin command: `/project-inventory:project-inventory`; standalone skill:
`/project-inventory`. After installation or replacement, reload plugins/start a new
host session. File-copy checks cover clean, existing and reinstall homes; actual
Claude Code, Codex and Hermes loading and host versions remain manually unverified.
See the repository README for explicit installation paths.

All state lives in one folder, `HOME` = `~/.project-inventory` unless the user names another
(`HOME` below is a placeholder for that path, not the environment variable):

```
HOME/inventory.json          projects, sources, data checks, diagram   (you write it with the user)
HOME/gathered/<date>.json    tickets/PRs you fetched through MCP tools  (you write it each run)
HOME/facts/<date>.json       one snapshot per run                       (collect.py)
HOME/summaries.json          one plain-words summary per project-week   (you write it)
HOME/shots/<project>-<step>.png captured project UIs                     (capture_shots.py)
HOME/out/index.html          the page                                   (build.py)
HOME/out/artifact.html       HTML fragment for manual host import          (build.py)
```

`SCRIPTS` = the `scripts/` folder next to this file. Not running in Claude Code? The Python scripts are portable;
OS scheduling uses `schedule.py`; Artifact import/publication remains unverified. MCP steps need the matching
connector in your own tool, and without one, say which source was not read. Schemas for every file: `reference/schema.md`.
Talk to the user in their language and write page text (names, tags, diagram) in it too; set
`"lang"` in inventory.json (`zh-TW` and `en` have page labels; anything else falls back to `en`).

This file covers the two common runs. The rest lives next to it; read a file only when its case comes up:

| When | Read |
|---|---|
| "full setup" / "完整設定", or an item from Quick start's "Add more?" menu | `reference/setup.md` |
| A configured source the scripts cannot read (Notion, Linear without `LINEAR_API_KEY`, GitHub without working `gh`) | `reference/gather.md` |
| Sending the page anywhere but the local file | `reference/publish.md` |
| Unattended refresh: model notes, automatic step rewrites and reverting them, automatic Vercel publishing | `reference/auto-refresh.md` |

## Which run is this?

- Present → **Refresh** immediately, unchanged. If the user adds a project or a data source,
  edit inventory.json first. Do not rediscover projects or offer the Quick start menu.
- `HOME/inventory.json` missing → **Quick start** by default, including “inventory my projects”
  and “盤點專案”. Only an explicit “full setup” / “完整設定” chooses **Setup** (all eight steps
  in `reference/setup.md`).

## Quick start (default first run)

Ask exactly one question before delivering the local page: which projects to include.
Do not ask about sources, language, diagrams, writing skills, screenshots, models,
schedules or publishing before the page. Use the conversation language for page text.

1. **Discover and select (the only question).** Run
   `python3 SCRIPTS/discover.py --inventory-home HOME`. Use its JSON, never model scanning,
   to show a checkbox list with name, local paths, GitHub repo and last commit date.
   Keep the script's `selected` defaults: commits within the last 90 days are checked;
   older or unknown dates are unchecked. Ask which projects to include; allow selecting
   older projects too. If the user replies “also look in <folder>” / “也看 <資料夾>”, rerun
   the same script with that folder as a positional argument (defaults are still included),
   then present the updated selection. Never include an unconfirmed project.
   The script scans the current directory, `~`, and existing `~/projects`, `~/code`,
   `~/src`, `~/dev`, `~/repos`, `~/workspace`, at most two directory levels below each
   root. It skips `node_modules`, hidden directories, symlink directories and inventory
   HOME itself. Authenticated `gh repo list` adds GitHub repos, merged with local remotes.
   Report discovery warnings without adding another setup question. An empty selection
   still builds a local page with no projects.
2. **Configure without more questions.** For each selected project, read its README (when
   it has one) and entry points and draft `nodes`: 5–10 steps, the real order of work as the spine,
   inputs/alternatives on the left, checks/helpers on the right, with `paths` to the code
   for each step. Facts in `detail` must come from code or docs, not guesses. Give every
   step an `icon` from this list: spider brain box gear shield clock truck globe eye flame check dice table hand cards play coin quiz scale pipe lake flask chart book plug.
   For GitHub-only projects read those files
   through authenticated GitHub access; never execute project code. Do not invent steps
   if files cannot be read: report the gap and leave `nodes` empty for that project.
   Save `"draft": true` on every generated node. Do not show drafts for approval.
   Set `sources.local` from all discovered `paths` (each entry has `label` and `path`).
   Collection runs `git fetch -q origin` in each checkout, writing remote refs and
   `.git/FETCH_HEAD`; add `"fetch": false` to an entry only when the user said that
   checkout must not be touched.
   When discovery's `github_available` is true and a project has `github`, add that repo
   to `sources.github` for PRs; add `sources.github_issues` only when `has_issues` is true.
   Selecting the project authorizes these Quick start defaults; full Setup step 2 still
   confirms ticket sources individually. No Linear, Notion or Obsidian sources yet.
   Use distinct readable colors, `data: []`, omit `writing_skill`, set
   `auto_refresh: {"model": "none"}` with no schedule, and `publish: {"to": "local"}`.
   No screenshots (`shot`/`capture`), model CLI, schedule installation or publication.
3. **Save and deliver.** Write `HOME/inventory.json`, then run
   `python3 SCRIPTS/collect.py HOME --refresh` (it collects and builds the page in one go).
   Follow Refresh steps 3–5 for factual summaries, page checks, errors and the local path
   `HOME/out/index.html`; this requires no further setup questions. On collection exit 2,
   fix the reported input error and rerun before delivering. Exit 1 keeps failures visible.
   Do not enter the full Refresh sequence or its Publish step during Quick start.
4. **Add more? (once, after the page).** Offer one optional menu, with “skip all”:

   | Choice | Run only this step of `reference/setup.md` |
   |---|---|
   | Connect Linear / Notion / Obsidian tasks | Setup step 2, limited to the chosen connector |
   | Watch data | Setup step 3 |
   | Add screenshots | Setup step 5, limited to screenshot selection and preview; step 6 only saves approved images/config |
   | Scheduled updates | Setup step 8 |
   | Publish | `reference/publish.md` |

   Run only the chosen step(s); never restart Setup or ask unrelated setup questions.
   Save the chosen configuration and collect/build as needed. Do not repeat this menu
   on Refresh. Draft labels remain until the user reviews the diagram in Setup step 5
   or explicitly confirms it later; then remove `draft` only from the reviewed nodes.

## Refresh (every run)

1. **Gather through MCP** only what scripts cannot reach. The scripts themselves read local
   git, Obsidian, data files, GitHub PRs and Issues through `gh`, and Linear when
   `LINEAR_API_KEY` is set: with only those configured, skip this step. For Notion, Linear
   without the key, or GitHub when `gh` is missing, logged out or denied, follow
   `reference/gather.md` and write `HOME/gathered/<today>.json`. Get `<today>` by running
   `date +%F` — collect.py looks for this computer's local date, which can differ from the
   date you believe it is (time zones, runs near midnight). If a source fails, write the
   error into `errors` (start the text with the source name) — never drop it silently.
2. `python3 SCRIPTS/capture_shots.py HOME` re-captures the saved UI sources first.
   Then `python3 SCRIPTS/collect.py HOME --refresh` — collect and build this run's exact snapshot.
   A `BUSY:` message means another refresh owns the lock: stop this manual run and let it finish.
   Exit 0 = success; 1 = partial, with visible errors; 2 = fatal, retaining last-good data/time
   with a failure summary. On exit 2 fix the input or permissions and rerun; do not publish.
3. Step 2 already built `HOME/out/index.html`. `python3 SCRIPTS/build.py HOME` rebuilds that same
   snapshot (`refresh.json`) without collecting again: run it after you change summaries or page text.
   Both print `SUMMARIES n weeks need a summary: HOME/out/summaries-needed.json` when one of a
   project's newest 4 weeks (the ones the page shows before "earlier weeks" is clicked) has
   no summary yet or got new work since its summary was written. Older weeks are left out;
   `python3 SCRIPTS/build.py HOME --all-weeks` lists them too — run that only when the user
   asks to fill in the history ("補摘要"). For each listed week write 2–3 short sentences in the page
   language: what changed that week and why it matters, from the listed commits/tickets/PRs
   only — no guesses. An entry whose `week` is `"now"` is the project's status line, not a week:
   write two short sentences from its listed facts — first what is blocking the project, then
   the one next thing the user should do (name PRs as PR #N) — and save it under the key `"now"`
   the same way. It is listed again only when the blockers change. Before saving, if `writing_skill` is set, pass the drafts through
   that installed skill once as a wording-only edit. Apply this rule whenever you write or
   rewrite diagram step `title`/`sub`/`zone` in a conversation too; never pass `detail`, `paths`
   or `media` (mocks marked `real: true` must stay copied output). Facts, numbers, dates, names, links and
   JSON structure must stay identical: compare with the originals after the pass and discard
   the pass if any changed. If the skill is unavailable in this session, say so once in the
   report and continue without it. Absent `writing_skill` means no polishing.
   Save summaries in `HOME/summaries.json` as
   `{"<key>": {"<week>": {"n": <n from the list>, "text": "…"}}}` (keep the other weeks), then
   run build.py again.
4. **Check the page** before handing it over: `python3 SCRIPTS/check_page.py HOME` (headless
   Chromium: every project tab at 390 px and 1280 px, light and dark, every diagram step, no JS
   errors, no sideways scroll). `Chromium not found` → say UNVERIFIED for the layout. `check_page.py` cannot
   start because the temp folder is read-only (some sandboxes, e.g. Codex)? Re-run it with
   `TMPDIR` set to a writable folder, e.g. `mkdir -p HOME/tmp && TMPDIR=HOME/tmp python3 ...`.
5. **Report** in chat: first line = what failed, if anything. Then what waits on the user (the
   home list), which data is stale, and the page path / URL.
6. **Publish** only where the user chooses (ask once, remember it in inventory.json `publish`).
   The default is the local file `HOME/out/index.html`. For anything else read
   `reference/publish.md` first. Never send the page anywhere the user did not choose.

## Rules

- Facts on the page come from tools and scripts. Your own words go only into names, tags,
  diagram text, ticket `benefit` notes and week summaries, and those must be checkable against code/docs.
- If a run cannot read a source, the page must say so (collect.py does this) — do not fill the
  gap with yesterday's data or a guess.
- Re-runs on the same day overwrite that day's snapshot. The ticket chart is rebuilt from ticket
  dates and the commit chart from git history, so both show on the first run.
- `build.py` prints `WARN` lines (a screenshot not found, a page over 8 MB). Report them.
- The top **Needs Claude** banner lists stale/unread MCP sources, missing week summaries,
  and Artifact publishing, with `/project-inventory` on each row. Invoke that command to
  gather MCP sources or fill missing summaries; automatic jobs never call MCP.
- Scheduled refresh (`python3 SCRIPTS/auto_refresh.py HOME`) is script-only and shares
  `HOME/state/refresh.lock` with manual runs. Its rules are in `reference/auto-refresh.md`.
