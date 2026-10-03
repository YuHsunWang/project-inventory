"""Gather the facts scripts can get without Claude, merge what Claude gathered, save one snapshot.

    python3 collect.py <home>        # <home> holds inventory.json (default ~/.project-inventory)

Reads   <home>/inventory.json               projects and their sources
        <home>/gathered/<today>.json        tickets/PRs Claude fetched through MCP (optional)
Writes  <home>/facts/<today>.json           one snapshot; build.py reads every snapshot for trends

Script-side sources: local git checkouts, GitHub PRs via `gh`, Obsidian task lines, data freshness,
and Linear when $LINEAR_API_KEY is set (then Claude does not need to gather Linear).
Nothing here needs a package outside the standard library except parquet/duckdb checks (duckdb).
Exit 1 when any source failed; the failure is also written into the snapshot, so the page shows it.
"""
import csv, datetime as dt, json, os, re, shutil, sqlite3, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

RECENT_DAYS, WEEKS = 14, 12
TASK = re.compile(r"^\s*[-*]\s+\[( |x|X)\]\s+(.*)$")


# never stop to ask for a password: fail instead (cron has no one to answer). An ssh passphrase
# prompt is left alone (overriding the ssh command would drop the user's core.sshCommand); the
# 60 s timeout ends it.
GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def run(cmd, cwd=None, timeout=60):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=GIT_ENV)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else f"exit {r.returncode}")
    return r.stdout


def git_state(path, today):
    g = lambda *a: run(["git", *a], cwd=path).strip()
    has_origin = "origin" in g("remote").split()
    fetch_error = None
    if has_origin:
        try:
            run(["git", "fetch", "-q", "origin"], cwd=path, timeout=60)
        except Exception as e:  # offline is not fatal; ahead/behind is then against the last fetch
            fetch_error = str(e)
    branch = g("branch", "--show-current") or "(detached)"
    upstream = None
    ahead = behind = None
    if has_origin:
        try:
            upstream = g("rev-parse", "--abbrev-ref", "@{upstream}")
            behind, ahead = map(int, g("rev-list", "--left-right", "--count", f"{upstream}...HEAD").split())
        except Exception:
            upstream = None
    since = (today - dt.timedelta(weeks=WEEKS)).isoformat()
    log = g("log", "--all", f"--since={since}", "--format=%h%x09%cs%x09%s")
    commits = [dict(zip(("hash", "date", "subject"), l.split("\t", 2))) for l in log.splitlines() if l]
    recent_since = (today - dt.timedelta(days=RECENT_DAYS)).isoformat()
    return {
        "branch": branch, "upstream": upstream, "has_origin": has_origin, "fetch_error": fetch_error,
        "ahead": ahead, "behind": behind,
        "dirty": len([l for l in g("status", "--porcelain").splitlines() if l]),
        "last_commit": g("log", "-1", "--format=%cs %s") if g("rev-list", "-n1", "--all") else None,
        "weekly": weekly([c["date"] for c in commits], today),
        "recent": [c for c in commits if c["date"] >= recent_since][:40],
        "_commits": commits,  # popped by main: the project's weekly counts, deduped across checkouts
    }


def weekly(dates, today):
    monday = today - dt.timedelta(days=today.weekday())
    starts = [monday - dt.timedelta(weeks=w) for w in range(WEEKS - 1, -1, -1)]
    ds = [dt.date.fromisoformat(d) for d in dates]
    return [{"week": s.isoformat(), "n": sum(s <= d < s + dt.timedelta(days=7) for d in ds)} for s in starts]


def gh_prs(repo):
    out = run(["gh", "pr", "list", "-R", repo, "--state", "open", "--limit", "50",
               "--json", "number,title,url,createdAt,isDraft,headRefName"])
    return [{**p, "repo": repo} for p in json.loads(out)]


LINEAR_Q = """query($name:String!, $after:String){
  projects(filter:{name:{eq:$name}}){ nodes{ id } }
  issues(first:100, after:$after, includeArchived:true, filter:{project:{name:{eq:$name}}}){
    nodes{ identifier title url createdAt completedAt canceledAt state{ name type } }
    pageInfo{ hasNextPage endCursor } } }"""


