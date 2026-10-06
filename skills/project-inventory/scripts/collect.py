"""Gather the facts scripts can get without Claude, merge what Claude gathered, save one snapshot.

    python3 collect.py <home>        # <home> holds inventory.json (default ~/.project-inventory)

Reads   <home>/inventory.json               projects and their sources
        <home>/gathered/<today>.json        tickets/PRs Claude fetched through MCP (optional)
Writes  <home>/facts/<today>.json           one snapshot; build.py reads every snapshot for trends

Script-side sources: local git checkouts, GitHub PRs via `gh`, Obsidian task lines, data freshness,
and Linear when $LINEAR_API_KEY is set (then Claude does not need to gather Linear).
Nothing here needs a package outside the standard library except parquet/duckdb checks (duckdb).
Exit 1 when any source failed; the failure is also written into the snapshot, so the page shows it.
Use --refresh to collect and build one run. Exit 2 means fatal input/write failure; refresh.json
blocks stale rebuilds and the last page retains its data/time with a failure banner.
"""
import argparse, csv, datetime as dt, json, os, re, shutil, sqlite3, subprocess, sys, uuid, urllib.error, urllib.request
from pathlib import Path
from validation import validate_inventory, validate_gathered, validate_snapshot, normalize_date, calendar_date, date_order, timezone

RECENT_DAYS, WEEKS, HISTORY = 14, 12, 3000  # HISTORY: newest commits kept per checkout for the progress tab
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
        except Exception as e:  # retain local facts, but the remote comparison is unavailable
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
    if fetch_error:
        ahead = behind = None
    log = g("log", "--all", "--format=%H%x09%cs%x09%s")
    commits = [dict(zip(("hash", "date", "subject"), l.split("\t", 2))) for l in log.splitlines() if l]
    recent_since = (today - dt.timedelta(days=RECENT_DAYS)).isoformat()
    return {
        "branch": branch, "upstream": upstream, "has_origin": has_origin, "fetch_error": fetch_error,
        "remote": clean_url(g("remote", "get-url", "origin")) if has_origin else None,
        "ahead": ahead, "behind": behind,
        "dirty": len([l for l in g("status", "--porcelain").splitlines() if l]),
        "last_commit": g("log", "-1", "--format=%cs %s") if g("rev-list", "-n1", "--all") else None,
        "weekly": weekly([c["date"] for c in commits], today),
        "recent": [c for c in commits if c["date"] >= recent_since][:40],
        "_recent_hashes": [c["hash"] for c in commits if c["date"] >= recent_since],
        "_commits": commits[:HISTORY],  # display history stays bounded; aggregate is computed before truncation
    }


def clean_url(u):
    """origin as a browser link, without any user:token@ in it."""
    u = re.sub(r"^git@([^:]+):", r"https://\1/", u.strip())
    return re.sub(r"^(\w+://)[^/@]+@", r"\1", u).removesuffix(".git")


def weekly(dates, today):
    monday = today - dt.timedelta(days=today.weekday())
    starts = [monday - dt.timedelta(weeks=w) for w in range(WEEKS - 1, -1, -1)]
    ds = [dt.date.fromisoformat(d) for d in dates]
    return [{"week": s.isoformat(), "n": sum(s <= d < s + dt.timedelta(days=7) for d in ds)} for s in starts]


GH_PRS_Q = """query($owner:String!, $repo:String!, $after:String){
  repository(owner:$owner, name:$repo){ pullRequests(first:50, after:$after, states:OPEN){
    nodes{ number title url createdAt isDraft headRefName }
    pageInfo{ hasNextPage endCursor } } } }"""


def gh_prs(repo):
    owner, name = repo.split("/", 1)
    prs, after = [], None
    while True:
        cmd = ["gh", "api", "graphql", "-f", f"query={GH_PRS_Q}",
               "-f", f"owner={owner}", "-f", f"repo={name}"]
        if after:
            cmd += ["-f", f"after={after}"]
        try:
            res = json.loads(run(cmd))
            if res.get("errors"):
                raise RuntimeError(res["errors"][0].get("message"))
            page = res["data"]["repository"]["pullRequests"]
        except Exception as e:
            raise RuntimeError(f"PR page {len(prs) // 50 + 1}: {e}") from e
        prs += [{**p, "repo": repo} for p in page["nodes"]]
        if not page["pageInfo"]["hasNextPage"]:
            return prs
        cursor = page["pageInfo"]["endCursor"]
        if not cursor or cursor == after:
            raise RuntimeError("PR pagination did not advance")
        after = cursor


LINEAR_PROJECT_Q = """query($id:String!){ project(id:$id){ id name archivedAt } }"""
LINEAR_NAME_Q = """query($name:String!){
  projects(first:2, includeArchived:true, filter:{name:{eq:$name}}){ nodes{ id name archivedAt } } }"""
