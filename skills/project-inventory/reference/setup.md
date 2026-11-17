# Full setup

Read when the user asks for full setup / 完整設定, or picks an item from Quick start's "Add more?" menu
(then run only the step that menu names). `HOME` and `SCRIPTS` mean what `SKILL.md` says.

Confirm each step with the user, one question at a time

1. **Projects.** Ask which projects to include. Offer what you can see: Linear projects
   (`list_projects` if a Linear MCP is connected), Notion databases/pages the user names,
   GitHub repos (`gh repo list` or GitHub MCP), local git checkouts under folders they name,
   Obsidian vault folders. Never include a project the user did not confirm.
2. **Sources per project.** Ask where each project's tickets live:
   **Linear / Notion / GitHub Issues / none**. Save the answer in the matching
   `sources.linear`, `sources.notion`, or `sources.github_issues` configuration; for none,
   save no ticket-source keys. Confirm the Issues repos separately from PR repos.
   Never enable GitHub Issues just because a repo is listed under `sources.github` for PRs.
   Fill other `sources` (see schema): `github`, `local`, `obsidian`. Check each one actually answers now (one MCP call / one `git -C <path> status`).
   For Linear, confirm and save `sources.linear.project_id` (project UUID) and `project`
   (display name), including archived projects. Same names can span teams: show the candidate
   IDs/team names and let the user choose; never merge them. Legacy name-only settings work
   only with one match; migrate by saving its confirmed UUID, especially before a rename.
   A source with no connector: tell the user which connector to add, leave it out for now.
   For Obsidian, ask which folders hold real tasks. Save the vault folder to scan in
   each `sources.obsidian[].path` and optional `exclude` folders relative to that vault
   path (for example `templates`, `marp`, `.superpowers`). The scan reads Markdown
   recursively, always skips `.obsidian` and `.trash`, and ignores fenced code blocks
   and blank checkboxes. Within each source, identical full task text after `strip()`
   counts once (exact matching only); any checked copy makes it done, otherwise open.
   Listed items point to the newest file holding an open copy, using the existing
   lexicographic path order, not parsed dates or modification times. Counts include all
   unique tasks; only the first 50 open tasks are listed. No new configuration is needed.
   Collection runs `git fetch -q origin` by default, writing remote refs and `.git/FETCH_HEAD`.
   For a checkout that must not be fetched, save `"fetch": false` on that `sources.local[]`
   entry. HEAD, branch, dirty files and history are still read; remote comparisons are unknown.
   History defaults to all refs (`git log --all`); `"history": "head"` limits it to HEAD.
3. **Data to watch.** Look for data the project produces (data/, *.csv, *.parquet, *.sqlite,
   *.jsonl, generated JSON). Show the candidates; for each one the user keeps, find the
   **date column inside the data** (never use file modification times — they lie after copies
   and rebuilds) and ask how many days old counts as stale. Run `collect.py` once to prove each
   check reads.
4. **Optional writing skill.** Ask whether the user wants an installed writing skill
   (for example sepia, or any rewriting/plain-language skill they already have) to polish
   summaries and diagram step `title`/`sub`/`zone`. Save its name (plugin skills are namespaced,
   e.g. `sepia:sepia` for the Claude Code plugin; `sepia` for a standalone install) in top-level `writing_skill`; default
   none (omit the field). Never install skills for the user.
5. **Diagram.** Read each project's README and entry points, draft `nodes` (5–10 steps: the
   real order of work as the spine, inputs/alternatives on the left, checks/helpers on the
   right), with `paths` to the code for each step. Show the draft as a short list; fix what the
   user corrects. After the user approves, remove `draft` from the reviewed nodes.
   Facts in `detail` must come from code or docs, not guesses.
   Apply the writing-skill rule in `SKILL.md` Refresh step 3 to these drafts too.
   Give every step an `icon` from this list: spider brain box gear shield clock truck globe eye flame check dice table hand cards play coin quiz scale pipe lake flask chart book plug.
   Then offer what a step can open to (`media`, see schema): a `mock` (a few lines showing what
   goes in and out, copied from real code/output; mark `real: true` only when it is real output),
   a `math` formula the code actually computes, a `link`, or a screenshot. For projects with a UI,
   find an existing URL in README links, package.json `homepage`, Vercel or GitHub Pages,
   or an HTML file the project ships or has already produced. Propose which steps get a
   screenshot and show their exact `capture` URL/path. In each caption, say whether
   it shows the live site or a local build output; a live site may differ from the checkout.
   `capture_shots.py` records `captured_at`, which the page shows beside the caption. Never start project servers, install
   dependencies or run project/build code; only open existing URLs/files in Chromium.
   User-supplied screenshot files still work via `shot`. Projects without a UI get no `shot`
   or `capture`; the page shows no placeholder or "no screenshot" text. Skip unwanted media.
   To preview captures before saving the final configuration, write the draft inventory
   into a temporary home, run
   `python3 SCRIPTS/capture_shots.py TEMP_HOME`, and show the resulting images to the user.
   Resolve relative HTML paths against the intended HOME before putting them in the temporary
   draft. Capture failures print `WARN`, retain any previous image and do not fail the run.
   Report warnings to the user.
6. After review, copy approved images to `HOME/shots/` and save `HOME/inventory.json`
   with the reviewed `capture` sources and HOME-relative `shot` paths. Pick distinct `color`s
   that read in light and dark mode.
7. **Optional plain words.** Ask which CLI may write summaries and commit/PR notes:
   `claude` (Haiku), `codex` (gpt-6-luna), or `none` (default; nothing sent).
   Save `auto_refresh.model`. Explain that notes receive listed work, while diagram step
   rewrites may read the project through read-only tools. Successful notes are cached by
   full commit hash / PR URL.
   Auto-refresh can rewrite only the wording of existing steps (`title`, `sub`, `zone`);
   it never adds steps, paths, detail or media. With `none`, even wording stays unchanged.
   For example, after a new `report.py` appears, read it and confirm its place in the flow
   with the user, then append a step by hand to that project's `nodes` in inventory.json
   (choose an unused id and adjust the text to match the code):

   ```json
   {"id": 3, "title": "Write report", "sub": "Save the processed results", "icon": "book", "paths": ["report.py"]}
   ```

   Run collect/build again to show the new step. Add any detail or media explicitly.
8. **Optional schedule, ask once.** Ask whether to install unattended refresh; default is no.
   Only on yes: offer every 2 hours, 08:00–22:00 inclusive in this computer's local time;
   let the user change the hours/cadence. Save `auto_refresh.schedule` (see schema).
   Run `python3 SCRIPTS/schedule.py print HOME` and show the exact cron line / schtasks
   command before `python3 SCRIPTS/schedule.py install HOME`. Never install on silence.
   `remove HOME` removes only this home's marked entry. No Claude/Codex chat is scheduled.