def linear_tickets(project):
    """Issues of one Linear project, straight from the API ($LINEAR_API_KEY), no Claude needed."""
    out, after = [], None
    while True:
        req = urllib.request.Request("https://api.linear.app/graphql",
                                     data=json.dumps({"query": LINEAR_Q, "variables": {"name": project, "after": after}}).encode(),
                                     headers={"Authorization": os.environ["LINEAR_API_KEY"], "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                res = json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}")
        if res.get("errors"):
            raise RuntimeError(res["errors"][0].get("message"))
        if not res["data"]["projects"]["nodes"]:
            raise RuntimeError(f"no Linear project named {project!r} (check the exact name)")
        page = res["data"]["issues"]
        for i in page["nodes"]:
            st = i["state"]
            state = {"completed": "done", "canceled": "dead"}.get(st["type"]) or ("wait" if "review" in st["name"].lower() else "open")
            out.append({"id": i["identifier"], "title": i["title"], "state": state, "url": i["url"], "source": "linear",
                        "created": i["createdAt"][:10], "completed": (i["completedAt"] or "")[:10] or None,
                        "canceled": (i["canceledAt"] or "")[:10] or None})
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def obsidian_tasks(folder):
    """Markdown task lines `- [ ]` / `- [x]` under a vault folder (skips .obsidian and .trash)."""
    open_, done = [], 0
    root = Path(folder).expanduser()
    if not root.is_dir():
        raise RuntimeError(f"folder not found: {root}")
    for f in sorted(root.rglob("*.md")):
        if any(part in (".obsidian", ".trash") for part in f.parts):
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = TASK.match(line)
            if m and m.group(1) == " ":
                open_.append({"text": m.group(2).strip()[:160], "file": str(f.relative_to(root))})
            elif m:
                done += 1
    return {"path": str(root), "open": len(open_), "done": done, "items": open_[:50]}


def newest_date(spec):
    """Largest value of the date column/field, read from the data itself (never file mtimes)."""
    path, kind, col = Path(spec["path"]).expanduser(), spec["kind"], spec.get("column")
    if kind == "csv":
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            vals = [r[col] for r in csv.DictReader(f) if r.get(col)]
    elif kind == "jsonl":
        vals = []
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip():
                    v = json.loads(line).get(col)
                    if v: vals.append(str(v))
    elif kind == "json":  # a single field, dotted path, e.g. "meta.generated_at"
        v = json.loads(path.read_text(encoding="utf-8"))
        for k in col.split("."):
            if not isinstance(v, dict) or k not in v:
                raise RuntimeError(f"field {col!r} not found (top-level keys: {', '.join(list(v)[:8]) if isinstance(v, dict) else type(v).__name__})")
            v = v[k]
        vals = [str(v)]
    elif kind == "sqlite":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        vals = [str(con.execute(f'SELECT MAX("{col}") FROM "{spec["table"]}"').fetchone()[0])]
        con.close()
    elif kind in ("parquet", "duckdb"):
        import duckdb  # only needed for these two kinds
        if kind == "parquet":
            # a folder: skip files/dirs starting with _ or . (staging/temp files, the Hive/Spark convention)
            files = [str(x) for x in sorted(path.rglob("*.parquet"))
                     if not any(part.startswith(("_", ".")) for part in x.relative_to(path).parts)] if path.is_dir() else [str(path)]
            if not files:
                raise RuntimeError("no .parquet files")
            src = f"read_parquet({files!r}, hive_partitioning=true, union_by_name=true)"
            con = duckdb.connect()
        else:
            src, con = f'"{spec["table"]}"', duckdb.connect(str(path), read_only=True)
        vals = [str(con.execute(f'SELECT MAX("{col}") FROM {src}').fetchone()[0])]
        con.close()
    else:
        raise RuntimeError(f"unknown kind {kind!r} (csv, jsonl, json, sqlite, parquet, duckdb)")
    vals = [v for v in vals if v and v != "None"]
    if not vals:
        raise RuntimeError(f"no values in column {col!r}")
    return max(vals)[:19]


def data_check(spec, today):
    newest = newest_date(spec)
    age = (today - dt.date.fromisoformat(newest[:10])).days
    limit = spec.get("max_age_days", 1)
    return {"label": spec.get("label", spec["path"]), "path": spec["path"], "newest": newest,
            "age_days": age, "max_age_days": limit, "stale": age > limit}


def main():
    home = Path(sys.argv[1] if len(sys.argv) > 1 else "~/.project-inventory").expanduser()
    inv = json.loads((home / "inventory.json").read_text(encoding="utf-8"))
    today = dt.date.today()
    gathered_f = home / "gathered" / f"{today}.json"
    gathered = json.loads(gathered_f.read_text(encoding="utf-8")) if gathered_f.exists() else {}
    have_gh = shutil.which("gh") is not None
    # a gathered file under another date usually means Claude's date and this computer's date differ
    others = sorted(x.name for x in (home / "gathered").glob("*.json") if x != gathered_f) if not gathered_f.exists() else []
    other = f"; newest gathered file is {others[-1]}, this computer's date is {today}" if others else ""
    snap = {"date": today.isoformat(), "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "gathered": gathered_f.exists(), "projects": {}}
    failed = 0
    for p in inv["projects"]:
        src, g = p.get("sources", {}), gathered.get(p["key"], {})
        f = {"errors": list(g.get("errors", [])), "tickets": g.get("tickets", []),
             "repos": [], "prs": [], "obsidian": [], "data": []}
        commits = {}
        if src.get("linear") and os.environ.get("LINEAR_API_KEY") and "linear" not in g.get("read", []):
            try:
                f["tickets"] = [t for t in f["tickets"] if t.get("source") != "linear"] + linear_tickets(src["linear"]["project"])
                g = {**g, "read": [*g.get("read", []), "linear"]}
            except Exception as e:
                f["errors"].append(f"linear: {e}")
        for r in src.get("local", []):
            try:
                st = git_state(Path(r["path"]).expanduser(), today)
                commits.update((c["hash"], c["date"]) for c in st.pop("_commits"))
                f["repos"].append({"label": r["label"], "path": r["path"], **st})
            except Exception as e:
                f["errors"].append(f'git {r["path"]}: {e}')
        f["weekly"] = weekly(list(commits.values()), today)
        if "prs" in g:  # Claude fetched PRs through the GitHub MCP (no gh here)
            f["prs"] = g["prs"]
        elif src.get("github"):
            if not have_gh:
                f["errors"].append("gh CLI not installed: open PRs not read")
            for repo in src["github"] if have_gh else []:
                try:
                    f["prs"] += gh_prs(repo)
                except Exception as e:
                    f["errors"].append(f"gh {repo}: {e}")
        for o in src.get("obsidian", []):
            try:
                f["obsidian"].append(obsidian_tasks(o["path"]))
            except Exception as e:
                f["errors"].append(f'obsidian {o["path"]}: {e}')
        for d in p.get("data", []):
            try:
                f["data"].append(data_check(d, today))
            except Exception as e:
                f["errors"].append(f'data {d.get("label", d["path"])}: {e}')
                f["data"].append({"label": d.get("label", d["path"]), "path": d["path"], "error": str(e)})
        for name in ("linear", "notion"):  # Claude lists what it read in "read"; a silent gap is an error
            if src.get(name) and name not in g.get("read", []) and not any(e.startswith(name) for e in f["errors"]):
                f["errors"].append(f"{name}: not gathered today (gathered/{today}.json does not list it in \"read\"){other}")
        failed += len(f["errors"])
        snap["projects"][p["key"]] = f
    out = home / "facts" / f"{today}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, f in snap["projects"].items():
        print(f'{k}: {len(f["repos"])} repos, {len(f["prs"])} PRs, {len(f["tickets"])} tickets, '
              f'{sum(o["open"] for o in f["obsidian"])} open notes tasks, {len(f["data"])} data, {len(f["errors"])} errors')
        for e in f["errors"]:
            print(f"  ERROR {e}")
    print(f"wrote {out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