LINEAR_Q = """query($id:ID!, $after:String){
  issues(first:100, after:$after, includeArchived:true, filter:{project:{id:{eq:$id}}}){
    nodes{ id identifier title url createdAt completedAt canceledAt state{ name type } }
    pageInfo{ hasNextPage endCursor } } }"""


def linear_query(query, variables):
    req = urllib.request.Request("https://api.linear.app/graphql",
                                 data=json.dumps({"query": query, "variables": variables}).encode(),
                                 headers={"Authorization": os.environ["LINEAR_API_KEY"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Linear HTTP {e.code}") from e
    if res.get("errors"):
        raise RuntimeError(res["errors"][0].get("message"))
    if not res.get("data"):
        raise RuntimeError("Linear returned no accessible data")
    return res["data"]


def linear_tickets(project):
    """Read one stable project ID; legacy names must resolve to exactly one accessible project."""
    spec = {"project": project} if isinstance(project, str) else project
    project_id = spec.get("project_id")
    if project_id:
        found = linear_query(LINEAR_PROJECT_Q, {"id": project_id}).get("project")
        if not found or found["id"] != project_id:
            raise RuntimeError(f"Linear project ID {project_id!r} not found or inaccessible (check permissions)")
    else:
        name = spec.get("project")
        if not name:
            raise RuntimeError("set sources.linear.project_id to the confirmed Linear project UUID")
        projects = linear_query(LINEAR_NAME_Q, {"name": name})["projects"]["nodes"]
        if not projects:
            raise RuntimeError(f"no Linear project named {name!r} (renamed or inaccessible); set sources.linear.project_id to its confirmed UUID")
        if len(projects) != 1:
            ids = ", ".join(p["id"] for p in projects)
            raise RuntimeError(f"ambiguous Linear project name {name!r}; choose a project and set sources.linear.project_id (candidates: {ids})")
        project_id = projects[0]["id"]
    out, after = [], None
    while True:
        page = linear_query(LINEAR_Q, {"id": project_id, "after": after})["issues"]
        for i in page["nodes"]:
            st = i["state"]
            state = {"completed": "done", "canceled": "dead"}.get(st["type"]) or ("wait" if "review" in st["name"].lower() else "open")
            out.append({"id": i["identifier"], "source_id": i.get("id", i["identifier"]), "title": i["title"], "state": state, "url": i["url"], "source": "linear",
                        "created": i["createdAt"], "completed": i["completedAt"] or None,
                        "canceled": i["canceledAt"] or None})
        if not page["pageInfo"]["hasNextPage"]:
            return out
        cursor = page["pageInfo"]["endCursor"]
        if not cursor or cursor == after:
            raise RuntimeError("Linear pagination did not advance")
        after = cursor


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


def sql_identifier(name):
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"invalid SQL identifier {name!r}")
    return '"' + name.replace('"', '""') + '"'


def database_newest(con, src, col):
    """Validate against result metadata before MAX: SQLite can treat unknown quotes as text."""
    try:
        columns = [c[0] for c in con.execute(f"SELECT * FROM {src} LIMIT 0").description]
    except Exception as e:
        raise RuntimeError(f"table/source {src} not found or unreadable: {e}") from e
    # Use the actual metadata spelling after a case-insensitive match, then quote it safely.
    actual = next((c for c in columns if c.lower() == col.lower()), None) if isinstance(col, str) else None
    if actual is None:
        raise RuntimeError(f"column {col!r} not found in {src} (columns: {', '.join(columns[:8])})")
    values = [r[0] for r in con.execute(f"SELECT {sql_identifier(actual)} FROM {src}")]
    if not values:
        raise RuntimeError(f"empty table/source {src}: no values in column {col!r}")
    return [str(value) for value in values if value is not None]


def newest_date(spec, zone="UTC"):
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
        try:
            vals = database_newest(con, sql_identifier(spec["table"]), col)
        finally:
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
            src, con = sql_identifier(spec["table"]), duckdb.connect(str(path), read_only=True)
        try:
            vals = database_newest(con, src, col)
        finally:
            con.close()
    else:
        raise RuntimeError(f"unknown kind {kind!r} (csv, jsonl, json, sqlite, parquet, duckdb)")
    vals = [v for v in vals if v and v != "None"]
    if not vals:
        raise RuntimeError(f"no values in column {col!r}")
    try:
        newest = max(vals, key=lambda value: date_order(value, zone, f"{path}:{col}"))
        return normalize_date(newest, zone, f"{path}:{col}").isoformat()
    except ValueError as e:
        raise RuntimeError(str(e)) from e


def data_check(spec, today, zone="UTC"):
    newest = newest_date(spec, zone)
    age = (today - calendar_date(newest, zone)).days
    if age < 0:
        raise RuntimeError(f"{spec['path']}:{spec.get('column')}: future date {newest}; allowed through {today} in {zone}")
    limit = spec.get("max_age_days", 1)
    return {"label": spec.get("label", spec["path"]), "path": spec["path"], "newest": newest,
            "age_days": age, "max_age_days": limit, "stale": age > limit}


def source_state(run_id, attempted_at, fetched_at=None, status="unavailable", complete=False, error=None):
    return dict(run_id=run_id, attempted_at=attempted_at, fetched_at=fetched_at,
                status=status, complete=complete, error=error)


def gathered_state(g, name, run_id, attempted_at, previous=None):
    m = g.get("sources", {}).get(name, {})
    previous = previous or {}
    error = m.get("error") or next((e for e in g.get("errors", []) if e.startswith(name.split(":")[0] + ":")), None)
    fresh = (m.get("run_id") == run_id and m.get("fetched_at") and
             m.get("status") == "ok" and m.get("complete") is True and not error)
    fetched = m.get("fetched_at") or previous.get("fetched_at")
    status = "ok" if fresh else ("partial" if m.get("status") == "partial" else "failed") if error else "stale" if fetched or name in g.get("read", []) else "unavailable"
    return source_state(run_id, m.get("attempted_at") if m.get("run_id") == run_id else attempted_at,
                        fetched, status, bool(fresh), error or (None if fresh else "not gathered today for this run; gather the source again"))


def collect_snapshot(home, requested_run=None, script_only=False):
    inv = validate_inventory(json.loads((home / "inventory.json").read_text(encoding="utf-8")))
    zone = inv.get("timezone", "UTC")
    today = dt.datetime.now(timezone(zone)).date()
    gathered_f = home / "gathered" / f"{today}.json"
    gathered = validate_gathered(json.loads(gathered_f.read_text(encoding="utf-8")) if gathered_f.exists() else {}, inv, str(gathered_f))
    previous_files = sorted(x for x in (home / "facts").glob("*.json") if x.stem <= today.isoformat())
    previous = json.loads(previous_files[-1].read_text(encoding="utf-8")) if previous_files else {}
    offered = gathered.get("_run", {}).get("run_id")
    consumed = previous.get("gathered_run_id", previous.get("run_id"))
    run_id = offered if offered and offered != consumed else uuid.uuid4().hex
    if requested_run:
        run_id = requested_run if requested_run != consumed else uuid.uuid4().hex
    if script_only:
        run_id = uuid.uuid4().hex
    attempted_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    have_gh = shutil.which("gh") is not None
    # a gathered file under another date usually means Claude's date and this computer's date differ
    others = sorted(x.name for x in (home / "gathered").glob("*.json") if x != gathered_f) if not gathered_f.exists() else []
    other = f"; newest gathered file is {others[-1]}, this computer's date is {today}" if others else ""
    snap = {"date": today.isoformat(), "generated_at": dt.datetime.now(timezone(zone)).isoformat(timespec="seconds"),
            "gathered": gathered_f.exists(), "run_id": run_id, "gathered_run_id": offered, "projects": {}}
    failed = 0
    for p in inv["projects"]:
        src, g = p.get("sources", {}), gathered.get(p["key"], {})
        old = previous.get("projects", {}).get(p["key"], {}).get("sources", {})
        f = {"errors": list(g.get("errors", [])), "tickets": [], "stale_tickets": [],
             "sources": {}, "repos": [], "prs": [], "obsidian": [], "data": []}
        commits, recent_hashes = {}, set()
        for name in ("linear", "notion"):
            if not src.get(name):
                continue
            state = gathered_state(g, name, run_id, attempted_at, old.get(name))
            tickets = [t for t in g.get("tickets", []) if t.get("source") == name]
            if name == "linear" and os.environ.get("LINEAR_API_KEY"):
                try:
                    tickets = linear_tickets(src[name])
                    state = source_state(run_id, attempted_at, dt.datetime.now().astimezone().isoformat(timespec="seconds"), "ok", True)
                    f["errors"] = [e for e in f["errors"] if not e.startswith("linear:")]
                except Exception as e:
                    state = source_state(run_id, attempted_at, state["fetched_at"], "failed", False, str(e))
            f["sources"][name] = state
            f["tickets" if state["status"] == "ok" else "stale_tickets"] += tickets
            if state["status"] != "ok":
                f["errors"].append(f"{name}: {state['error']}{other}")
        for r in src.get("local", []):
            try:
                st = git_state(Path(r["path"]).expanduser(), today)
                # A full SHA is one event per project, even across worktrees, clones or forks.
                recent_hashes.update(st.pop("_recent_hashes"))
                for c in st.pop("_commits"):
                    commits.setdefault(c["hash"], {**c, "where": r["label"]})
                name = f"git:{r['path']}"
                last_fetch = old.get(name, {}).get("fetched_at")
                if st["has_origin"] and not st["fetch_error"]:
                    last_fetch = dt.datetime.now().astimezone().isoformat(timespec="seconds")
                f["sources"][name] = source_state(run_id, attempted_at, last_fetch,
                    "partial" if st["fetch_error"] else "ok", not bool(st["fetch_error"]), st["fetch_error"])
                if st["fetch_error"]:
                    f["errors"].append(f"git {r['path']}: remote refresh failed: {st['fetch_error']}")
                f["repos"].append({"label": r["label"], "path": r["path"], "last_fetched_at": last_fetch, **st})
            except Exception as e:
                f["errors"].append(f'git {r["path"]}: {e}')
        f["commit_count_14"] = len(recent_hashes)
        f["weekly"] = weekly([c["date"] for c in commits.values()], today)
        f["commits"] = sorted(commits.values(), key=lambda c: c["date"], reverse=True)
        for repo in src.get("github", []):
            name = f"github:{repo}"
            state = gathered_state(g, name, run_id, attempted_at, old.get(name))
            prs = [pr for pr in g.get("prs", []) if pr.get("repo") == repo]
            if state["status"] != "ok" and have_gh:
                try:
                    prs = gh_prs(repo)
                    state = source_state(run_id, attempted_at, dt.datetime.now().astimezone().isoformat(timespec="seconds"), "ok", True)
                except Exception as e:
                    state = source_state(run_id, attempted_at, state["fetched_at"], "failed", False, str(e))
            f["sources"][name] = state
            if state["status"] == "ok":
                f["prs"] += prs
            else:
                f["errors"].append(f"{name}: {state['error']}; install gh or gather PRs again")
        for o in src.get("obsidian", []):
            try:
                f["obsidian"].append(obsidian_tasks(o["path"]))
            except Exception as e:
                f["errors"].append(f'obsidian {o["path"]}: {e}')
        for d in p.get("data", []):
            try:
                f["data"].append(data_check(d, today, zone))
            except Exception as e:
                f["errors"].append(f'data {d.get("label", d["path"])}: {e}')
                f["data"].append({"label": d.get("label", d["path"]), "path": d["path"], "error": str(e)})
        failed += len(f["errors"])
        snap["projects"][p["key"]] = f
    validate_snapshot(snap, inv)
    out = home / "facts" / f"{today}.json"
    atomic_write(out, json.dumps(snap, ensure_ascii=False, indent=1))
    for k, f in snap["projects"].items():
        print(f'{k}: {len(f["repos"])} repos, {len(f["prs"])} PRs, {len(f["tickets"])} tickets, '
              f'{sum(o["open"] for o in f["obsidian"])} open notes tasks, {len(f["data"])} data, {len(f["errors"])} errors')
        for e in f["errors"]:
            print(f"  ERROR {e}")
    print(f"wrote {out}")
    return (1 if failed else 0), out, run_id


def atomic_write(path, text):
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".pending-", delete=False) as f:
            pending = Path(f.name)
            f.write(text)
        pending.replace(path)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("home", nargs="?", default="~/.project-inventory")
    parser.add_argument("--run-id", help="MCP gather run to consume")
    parser.add_argument("--refresh", action="store_true", help="collect and build only this run's snapshot")
    parser.add_argument("--script-only", action="store_true", help="cron: refresh APIs without consuming MCP results")
    args = parser.parse_args()
    home = Path(args.home).expanduser()
    manifest_f = home / "refresh.json"
    manifest = {"run_id": args.run_id or uuid.uuid4().hex,
                "attempted_at": dt.datetime.now().astimezone().isoformat(),
                "status": "running", "snapshot": None, "error": None}
    try:
        atomic_write(manifest_f, json.dumps(manifest))
        code, out, rid = collect_snapshot(home, args.run_id, args.script_only)
        manifest.update(run_id=rid, status="partial" if code else "ok", snapshot=str(out.resolve()))
        atomic_write(manifest_f, json.dumps(manifest))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        message = f"FAILED: collection could not complete: {e}. Fix the input or directory permissions and rerun collect.py HOME --refresh."
        manifest.update(status="fatal", error=message)
        try:
            atomic_write(manifest_f, json.dumps(manifest))
        except OSError as record_error:
            print(f"FAILED: cannot record refresh failure: {record_error}; no build was attempted", file=sys.stderr)
        # Preserve the last page's data and time, but mark this failed attempt visibly.
        import build
        build.mark_failed_page(home, manifest)
        print(message, file=sys.stderr)
        sys.exit(2)
    if args.refresh:
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("build.py")), str(home),
                                 "--snapshot", str(out), "--run-id", rid])
        if result.returncode:
            sys.exit(2)
    sys.exit(code)


if __name__ == "__main__":
    main()
