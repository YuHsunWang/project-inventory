# project-inventory

**English** | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

[![CI](https://github.com/YuHsunWang/project-inventory/actions/workflows/ci.yml/badge.svg)](https://github.com/YuHsunWang/project-inventory/actions/workflows/ci.yml) [![Pages](https://github.com/YuHsunWang/project-inventory/actions/workflows/pages.yml/badge.svg)](https://github.com/YuHsunWang/project-inventory/actions/workflows/pages.yml) [![Latest release](https://img.shields.io/github/v/release/YuHsunWang/project-inventory)](https://github.com/YuHsunWang/project-inventory/releases/latest) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> One dashboard for people juggling projects: see how each project works, what changed, which tickets need you, and which data is out of date.

A portable [Agent Skill](https://agentskills.io/specification), installable on many agents in one command with the [Skills CLI](https://skills.sh), and available as a native Claude Code plugin.

![Sample dashboard: home, project and an expanded step](skills/project-inventory/reference/demo.gif)

[Live demo — sample data only](https://yuhsunwang.github.io/project-inventory/)

[Desktop PNG](skills/project-inventory/reference/demo-desktop.png) · [Mobile PNG](skills/project-inventory/reference/demo-mobile.png). The GIF and PNGs contain sample data only. The PNGs are Chromium captures at 1280 and 390 px; no real project information or external API results are included.

Detailed Traditional Chinese manual: [說明書.md](說明書.md).

## Table of Contents

- [Why project-inventory?](#why-project-inventory)
- [Entry points](#entry-points)
- [Install](#install)
- [Uninstall](#uninstall)
- [Use](#use)
- [My workflow and companion skills](#my-workflow-and-companion-skills)
- [Try it locally without accounts](#try-it-locally-without-accounts)
- [Requirements](#requirements)
- [Publishing and privacy](#publishing-and-privacy)
- [Scripts](#scripts)
- [Scheduled refresh and AI text](#scheduled-refresh-and-ai-text)
- [Verification status](#verification-status)
- [Troubleshooting](#troubleshooting)
- [Layout](#layout)
- [License](#license)

---

## Why project-inventory?

Project work is spread across checkouts, tickets, notes and data files. This skill reads those sources into one page, with a home list of everything waiting on you across projects.

| Source | What it contributes |
|---|---|
| Local Git checkouts | Branches, uncommitted files, history, remotes and unpushed commits |
| GitHub | Open PRs; tickets only from explicitly configured GitHub Issues repos |
| Linear / Notion | Tickets: done, waiting for review, open and canceled |
| Obsidian | Open Markdown note tasks (`- [ ]` lines) |
| CSV / JSON / JSONL / SQLite / Parquet / DuckDB | Newest dates read from file contents, not file timestamps |

| On each project page | What you see |
|---|---|
| How it works | An icon for each diagram step, drafted from code and confirmed by you; expandable screenshots, formulas or input/output sketches |
| Tickets | Done, waiting for your review, open and canceled work |
| Facts: local | Checkouts, branches, uncommitted files, data files and Obsidian notes |
| Facts: cloud | Each checkout's remote and unpushed commits, open PRs, Linear project and Notion page |
| Data freshness | The newest date inside each watched dataset |
| Progress | Commits per week and open/done ticket trends over 90 days, rebuilt where ticket dates are known; unknown periods and incomplete coverage are labelled |
| Weekly history | The whole history in 2–3 sentence summaries, expandable to every commit, finished ticket and new PR; four weeks initially, then four more per click |

The footer names only configured ticket providers. Projects without one say “No ticket source set.” Empty progress charts are hidden when no ticket source or local Git history is configured. Source failures stay visible.

## Entry points

| Tool / installation | How to invoke |
|---|---|
| Claude Code plugin | `/project-inventory:project-inventory` |
| Standalone skill | `/project-inventory` |
| Any agent | Ask “inventory my projects” or 「盤點專案」 |
| Other tools that run shell commands | Ask the tool to read `skills/project-inventory/SKILL.md` and follow it |

The plugin namespace comes from `.claude-plugin/plugin.json`. See the [Claude Code plugin loading rules](https://code.claude.com/docs/en/plugins).

> **Notice:** “Verified” installation means the command completed and the files are in place. Runtime behavior has been verified on Claude Code and Codex only. No host version was recorded; the repository's formal host-loading and service acceptance limits remain in [Verification status](#verification-status).

> **Tip:** After installation or replacement, reload plugins or start a new tool session.

## Install

Paste this sentence into your agent to install and self-check. The agent needs network access and write access to your home directory; if a Codex sandbox blocks either, report it as a permission problem:

> Install project-inventory: read https://raw.githubusercontent.com/YuHsunWang/project-inventory/main/INSTALL.md and follow it.

### Skills CLI — many agents

User scope is the default in these instructions:

```sh
# install
npx skills add YuHsunWang/project-inventory -g
npx skills ls -g
# update
npx skills update project-inventory -g
```

Installation checked on 2026-10-17 in an isolated home: the skill and all scripts were installed to `~/.agents/skills/project-inventory`, shared with Codex and other universal agents, and symlinked into Claude Code. `npx skills ls -g` listed Claude Code and Codex.

### Claude Code plugin

```sh
# install
claude plugin marketplace add YuHsunWang/project-inventory
claude plugin install project-inventory@project-inventory --scope user
# update
claude plugin marketplace update project-inventory
claude plugin update project-inventory
```

> **Tip:** In-session `/plugin install` asks for a scope. Choose **User**. Start a new session or reload plugins, then run `/project-inventory:project-inventory`.

### Manual Codex standalone copy

No MCP server is needed for skill installation. For a first manual install, clone once and enter the checkout:

```sh
# install — obtain the checkout once for either manual copy below
git clone https://github.com/YuHsunWang/project-inventory
cd project-inventory
# update — enter your existing, updated checkout and repeat the matching copy below
```

```sh
# install
mkdir -p ~/.codex/skills/project-inventory
cp -R skills/project-inventory/. ~/.codex/skills/project-inventory/
test -f ~/.codex/skills/project-inventory/SKILL.md && echo "Codex skill files OK"
# update — from your updated checkout
mkdir -p ~/.codex/skills/project-inventory
cp -R skills/project-inventory/. ~/.codex/skills/project-inventory/
test -f ~/.codex/skills/project-inventory/SKILL.md && echo "Codex skill files OK"
```

### Manual Hermes standalone copy

Use the same repository checkout:

```sh
# install
mkdir -p ~/.hermes/skills/project-inventory
cp -R skills/project-inventory/. ~/.hermes/skills/project-inventory/
test -f ~/.hermes/skills/project-inventory/SKILL.md && echo "Hermes skill files OK"
# update — from your updated checkout
mkdir -p ~/.hermes/skills/project-inventory
cp -R skills/project-inventory/. ~/.hermes/skills/project-inventory/
test -f ~/.hermes/skills/project-inventory/SKILL.md && echo "Hermes skill files OK"
```

Both copy methods work when the tool's home already exists without a `skills` folder. For an existing install or reinstall, run the matching `mkdir`, `cp` and `test` lines in the existing checkout. They update files in place, preserve sibling skills and avoid a nested `project-inventory` folder. Start a new tool session afterward. Linear and Notion need the agent's own connector, or `LINEAR_API_KEY` for Linear.

### Project scope (alternative)

For a Claude Code plugin installed in the current project instead of user scope:

```sh
# install
claude plugin marketplace add YuHsunWang/project-inventory
claude plugin install project-inventory@project-inventory --scope project
# update
claude plugin marketplace update project-inventory
claude plugin update project-inventory
```

## Uninstall

Run only the command matching the installation you used. Manual-copy commands remove only the skill folder.

```sh
# Skills CLI — user scope
npx skills remove project-inventory -g
# Claude Code plugin — user scope
claude plugin uninstall project-inventory@project-inventory --scope user
# Claude Code plugin — project scope alternative
claude plugin uninstall project-inventory@project-inventory --scope project
# Manual Codex copy
rm -r ~/.codex/skills/project-inventory
# Manual Hermes copy
rm -r ~/.hermes/skills/project-inventory
```

## Use

| Run | What happens |
|---|---|
| First run | Quick start asks one question: pick projects from deterministic local/GitHub discovery (commits within 90 days checked by default). It builds a local page with AI draft diagrams; authenticated GitHub PRs and enabled Issues use defaults. Then one optional menu offers task connectors, data checks, screenshots, scheduling or publishing. Say “full setup” / “完整設定” for the original eight-step setup. |
| UI setup | It finds an existing URL or HTML output, proposes screenshots for relevant steps, captures and shows the images before saving. Supplied screenshots work too. Projects without a UI show no screenshot placeholder. It never starts project servers or runs project/build code. |
| Later runs | It re-reads every source and rebuilds the page. It fills summaries for weeks that have none or have new work since the last summary, usually the current week. The first run covers all past weeks and takes longer. |

Configuration is saved to `~/.project-inventory/inventory.json`. Weekly summaries live in `~/.project-inventory/summaries.json` and are not rewritten once a week is over. Captions show `captured_at` and identify a live site or local build output; capture source URLs stay out of the HTML.

### Git and ticket source details

| Source | Collection rules |
|---|---|
| Local Git | Fetches `origin` by default, updating refs and `.git/FETCH_HEAD`. Set `"fetch": false` on a `sources.local[]` entry to read HEAD, branch, dirty files and history without fetching; ahead/behind and remote unpushed counts remain unknown. History defaults to `git log --all`; `"history": "head"` limits it to commits reachable from HEAD. Progress labels each checkout's scope. Unread or disconnected history appears as not collected, with source errors, on project cards and the home list. |
| GitHub Issues | Explicitly set `sources.github_issues: ["owner/repo"]`. Collection reads all open and closed issues, excludes PRs and rebuilds trends from creation/closure dates. Closed-as-not-planned is canceled; other closed issues are done. Missing `gh` access or an unread page shows a failed source. Existing configurations remain valid. |
| Obsidian | Setup asks which folders contain real tasks. Each source scans Markdown recursively under its vault `path`; optional `exclude` folders are relative to that path. `.obsidian`, `.trash`, fenced code blocks and blank checkboxes are skipped. Within each source, identical full text after `strip()` counts once, with exact matching only. Any checked copy makes the task done; otherwise it is open. Each listed item points to the newest file holding an open copy, using lexicographic path order, not parsed dates or modification times. Counts include all unique tasks; the list shows the first 50 open tasks. No new configuration is needed. |

## My workflow and companion skills

1. Set up the projects, sources and diagrams with the agent.
2. Refresh the project data.
3. Have the agent write weekly summaries and diagram step text from those facts.
4. Optionally pass the drafts through your chosen writing skill once.
5. Build the page with the finished text.
6. Check the page.
7. Publish where you choose.

I recommend [sepia](https://github.com/Nanako0129/sepia) to remove AI-sounding patterns from prose. Install it in Claude Code:

```sh
claude plugin marketplace add Nanako0129/sepia
claude plugin install sepia@sepia --scope user
```

For other agents:

```sh
npx skills add Nanako0129/sepia -g
```

To enable it, answer the optional setup question or add it to `inventory.json`: `"writing_skill": "sepia:sepia"` for the Claude Code plugin install (plugin skills are namespaced), or `"writing_skill": "sepia"` for the Skills CLI install. Any rewriting or plain-language skill you already have works the same way: give its installed name. The field accepts only ASCII letters, digits, `-`, `_` and `:`. Omit it for no polishing, the default. The agent never installs skills for you.

> **Notice:** Only conversation runs use the writing skill. Scheduled unattended refresh (`auto_refresh.py` / `step_refresh.py` through the `claude` / `codex` CLI) does not use it. Polishing changes wording only: facts, numbers, dates, names, links and JSON structure are checked to stay identical; a pass that changes any of them is discarded. If the skill is unavailable in the session, the agent reports it once and continues without it.

## Try it locally without accounts

From this repository checkout, use a new demo directory:

```sh
mkdir -p .tmp
export TMPDIR="$PWD/.tmp"
python3 skills/project-inventory/reference/demo.py .tmp/demo
python3 skills/project-inventory/scripts/collect.py .tmp/demo
python3 skills/project-inventory/scripts/build.py .tmp/demo
python3 tests/demo_fixture.py .tmp/demo --offline-fonts
python3 skills/project-inventory/scripts/check_page.py .tmp/demo --shots .tmp/demo-shots
```

Open `.tmp/demo/out/index.html`. The helper derives its configuration from `example-inventory.json` and creates three fictional projects: a web app, a data pipeline and a writing project. Each has local Git history, Markdown review tasks and sample CSV data; one dataset is deliberately stale. No accounts, tokens or network access are needed. The helper refuses to overwrite an existing inventory. Python/git suffice for collect/build; the optional browser check requires Playwright/Chromium below. The offline-fonts helper uses fallback fonts to avoid font CDN requests.

Regenerate the animated preview from a fresh sample-only build with Playwright, Chromium and Pillow:

```sh
python3 skills/project-inventory/reference/demo_gif.py
```

## Requirements

| Needed for | What |
|---|---|
| Everything | Python 3.9+, git |
| Linear tickets | A Linear MCP connector in Claude, or `LINEAR_API_KEY` in the environment (faster; scripts read Linear without Claude) |
| Notion tickets | A Notion MCP connector in Claude |
| GitHub Issues tickets | Logged-in `gh` CLI; explicitly confirmed `sources.github_issues` repos |
| GitHub PRs | Logged-in `gh` CLI, or a GitHub MCP connector |
| Parquet / DuckDB data checks | `pip install duckdb` |
| UI capture / page check | `pip install playwright && python3 -m playwright install chromium` (optional) |
| Vercel publishing | Logged-in Vercel CLI (`vercel login`) |

## Publishing and privacy

You choose where the page goes. The default is a local file.

| Option | Who can see it |
|---|---|
| Local file `~/.project-inventory/out/index.html` | Only you |
| HTML for manual import into claude.ai Artifact | Host-dependent; publication, sharing and access are unverified |
| Vercel | Vercel-authorized users; access depends on team/project membership, granted access, sharing and bypass settings ([access rules](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments/vercel-authentication)). Protection is enabled before the first deploy; every deploy is checked from outside. |
| GitHub Pages | **Everyone**. The agent asks before the first publish. |

`build.py` also writes `out/artifact.html`: a fragment with styles/scripts and page content, without the document wrapper or meta tags, for manual import into a compatible host. There is no Artifact publishing API, host capability detection or saved artifact identity; a file path does not preserve a URL. End-to-end import/publishing is **pending**. Before claiming support, record host/version and test create/update identity, stable URL, external fonts/MathJax scripts, CSP handling and sharing permissions. No private or fixed-URL guarantee is made.

### GitHub Pages plan and preview

| Repository / plan | Standard Pages path |
|---|---|
| GitHub Free, public repo | Supported; repository and site are public |
| GitHub Free, private repo | Not supported. Keep the page local or choose another host; never automatically change repo visibility. |
| GitHub Pro / Team, private repo | Supported; repository stays private, but the standard site is public |

See [GitHub's plan requirements](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages). Enterprise access-controlled Pages is separate and unverified in this workflow.

> **Notice:** Before publishing, preview the local page and its embedded assets. Project names, tickets, branches, file paths and screenshots may be exposed. Confirm the account plan, repository visibility and exact public content before creating a repo or pushing.

For a minimal public page, use a separate inventory home with only approved project names/tags/diagram text, empty `sources` and `data`, and no `notes`, node `paths` or `media`. Collect, build and preview that home again. There is no automatic redaction switch.

`publish_vercel.py` refuses to overwrite a Vercel project it did not create; pass `--reuse` once to use an existing project. Without `VERCEL_TOKEN`, it runs `vercel whoami` before reading CLI credentials. A failed credential refresh stops publishing with a login instruction.

## Scripts

Scripts live in `skills/project-inventory/scripts/` and run without Claude. For manual use, clone this repo: the plugin's own copy lives in Claude's plugin folder. Write `~/.project-inventory/inventory.json` yourself, starting from [example-inventory.json](skills/project-inventory/reference/example-inventory.json).

```sh
S=skills/project-inventory/scripts
python3 $S/collect.py ~/.project-inventory     # git, gh PRs/opted-in Issues, Obsidian tasks, data checks -> facts/<date>.json
python3 $S/capture_shots.py ~/.project-inventory # existing UI URLs/HTML -> shots/, updates shot paths
python3 $S/build.py   ~/.project-inventory     # -> out/index.html
python3 $S/check_page.py ~/.project-inventory  # headless browser check, every tab and step, 390 + 1280 px
python3 $S/publish_vercel.py ~/.project-inventory <vercel-project-name>
```

Without Claude, scripts do not refresh Notion, or Linear unless `LINEAR_API_KEY` is set. Without an optional text CLI, they write no weekly summaries: new weeks show “no summary yet” until the next Claude run. `build.py` lists them in `out/summaries-needed.json`.

Use `python3 collect.py HOME --refresh` for one refresh; it builds only that run's snapshot.

| Exit | Meaning / recovery |
|---|---|
| 0 | Success |
| 1 | Partial collection; the page shows failed sources |
| 2 | Fatal failure; fix input or permissions and rerun. Do not publish. |

`refresh.json` records the run and exact snapshot. Fatal failures retain the last page's data/time with a visible failure summary. Standalone build checks this manifest; legacy homes without one can still be built. File formats: [schema.md](skills/project-inventory/reference/schema.md).

## Scheduled refresh and AI text

Unattended refresh is opt-in during Setup. Choose `auto_refresh.model`: `none` (default; no AI calls), `claude` (Haiku), or `codex` (gpt-6-luna). Only with consent, preview and install one OS schedule: cron on macOS/Linux, schtasks on Windows.

The commands below use `S` from [Scripts](#scripts).

```sh
python3 $S/schedule.py print ~/.project-inventory
python3 $S/schedule.py install ~/.project-inventory  # only after reviewing the printed command
python3 $S/schedule.py remove ~/.project-inventory
python3 $S/auto_refresh.py ~/.project-inventory     # run once without installing anything
```

| Behavior | Details |
|---|---|
| Schedule | Every 2 hours, 08:00–22:00 inclusive, computer local time. Customize with `--every`, `--start`, `--end` or `auto_refresh.schedule` in the schema. Installation replaces this home's marked entry and captures PATH for git/gh/codex/claude/vercel. Keep `LINEAR_API_KEY` in the scheduler environment, not the printed command. Reinstall after moving the skill or CLI locations. No chat session is scheduled. |
| Screenshots | Saved `media.capture` URLs/HTML are re-captured before fingerprint checks. Failures print `WARN`, keep the previous image and retry next run; identical images stay untouched. |
| Changes and locks | Same source fingerprints and calendar day skip collect/build/model/publish. Failed script reads always run and show errors. Freshness still reads dates inside data. Manual and automatic collection share an OS lock, released immediately on a crash; a live run is never evicted by age. |
| AI summaries and notes | An enabled text CLI batches missing week summaries and uncached commit/PR notes once per project; failures leave them missing. |
| Needs Claude banner | Lists only MCP sources needing a read, missing summaries and manual Artifact publishing, with the exact `/project-inventory` command |
| Publishing | Local HTML is always built on changed runs. Vercel (`publish.to: vercel`, `project`, optional `team`) deploys only changed page hashes through the protected publisher. GitHub Pages never publishes automatically; Artifact publishing remains manual. |

### Diagram text updates and undo

With a text CLI enabled, commits touching a step's `paths` can update only `title`, `sub` and `zone` directly in `inventory.json`. It never adds steps, paths, details or media; add new steps by hand after reviewing new files (see Setup in [SKILL.md](skills/project-inventory/SKILL.md)). `none` disables step rewriting and notes.

The first run only records each checkout's HEAD. Later runs send all changed steps of one project in one read-only session, at most once per calendar day in the inventory timezone. The model may read the project; repository content is treated as data. Relative paths resolve against each checkout; absolute and `~` paths inside it count too. Paths outside all checkouts are ignored. Invalid steps keep their checked commit for a later day's retry; a valid empty object means no change is needed.

Updated boxes show “AI-updated (YYYY-MM-DD)”. Previous text is kept in `step_history.json`; checked commits and the daily session date live in `state/steps.json`. To undo the latest rewrite for one step and rebuild locally:

```sh
python3 $S/auto_refresh.py ~/.project-inventory --revert-step PROJECT_KEY STEP_ID
python3 $S/auto_refresh.py ~/.project-inventory
```

Revert restores only the text and removes the label, preserving other node settings. It refuses if you edited any step text after the rewrite. A failed model session consumes that day's allowance without advancing affected steps' checked commits.

## Verification status

`inventory.json` + current MCP/API reads → `collect.py` → validated run snapshot + `refresh.json` → `build.py` → HTML → optional browser check / approved publishing. The assistant writes weekly summaries; Python does not generate them. Source failures remain visible.

The table below records formal host-loading acceptance separately from the install and runtime checks described above. Versioned host acceptance remains pending.

| Host | Verification / version |
|---|---|
| Claude Code plugin | Expected compatible; no host version verified. Manual loading check pending: reload/new session, then `/project-inventory:project-inventory`. |
| Codex standalone | File installation tested in clean, existing and reinstall homes; no host version verified. Manual loading check pending in a new session. |
| Hermes standalone | Same file installation checks; expected compatible, no host version verified. Manual loading check pending in a new session. |

| Path | Current support |
|---|---|
| Local Git, CSV/JSON/JSONL/SQLite, notes | Python collection and regression tests; no service connector required |
| Parquet / DuckDB | Optional DuckDB package; real-source regression coverage |
| GitHub / Linear | `gh` / API key or current MCP reads; authenticated services required |
| Notion | Assistant connector contract has offline mock coverage; real workspace acceptance pending |
| Host skill loading / Artifact publishing | Manual host/version acceptance pending |
| Page layout | Headless Chromium check at desktop/mobile sizes; optional browser dependency |

Full check: `python3 tests/release_gate.py`. GitHub CI runs the same command on pushes and PRs to main. [Trigger evals](evals/README.md) require Claude credentials; offline checks validate case configuration, not observed trigger rates. They measure skill invocation, not dashboard quality or setup behavior.

Development and reporting: [CONTRIBUTING.md](CONTRIBUTING.md). Changes: [CHANGELOG.md](CHANGELOG.md).

## Troubleshooting

| Symptom | What to check |
|---|---|
| Plugin command is missing | Reload plugins or start a new session; use `/project-inventory:project-inventory` for the plugin and `/project-inventory` for standalone |
| Notion, Linear or weekly summaries do not refresh in scripts | Notion needs the assistant connector; Linear needs it or `LINEAR_API_KEY`; summaries need an enabled text CLI or the next Claude run |
| A source fails / refresh exits 1 or 2 | Read the visible source errors and `refresh.json`; fix input/permissions and rerun. Never publish after exit 2. |
| Progress charts are empty | Configure tickets and/or local Git history; unknown or incomplete ticket dates are labelled |
| Vercel refuses an existing project | Use `--reuse` once only for the project you intend to use |
| Vercel credential refresh fails | Follow the login instruction; without `VERCEL_TOKEN`, `vercel whoami` must succeed before publishing |
| A screenshot capture fails | `WARN` retains the last image and retries next run; no project server or build is started |
| Undo refuses a diagram step | Step text was edited after the AI rewrite; the guard preserves your edits |

## Layout

```text
project-inventory/
├── .claude-plugin/
│   ├── plugin.json                 # plugin identity and version
│   └── marketplace.json            # Claude Code marketplace entry
├── .github/workflows/
│   ├── ci.yml                      # offline release gate
│   └── pages.yml                   # sample-only Pages demo
├── skills/project-inventory/
│   ├── SKILL.md                    # setup and refresh instructions
│   ├── scripts/                    # collect, build, capture, schedule, publish
│   └── reference/                  # schema, example config, demo and screenshots
├── evals/                          # trigger cases and instructions
├── tests/                          # regressions and release gate
├── README.md                       # English
├── README.zh-TW.md                  # Traditional Chinese
├── README.zh-CN.md                  # Simplified Chinese
├── 說明書.md                         # detailed Traditional Chinese manual
├── CONTRIBUTING.md
├── CHANGELOG.md
└── LICENSE
```

All inventory state defaults to `~/.project-inventory`: configuration in `inventory.json`, MCP reads in `gathered/<date>.json`, snapshots in `facts/<date>.json`, weekly summaries in `summaries.json`, captured images in `shots/`, and generated pages in `out/`.

## License

[MIT](LICENSE).
