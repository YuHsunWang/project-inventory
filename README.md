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
| Linear tickets | a Linear MCP connector in Claude |
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

```
python3 scripts/collect.py ~/.project-inventory     # git, gh PRs, Obsidian tasks, data checks -> facts/<date>.json
python3 scripts/build.py   ~/.project-inventory     # -> out/index.html
python3 scripts/check_page.py ~/.project-inventory  # headless browser check, every tab and step, 390 + 1280 px
python3 scripts/publish_vercel.py ~/.project-inventory <vercel-project-name>
```

Run without Claude, the scripts do not refresh Linear or Notion. The page then says those sources were not read.

File formats: [skills/project-inventory/reference/schema.md](skills/project-inventory/reference/schema.md).
