# project-inventory

A Claude Code skill that takes stock of all your projects and builds one dashboard page.

For each project the page shows:

- **How it works**: a diagram of the project's steps, each with an icon. Claude drafts it from your code and you confirm it. A step can open to screenshots, formulas or a sketch of its input and output.
- **Tickets** from Linear and/or Notion: done, waiting for your review, open, canceled.
- **Facts**, in two tables. *Local*: checkouts (branch, uncommitted files), data files, Obsidian notes. *Cloud*: each checkout's GitHub remote and unpushed commits, open PRs, the Linear project, the Notion page.
- **Obsidian**: open note tasks (`- [ ]` lines).
- **Data freshness**: the newest date read from inside your data files (not file timestamps).
- **Progress**: commits per week and open/done tickets over the last 90 days (rebuilt from ticket dates, so they show on the first run). Below that, the whole history week by week: each week has a 2–3 sentence plain-words summary, and opens to every commit, finished ticket and new PR. Four weeks show at first; a button loads four more.

The home page lists everything that waits on you, across all projects.

中文說明書：[說明書.md](說明書.md)

## Install

```
/plugin marketplace add YuHsunWang/project-inventory
/plugin install project-inventory@project-inventory
```

### Other AI coding tools (Codex, Hermes, …)

No MCP server needed. The skill is a folder with `SKILL.md` (the steps) and `scripts/` (plain
Python), the same layout Codex and Hermes read skills from. Copy the folder in:

```
git clone https://github.com/YuHsunWang/project-inventory
cp -r project-inventory/skills/project-inventory ~/.codex/skills/     # Codex
cp -r project-inventory/skills/project-inventory ~/.hermes/skills/    # Hermes
```

Any other tool that can run shell commands: tell it to read `skills/project-inventory/SKILL.md`
and follow it. Claude-only parts: the claude.ai Artifact option and `/schedule`. Linear and
Notion need that tool's own connector (or `LINEAR_API_KEY` for Linear).

## Use

Say "inventory my projects" or run `/project-inventory`.

- **First run.** Claude asks which projects to include and where each one lives. It finds data files and asks which ones to watch, then drafts each diagram. Everything is saved to `~/.project-inventory/inventory.json`.
- **Later runs.** Claude re-reads every source and rebuilds the page. It also writes the summary for any week that has none yet, or got new work since its summary was written (usually just the current week). On the first run that means every past week, so the first run takes longer.

Week summaries are kept in `~/.project-inventory/summaries.json` and are not rewritten once a week is over.

## Requirements

| Needed for | What |
|---|---|
| everything | Python 3.9+, git |
| Linear tickets | a Linear MCP connector in Claude, or `LINEAR_API_KEY` in the environment (faster; scripts then read Linear without Claude) |
| Notion tickets | a Notion MCP connector in Claude |
| GitHub PRs | `gh` CLI logged in, or a GitHub MCP connector |
| parquet / duckdb data checks | `pip install duckdb` |
| page check | `pip install playwright && python3 -m playwright install chromium` (optional) |
| Vercel publishing | Vercel CLI logged in (`vercel login`) |

## Where the page goes

You choose. The default is a local file.

| Option | Who can see it |
|---|---|
| Local file `~/.project-inventory/out/index.html` | only you |
| claude.ai Artifact | only you (private) |
| Vercel | Vercel-authorized users; access depends on team/project membership, granted access, sharing and bypass settings ([access rules](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments/vercel-authentication)). Protection is switched on before the first deploy, and every deploy is checked from outside. |
| GitHub Pages | **everyone**. Claude asks before the first publish. |

## Scripts (usable without Claude)

The scripts are in `skills/project-inventory/scripts/`. To run them by hand, clone this repo
(the plugin install puts its copy in Claude's own plugin folder). Without Claude you write
`~/.project-inventory/inventory.json` yourself: start from
[example-inventory.json](skills/project-inventory/reference/example-inventory.json).

```
S=skills/project-inventory/scripts
python3 $S/collect.py ~/.project-inventory     # git, gh PRs, Obsidian tasks, data checks -> facts/<date>.json
python3 $S/build.py   ~/.project-inventory     # -> out/index.html
python3 $S/check_page.py ~/.project-inventory  # headless browser check, every tab and step, 390 + 1280 px
python3 $S/publish_vercel.py ~/.project-inventory <vercel-project-name>
```

Run without Claude, the scripts do not refresh Notion, or Linear unless `LINEAR_API_KEY` is set,
and they write no week summaries: new weeks show "no summary yet" until the next Claude run
(`build.py` lists them in `out/summaries-needed.json`).
Use `python3 collect.py HOME --refresh` for one refresh: it builds only that run's snapshot.
Exit 0 means success, 1 means partial collection (the page shows failed sources), and 2 means
fatal failure. `refresh.json` records the run and exact snapshot. Fatal failures retain the
last page's data/time with a visible failure summary; fix the input or permissions and rerun.
Do not publish after exit 2. Standalone build checks this manifest; legacy homes without one
can still be built. For cron, add `--script-only` to avoid consuming old MCP results:

```
# crontab: cron has almost no environment. Give it PATH (git, gh), and keep LINEAR_API_KEY in a
# file only you can read (chmod 600) rather than in the crontab line.
0 7 * * * PATH=/usr/local/bin:/usr/bin:/bin sh -c '. ~/.project-inventory/env; cd ~/project-inventory/skills/project-inventory/scripts; python3 collect.py ~/.project-inventory --refresh --script-only'
```

`~/.project-inventory/env` holds one line, `export LINEAR_API_KEY=lin_api_...` (leave it empty if
you do not use the key).

`publish_vercel.py` will not overwrite a Vercel project it did not create. To use one you already
have, pass `--reuse` once.

File formats: [skills/project-inventory/reference/schema.md](skills/project-inventory/reference/schema.md).
