# project-inventory

A Claude Code skill that takes stock of all your projects and builds one dashboard page.

For each project the page shows:

- **How it works**: a diagram of the project's steps. Claude drafts it from your code and you confirm it.
- **Tickets** from Linear and/or Notion: done, waiting for your review, open, canceled.
- **GitHub**: open PRs.
- **Local git**: branch, uncommitted files, unpushed commits.
- **Obsidian**: open note tasks (`- [ ]` lines).
- **Data freshness**: the newest date read from inside your data files (not file timestamps).
- **Activity and trends**: commits per week, recent work, open tickets over time.

The home page lists everything that waits on you, across all projects.

中文說明書：[說明書.md](說明書.md)

## Install

```
/plugin marketplace add YuHsunWang/project-inventory
/plugin install project-inventory@project-inventory
```

## Use

Say "inventory my projects" or run `/project-inventory`.

- **First run.** Claude asks which projects to include and where each one lives. It finds data files and asks which ones to watch, then drafts each diagram. Everything is saved to `~/.project-inventory/inventory.json`.
- **Later runs.** Claude re-reads every source and rebuilds the page.

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
| Vercel | only your logged-in Vercel account. Protection is switched on before the first deploy, and every deploy is checked from outside. |
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

Run without Claude, the scripts do not refresh Notion, or Linear unless `LINEAR_API_KEY` is set.
The page then says those sources were not read, and `collect.py` exits 1. So chain the two with
`;`, not `&&` — with `&&` the page would never be rebuilt:

```
# crontab: cron has almost no environment. Give it PATH (git, gh), and keep LINEAR_API_KEY in a
# file only you can read (chmod 600) rather than in the crontab line.
0 7 * * * PATH=/usr/local/bin:/usr/bin:/bin sh -c '. ~/.project-inventory/env; cd ~/project-inventory/skills/project-inventory/scripts; python3 collect.py ~/.project-inventory; python3 build.py ~/.project-inventory'
```

`~/.project-inventory/env` holds one line, `export LINEAR_API_KEY=lin_api_...` (leave it empty if
you do not use the key).

`publish_vercel.py` will not overwrite a Vercel project it did not create. To use one you already
have, pass `--reuse` once.

File formats: [skills/project-inventory/reference/schema.md](skills/project-inventory/reference/schema.md).
