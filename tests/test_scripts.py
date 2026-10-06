"""Checks for the script fixes. Stdlib only; no network, no Vercel, no Linear.

    python3 tests/test_scripts.py
"""
import base64, struct, zlib, io, json, subprocess, urllib.error, sys, tempfile, types, urllib.request
from pathlib import Path

S = Path(__file__).resolve().parent.parent / "skills/project-inventory/scripts"
sys.path.insert(0, str(S))
import collect, publish_vercel as pv

tmp = Path(tempfile.mkdtemp())
git = lambda cwd, *a: subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=a", *a], cwd=cwd, check=True, capture_output=True)


def run(script, *args):
    return subprocess.run([sys.executable, str(S / script), *args], capture_output=True, text=True)


# --- collect + build: one repo checked out twice (a worktree) and one other repo -----------------
a, b = tmp / "a", tmp / "b"
for r in (a, b):
    r.mkdir(); git(r, "init", "-q"); git(r, "commit", "-q", "--allow-empty", "-m", f"c1 {r.name}")
git(a, "commit", "-q", "--allow-empty", "-m", "c2")
git(a, "worktree", "add", "-q", str(tmp / "a-wt"))
home = tmp / "home"; (home / "gathered").mkdir(parents=True)
(home / "gathered" / "2000-01-01.json").write_text("{}")
(home / "inventory.json").write_text(json.dumps({"title": "A&B <i>x</i>", "projects": [{
    "key": "p", "name": "P", "color": "#c00",
    "sources": {"notion": {"url": "x"}, "local": [{"label": "a", "path": str(a)}, {"label": "a-wt", "path": str(tmp / "a-wt")},
                                                  {"label": "b", "path": str(b)}]}}]}))
r = run("collect.py", str(home))
# Notion not gathered -> partial exit 1; build remains allowed, with a hint naming the other date
assert r.returncode == 1, r.stdout + r.stderr
assert "newest gathered file is 2000-01-01.json" in r.stdout, r.stdout
facts = json.loads(next((home / "facts").glob("*.json")).read_text())["projects"]["p"]
# 3 distinct commits: a's two are seen from both checkouts but count once; b's one adds to them
assert sum(w["n"] for w in facts["weekly"]) == 3, facts["weekly"]
r = run("build.py", str(home))
assert r.returncode == 0, r.stderr
page = (home / "out/index.html").read_text()
assert "<title>A&amp;B &lt;i&gt;x&lt;/i&gt;</title>" in page, "title must be HTML-escaped"
assert "libs/mathjax" not in page, "no formula on the page -> MathJax is not loaded"

# --- build: a step's screenshot is embedded, a missing one is shown and warned, a formula loads MathJax
def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

PNG = (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
       + png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff")) + png_chunk(b"IEND", b""))
shot = tmp / "s.png"; shot.write_bytes(PNG)
inv = json.loads((home / "inventory.json").read_text())
inv["projects"][0]["nodes"] = [{"id": 1, "title": "x", "icon": "gear", "media": [
    {"shot": str(shot), "caption": "ok"}, {"shot": "nope.png", "caption": "gone"}, {"math": ["a+b"]}]}]
(home / "inventory.json").write_text(json.dumps(inv))
r = run("build.py", str(home))
assert r.returncode == 0 and "WARN p: step 1: screenshot not found" in r.stdout, r.stdout + r.stderr
page = (home / "out/index.html").read_text()
assert "data:image/png;base64," in page and str(shot) not in page, "screenshot must be inside the page, not linked"
assert '"missing":' in page, "a missing screenshot is shown as missing, not dropped"
assert "cdnjs.cloudflare.com/ajax/libs/mathjax" in page

# --- security #4: exercise the actual JavaScript sinks from built HTML --------------------------
def test_html_trust_boundary():
    from html.parser import HTMLParser
    class SafeHTML(HTMLParser):
        def handle_starttag(self, tag, attrs):
            assert tag not in ("script", "iframe", "object"), (tag, attrs)
            for name, value in attrs:
                assert not name.lower().startswith("on"), (tag, attrs)
                if name == "href":
                    assert value.startswith(("#", "http://", "https://")), value
                if name == "src":
                    assert value.startswith("data:image/png;base64,"), value
    inv = json.loads((home / "inventory.json").read_text())
    inv["projects"][0]["nodes"][0]["media"].extend([
        {"mock": "</script><script>window.__audit_xss=1</script>"},
        {"src": '\" onerror=\"window.__audit_xss=1'},
        {"link": ["bad", "javascript:window.__audit_xss=1"]}])
    (home / "inventory.json").write_text(json.dumps(inv))
    result = run("build.py", str(home))
    assert result.returncode == 0, result.stderr
    built = (home / "out/index.html").read_text()
    assert "Content-Security-Policy" in built and "sha256-" in built
    assert "WARN p: step 1: rejected unsafe image source" in result.stdout
    result = subprocess.run(["node", str(Path(__file__).with_name("html_security.js"))],
                            input=built, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    fragments = json.loads(result.stdout)
    for fragment in fragments:
        SafeHTML().feed(fragment)
    assert "<b>&lt;img onerror=x&gt;</b>" in "".join(fragments)
    assert '<a href="https://example.com"' in fragments[-1]
    # Restore the fixture for the remaining build tests.
    inv["projects"][0]["nodes"][0]["media"] = inv["projects"][0]["nodes"][0]["media"][:-3]
    (home / "inventory.json").write_text(json.dumps(inv))

test_html_trust_boundary()

# --- build logic --------------------------------------------------------------------------------
import build, datetime as dt

WEBP = b"RIFF" + (12).to_bytes(4, "little") + b"WEBPVP8L\0\0\0\0"
JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 4 + b"\xff\xd9"


def test_shot_validation():
    for name, raw in [("private.txt", b"AUDIT_FAKE_PRIVATE_MARKER"), ("empty.png", b""),
                      ("broken.png", b"\x89PNG\r\n\x1a\nBAD"), ("vector.svg", b"<svg onload='x'/>") ,
                      ("oversized.png", PNG + b"x" * build.MAX_SHOT),
                      ("truncated.png", PNG[:-8]), ("checksum.png", PNG[:-1] + b"x"),
                      ("trailing.png", PNG + b"PRIVATE"),
                      ("truncated.webp", WEBP[:-2]), ("truncated.jpg", JPEG[:-2])]:
        file = tmp / name; file.write_bytes(raw)
        nodes = [{"id": 1, "media": [{"shot": str(file), "src": "data:image/png;base64,eA=="}]}]
        warnings = []
        build.embed_media(nodes, home, warnings.append)
        assert "src" not in nodes[0]["media"][0], name
        assert warnings and "screenshot rejected" in warnings[0], (name, warnings)
        inv = json.loads((home / "inventory.json").read_text())
        previous = inv["projects"][0]["nodes"][0]["media"]
        inv["projects"][0]["nodes"][0]["media"] = [{"shot": str(file)}]
        (home / "inventory.json").write_text(json.dumps(inv))
        result = run("build.py", str(home))
        assert result.returncode == 0 and "screenshot rejected" in result.stdout, result.stderr
        assert '"src":' not in (home / "out/index.html").read_text(), name
        inv["projects"][0]["nodes"][0]["media"] = previous
        (home / "inventory.json").write_text(json.dumps(inv))
    assert build.checked_png(PNG) == "image/png"
    # the real dashboards ship WebP screenshots: they must still embed
    assert (build.checked_image(WEBP), build.checked_image(JPEG)) == ("image/webp", "image/jpeg")
    for path in (shot, home / "relative.png"):
        path.write_bytes(PNG)
        nodes = [{"id": 1, "media": [{"shot": str(path) if path == shot else "relative.png"}]}]
        warnings = []
        build.embed_media(nodes, home, warnings.append)
        assert not warnings and nodes[0]["media"][0]["src"].startswith("data:image/png;base64,")

test_shot_validation()
today = dt.date(2026, 10, 3)
s = build.ticket_series([
    {"state": "done", "created": "2026-09-01", "completed": "2026-09-10"},
    {"state": "dead", "created": "2026-09-01", "canceled": "2026-09-05"},
    {"state": "dead", "created": "2026-09-01"},              # canceled, date unknown: never counted as open
    {"state": "open", "created": "2026-09-20"}], today)
at = lambda d: s["days"].index(d)
assert (s["done"][at("2026-09-09")], s["done"][at("2026-09-10")]) == (0, 1)
assert s["open"][at("2026-09-04")] == 2  # the done one + the one canceled on 9/5
assert s["open"][at("2026-09-06")] == 1 and s["open"][at("2026-10-03")] == 1
f = {"prs": [], "tickets": [], "data": [], "errors": [], "repos": [
    {"label": "main", "dirty": 2, "ahead": 3, "has_origin": True, "upstream": "origin/x", "branch": "x"},
    {"label": "wt", "dirty": 0, "ahead": 0, "has_origin": True, "upstream": None, "branch": "y"}]}
t = build.todos({"key": "k"}, f)
assert [x["parts"] for x in t] == [[[2, "dirty"], [3, "unpushed"]], [[None, "no_upstream"]]], "one row per checkout"

# --- progress history: grouped by week (Monday), a summary is stale once the week gets new work
f = {"prs": [], "commits": [{"hash": "a", "date": "2026-09-28", "subject": "x"}, {"hash": "b", "date": "2026-10-04", "subject": "y"},
                            {"hash": "c", "date": "2026-09-27", "subject": "z"}],
     "tickets": [{"state": "done", "completed": "2026-09-30T10:00", "title": "t"}, {"state": "open", "title": "u"}]}
h = build.history(f, {"2026-09-28": {"n": 2, "text": "s"}, "2026-09-21": {"n": 2, "text": "old"}})
assert [(w["week"], len(w["items"])) for w in h] == [("2026-09-28", 3), ("2026-09-21", 1)], h
assert h[0]["summary"] == "s" and not h[0]["fresh"], "3 items now, summary was written for 2: rewrite it"
assert not h[1]["fresh"]
assert h[0]["items"][0]["text"] == "y", "newest first"
# the whole history reaches the page, and the weeks to summarise are listed for Claude
r = run("build.py", str(home))
need = json.loads((home / "out/summaries-needed.json").read_text())["p"]
assert "SUMMARIES" in r.stdout and sum(w["n"] for w in need) == 3, need
wk = need[0]["week"]
(home / "summaries.json").write_text(json.dumps({"p": {w["week"]: {"n": w["n"], "text": "ok"} for w in need}}))
r = run("build.py", str(home))
assert "SUMMARIES" not in r.stdout and not (home / "out/summaries-needed.json").exists(), r.stdout

# --- a remote URL never shows a token
assert collect.clean_url("https://me:ghp_secret@github.com/o/r.git") == "https://github.com/o/r"
assert collect.clean_url("git@github.com:o/r.git") == "https://github.com/o/r"

# --- git never waits for a password ----------------------------------------------------------
assert collect.GIT_ENV["GIT_TERMINAL_PROMPT"] == "0"


# --- Linear project identity is independent of its display name ------------------------------
from unittest.mock import patch


def test_linear_project_identity():
    issue = {"identifier": "L-1", "title": "one project", "url": "https://linear.app/i",
             "createdAt": "2026-10-01", "completedAt": None, "canceledAt": None,
             "state": {"name": "Open", "type": "unstarted"}}
    for spec, archived, empty in [({"project_id": "a", "project": "Old name"}, None, False),
                                  ({"project_id": "a"}, "2026-09-01", False),
                                  ({"project_id": "a"}, None, True),
                                  ({"project": "Unique"}, "2026-09-01", True)]:
        requests = []
        def api(req, timeout):
            q = json.loads(req.data); requests.append(q)
            variables = q["variables"]
            if q["query"] == collect.LINEAR_PROJECT_Q:
                assert variables == {"id": "a"}
                data = {"project": {"id": "a", "name": "Renamed", "archivedAt": archived}}
            elif q["query"] == collect.LINEAR_NAME_Q:
                assert "includeArchived:true" in q["query"]
                data = {"projects": {"nodes": [{"id": "a", "name": "Unique", "archivedAt": archived}]}}
            else:
                assert variables["id"] == "a" and "name" not in variables
                assert "project:{id:{eq:$id}}" in q["query"] and "includeArchived:true" in q["query"]
                more = not empty and variables["after"] is None
                data = {"issues": {"nodes": [issue] if more else [],
                    "pageInfo": {"hasNextPage": more, "endCursor": "cursor" if more else None}}}
            return io.BytesIO(json.dumps({"data": data}).encode())
        with patch.dict(collect.os.environ, {"LINEAR_API_KEY": "fixture"}), patch.object(urllib.request, "urlopen", side_effect=api):
            tickets = collect.linear_tickets(spec)
        assert len(tickets) == (0 if empty else 1)
        assert len(requests) == (2 if empty else 3)
        if not empty:
            assert requests[-1]["variables"]["after"] == "cursor"


def test_linear_legacy_migration_and_permissions():
    cases = [({"projects": {"nodes": [{"id": "a"}, {"id": "b"}]}}, {"project": "Same"}, "ambiguous"),
             ({"projects": {"nodes": []}}, {"project": "Old"}, "renamed or inaccessible"),
             ({"project": None}, {"project_id": "hidden"}, "not found or inaccessible")]
    for data, spec, expected in cases:
        with patch.dict(collect.os.environ, {"LINEAR_API_KEY": "fixture"}), patch.object(urllib.request, "urlopen", return_value=io.BytesIO(json.dumps({"data": data}).encode())) as api:
            try:
                collect.linear_tickets(spec); raise AssertionError("must not mix or silently lose projects")
            except RuntimeError as e:
                assert expected in str(e), str(e)
                if expected == "ambiguous":
                    assert "project_id" in str(e) and "a, b" in str(e)
            assert api.call_count == 1, "issues must not be read after unresolved identity"
    for response in ({"errors": [{"message": "permission denied"}], "data": None},
                     urllib.error.HTTPError("url", 403, "Forbidden", {}, None)):
        kwargs = {"side_effect": response} if isinstance(response, Exception) else {"return_value": io.BytesIO(json.dumps(response).encode())}
        with patch.dict(collect.os.environ, {"LINEAR_API_KEY": "fixture"}), patch.object(urllib.request, "urlopen", **kwargs):
            try:
                collect.linear_tickets({"project_id": "hidden"}); raise AssertionError("permission error required")
            except RuntimeError as e:
                assert "permission denied" in str(e) or "HTTP 403" in str(e)


test_linear_project_identity()
test_linear_legacy_migration_and_permissions()


# --- wave 1b: collection failures must remain visible -----------------------------------------
from unittest.mock import patch
from contextlib import redirect_stdout
import os, uuid

def fixture(name, sources):
    root = tmp / name; (root / "gathered").mkdir(parents=True)
    (root / "inventory.json").write_text(json.dumps({"projects": [
        {"key": "p", "name": "P", "color": "#c00", "sources": sources}]}))
    return root

def gather(root, status="ok", source="notion", tickets=None):
    rid = uuid.uuid4().hex
    stamp = dt.datetime.now().astimezone().isoformat()
    (root / "gathered" / f"{dt.date.today()}.json").write_text(json.dumps({"_run": {"run_id": rid}, "p": {
        "sources": {source: dict(run_id=rid, attempted_at=stamp, fetched_at=stamp,
          status=status, complete=status == "ok", error=None if status == "ok" else "403")},
        "tickets": tickets or [], "read": [source] if status == "ok" else [], "errors": []}}))
    return rid

def snapshot(root):
    return json.loads((root / "facts" / f"{dt.date.today()}.json").read_text())

def page_data(root):
    import re
    result = run("build.py", str(root)); assert result.returncode == 0, result.stdout + result.stderr
    page = (root / "out/index.html").read_text()
    return json.loads(re.search(r"const D = (.*?);\nconst L", page, re.S)[1].replace("<\\/", "</"))

OLD_TICKET = {"id": "N-1", "title": "old", "source": "notion", "state": "wait", "created": "2026-09-01"}

def test_commit_count_uncapped_worktrees_branches_and_repos():
    repo = tmp / "busy"; repo.mkdir(); git(repo, "init", "-q")
    old = (dt.date.today() - dt.timedelta(days=30)).isoformat() + "T12:00:00+00:00"
    subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "--allow-empty", "-m", "old"],
                   cwd=repo, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_DATE": old, "GIT_COMMITTER_DATE": old})
    for n in range(45):
        git(repo, "commit", "-q", "--allow-empty", "-m", f"busy {n}")
    wt = tmp / "busy-wt"
    git(repo, "worktree", "add", "-q", "-b", "side", str(wt))
    git(wt, "commit", "-q", "--allow-empty", "-m", "only on side branch")
    clone = tmp / "busy-clone"
    git(tmp, "clone", "-q", "--no-hardlinks", str(repo), str(clone))
    git(clone, "remote", "remove", "origin")
    other = tmp / "independent"; other.mkdir(); git(other, "init", "-q")
    git(other, "commit", "-q", "--allow-empty", "-m", "independent commit")
    root = fixture("busy-home", {"local": [{"label": p.name, "path": str(p)} for p in (repo, wt, clone, other)]})
    with redirect_stdout(io.StringIO()):
        code, path, _ = collect.collect_snapshot(root)
    f = json.loads(path.read_text())["projects"]["p"]
    assert code == 0 and f["commit_count_14"] == 47, f["errors"]
    assert sum(w["n"] for w in f["weekly"]) == 48  # includes one old commit
    assert len(f["repos"][0]["recent"]) == 40
    assert all(len(c["hash"]) == 40 for c in f["commits"])
    assert build.now(f, dt.date.today())["c14"] == 47
    assert page_data(root)["projects"][0]["now"]["c14"] == 47
    # The summary must also survive display history being much smaller than the recent set.
    with patch.object(collect, "HISTORY", 10), redirect_stdout(io.StringIO()):
        code, path, _ = collect.collect_snapshot(root)
    f = json.loads(path.read_text())["projects"]["p"]
    assert code == 0 and f["commit_count_14"] == 47 and len(f["commits"]) < 47
    assert page_data(root)["projects"][0]["now"]["c14"] == 47


def test_commit_count_legacy_snapshot():
    since = dt.date.today()
    recent = [{"hash": f"{n:040x}", "date": since.isoformat(), "subject": str(n)} for n in range(45)]
    f = {"commits": recent, "repos": [{"recent": recent[:40], "last_commit": None}], "errors": [], "tickets": []}
    assert build.now(f, since)["c14"] == 45
    f["commits"].append({"hash": "old", "date": "2000-01-01", "subject": "old"})
    assert build.now(f, since)["c14"] == 45
    del f["commits"]
    assert build.now(f, since)["c14"] == 40  # very old snapshots only retain the display list


test_commit_count_uncapped_worktrees_branches_and_repos()
test_commit_count_legacy_snapshot()


def test_sqlite_identifier_validation():
    import sqlite3
    path = tmp / "quoted.sqlite"
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE "day""table" ("date""quoted" TEXT, date TEXT)')
        con.execute('INSERT INTO "day""table" VALUES (?, ?)', ("2026-10-05", "2026-10-04"))
        con.execute('CREATE TABLE empty (date TEXT)')
        con.execute('CREATE TABLE nulls (date TEXT)')
        con.execute('INSERT INTO nulls VALUES (NULL)')
    spec = {"path": str(path), "kind": "sqlite", "table": 'day"table', "column": 'date"quoted'}
    assert collect.newest_date(spec) == "2026-10-05"
    assert collect.newest_date({**spec, "column": "DATE"}) == "2026-10-04"
    for changes, message in [({"column": "2026-10-05"}, "column '2026-10-05' not found"),
                             ({"column": "typo"}, "column 'typo' not found"),
                             ({"table": "missing"}, 'table/source "missing" not found'),
                             ({"table": 'missing"; DROP TABLE empty; --'}, "not found or unreadable"),
                             ({"table": "empty", "column": "date"}, "empty table/source"),
                             ({"table": "nulls", "column": "date"}, "no values in column")]:
        try:
            collect.newest_date({**spec, **changes}); raise AssertionError("accurate error required")
        except RuntimeError as e:
            assert message in str(e), str(e)
    with sqlite3.connect(path) as con:
        assert con.execute('SELECT COUNT(*) FROM empty').fetchone()[0] == 0


def test_duckdb_identifier_validation():
    # Exercise the optional adapter with a stdlib SQL backend; never require/install duckdb.
    import sqlite3
    path = tmp / "quoted.sqlite"
    calls = []
    def connect(name, read_only):
        calls.append((name, read_only))
        return sqlite3.connect(f"file:{name}?mode=ro", uri=True)
    with patch.dict(sys.modules, {"duckdb": types.SimpleNamespace(connect=connect)}):
        spec = {"kind": "duckdb", "path": str(path), "table": 'day"table', "column": 'date"quoted'}
        assert collect.newest_date(spec) == "2026-10-05"
        for changes, message in [({"column": "2026-10-05"}, "not found"),
                                 ({"table": "missing"}, "not found or unreadable"),
                                 ({"table": "empty", "column": "date"}, "empty table/source")]:
            try:
                collect.newest_date({**spec, **changes}); raise AssertionError("metadata validation required")
            except RuntimeError as e:
                assert message in str(e), str(e)
    assert len(calls) == 4 and all(read_only for _, read_only in calls)


test_sqlite_identifier_validation()
test_duckdb_identifier_validation()


def test_github_pr_pagination():
    for count in (0, 50, 51, 101):
        calls = []
        def api(cmd, **kwargs):
            page = len(calls); calls.append(cmd)
            assert cmd[:3] == ["gh", "api", "graphql"]
            assert (f"after=c{page}" in cmd) if page else not any(x.startswith("after=") for x in cmd)
            nodes = [{"number": n, "title": str(n)} for n in range(page * 50, min(count, (page + 1) * 50))]
            return json.dumps({"data": {"repository": {"pullRequests": {"nodes": nodes,
                "pageInfo": {"hasNextPage": (page + 1) * 50 < count, "endCursor": f"c{page + 1}"}}}}})
        with patch.object(collect, "run", side_effect=api):
            prs = collect.gh_prs("o/r")
        assert len(prs) == count and all(p["repo"] == "o/r" for p in prs)
        assert len(calls) == max(1, (count + 49) // 50)


def test_github_denied_second_page():
    first = json.dumps({"data": {"repository": {"pullRequests": {"nodes": [{"number": n} for n in range(50)],
        "pageInfo": {"hasNextPage": True, "endCursor": "next"}}}}})
    root = fixture("github-denied", {"github": ["o/r"]})
    with patch.object(collect.shutil, "which", return_value="gh"), patch.object(collect, "run", side_effect=[first, RuntimeError("permission denied")]), redirect_stdout(io.StringIO()):
        code, path, _ = collect.collect_snapshot(root)
    f = json.loads(path.read_text())["projects"]["p"]
    assert code == 1 and f["prs"] == []
    assert f["sources"]["github:o/r"]["status"] == "failed" and not f["sources"]["github:o/r"]["complete"]
    assert any("PR page 2: permission denied" in e for e in f["errors"])
    assert run("build.py", str(root)).returncode == 0
    assert "permission denied" in (root / "out/index.html").read_text()


def test_github_mcp_with_unauthed_cli():
    root = fixture("github-mcp-cli", {"github": ["o/r"]})
    gather(root, source="github:o/r")
    path = next((root / "gathered").glob("*.json"))
    g = json.loads(path.read_text()); g["p"]["prs"] = [{"number": 1, "repo": "o/r"}]
    path.write_text(json.dumps(g))
    with patch.object(collect.shutil, "which", return_value="gh"), patch.object(collect, "run", side_effect=RuntimeError("not logged in")) as api, redirect_stdout(io.StringIO()):
        code, path, _ = collect.collect_snapshot(root)
    assert code == 0 and len(json.loads(path.read_text())["projects"]["p"]["prs"]) == 1
    api.assert_not_called()


test_github_pr_pagination()
test_github_denied_second_page()
test_github_mcp_with_unauthed_cli()


def test_same_day_reuse():
    root = fixture("same-day", {"notion": {"url": "x"}})
    rid = gather(root, tickets=[OLD_TICKET])
    first = run("collect.py", str(root)); assert first.returncode == 0, first.stdout + first.stderr
    assert snapshot(root)["run_id"] == rid
    assert page_data(root)["projects"][0]["counts"]["wait"] == 1
    second = run("collect.py", str(root)); assert second.returncode == 1, second.stdout + second.stderr
    f = snapshot(root)["projects"]["p"]
    assert snapshot(root)["run_id"] != rid and f["sources"]["notion"]["status"] == "stale"
    assert f["tickets"] == [] and f["stale_tickets"] == [OLD_TICKET]
    p = page_data(root)["projects"][0]
    assert p["counts"]["wait"] == 0 and p["trend_tickets"] is None
    assert 'stale' in (root / "out/index.html").read_text()

def test_cron_takeover():
    root = fixture("cron", {"linear": {"project": "P"}})
    gather(root, source="linear", tickets=[{**OLD_TICKET, "source": "linear"}])
    with patch.dict(os.environ, {"LINEAR_API_KEY": "fixture"}), patch.object(collect, "linear_tickets", return_value=[]) as api:
        for _ in range(2):
            with patch.object(sys, "argv", ["collect.py", str(root)]), redirect_stdout(io.StringIO()):
                try: collect.main()
                except SystemExit as e: assert e.code == 0
        assert api.call_count == 2
    f = snapshot(root)["projects"]["p"]
    assert f["sources"]["linear"]["status"] == "ok" and f["tickets"] == []

def test_failed_source_keeps_tickets():
    root = fixture("failed-old", {"notion": {"url": "x"}})
    gather(root, status="failed", tickets=[OLD_TICKET])
    result = run("collect.py", str(root)); assert result.returncode == 1
    f = snapshot(root)["projects"]["p"]
    assert f["sources"]["notion"]["status"] == "failed" and f["tickets"] == []
    p = page_data(root)["projects"][0]
    assert p["counts"]["wait"] == 0 and p["now"]["wait"] == 0 and p["trend_tickets"] is None

def test_mcp_prs_per_repo():
    root = fixture("mcp-prs", {"github": ["o/a", "o/b"]})
    gather(root, source="github:o/a")
    with patch.object(collect.shutil, "which", return_value=None), patch.object(sys, "argv", ["collect.py", str(root)]), redirect_stdout(io.StringIO()):
        try: collect.main()
        except SystemExit as e: assert e.code == 1
    states = snapshot(root)["projects"]["p"]["sources"]
    assert states["github:o/a"]["status"] == "ok" and states["github:o/b"]["status"] == "unavailable"

def rendered(root):
    result = subprocess.run(["node", str(Path(__file__).with_name("html_collection.js"))],
        input=(root / "out/index.html").read_text(), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)

def test_git_fetch_failures():
    repo = tmp / "fetch-repo"; repo.mkdir(); git(repo, "init", "-q")
    git(repo, "commit", "-q", "--allow-empty", "-m", "local")
    (repo / "dirty.txt").write_text("local work")
    git(repo, "remote", "add", "origin", str(tmp / "nonexistent-origin"))
    original_run = collect.run
    for name, error in [("offline", None), ("permission", RuntimeError("Permission denied (publickey)")),
                        ("timeout", subprocess.TimeoutExpired(["git", "fetch"], 60))]:
        root = fixture("fetch-" + name, {"local": [{"label": "local", "path": str(repo)}]})
        def local_run(cmd, **kwargs):
            if cmd[1] == "fetch" and error is not None: raise error
            return original_run(cmd, **kwargs)
        with patch.object(collect, "run", side_effect=local_run), patch.object(sys, "argv", ["collect.py", str(root)]), redirect_stdout(io.StringIO()):
            try: collect.main()
            except SystemExit as e: assert e.code == 1
        f = snapshot(root)["projects"]["p"]; r = f["repos"][0]
        assert r["dirty"] == 1 and r["ahead"] is None and r["behind"] is None
        assert f["sources"]["git:" + str(repo)]["status"] == "partial" and f["errors"]
        page_data(root); fragments = rendered(root)[0]
        assert "Remote refresh failed; remote comparison unknown" in fragments["facts"]
        assert "Uncommitted files 1" in fragments["facts"] and "some sources failed" in fragments["now"]
    # Last successful fetch survives the next failure.
    root = fixture("fetch-last-good", {"local": [{"label": "local", "path": str(repo)}]})
    def success(cmd, **kwargs):
        return "" if cmd[1] == "fetch" else original_run(cmd, **kwargs)
    with patch.object(collect, "run", side_effect=success), patch.object(sys, "argv", ["collect.py", str(root)]), redirect_stdout(io.StringIO()):
        try: collect.main()
        except SystemExit as e: assert e.code == 0
    last = snapshot(root)["projects"]["p"]["repos"][0]["last_fetched_at"]
    result = run("collect.py", str(root)); assert result.returncode == 1
    assert snapshot(root)["projects"]["p"]["repos"][0]["last_fetched_at"] == last

def test_fatal_refresh_inputs():
    for name, bad_inventory, added in [("invalid-inventory", True, False),
                                      ("invalid-gathered", False, False),
                                      ("new-project-fatal", False, True)]:
        root = fixture(name, {})
        result = run("collect.py", str(root), "--refresh"); assert result.returncode == 0, result.stderr
        before = page_data(root); saved = (root / "facts" / f"{dt.date.today()}.json").read_bytes()
        if bad_inventory:
            (root / "inventory.json").write_text("{bad")
        else:
            if added:
                inv = json.loads((root / "inventory.json").read_text())
                inv["projects"].append({"key": "new", "name": "New", "color": "#000", "sources": {}})
                (root / "inventory.json").write_text(json.dumps(inv))
            (root / "gathered" / f"{dt.date.today()}.json").write_text("{bad")
        result = run("collect.py", str(root), "--refresh")
        assert result.returncode == 2 and "FAILED:" in result.stderr and "rerun collect.py HOME --refresh" in result.stderr
        assert "Traceback" not in result.stderr and "built " not in result.stdout
        assert (root / "facts" / f"{dt.date.today()}.json").read_bytes() == saved
        manifest = json.loads((root / "refresh.json").read_text()); assert manifest["status"] == "fatal"
        # Even the old documented collect; build sequence cannot hide this failure.
        result = run("build.py", str(root)); assert result.returncode == 2 and "built " not in result.stdout
        page = (root / "out/index.html").read_text()
        assert 'role="alert"' in page and "FAILED: refresh" in page
        assert before["generated_at"] in page, "failure must retain the last-good timestamp"
        assert "FAILED: refresh" in (root / "out/artifact.html").read_text()
        # Restore inputs: one command recovers and removes the failure banner.
        (root / "inventory.json").write_text(json.dumps({"projects": [{"key": "p", "name": "P", "color": "#c00", "sources": {}}]}))
        (root / "gathered" / f"{dt.date.today()}.json").write_text("{}")
        result = run("collect.py", str(root), "--refresh"); assert result.returncode == 0, result.stderr
        assert "<!--refresh-failure-->" not in (root / "out/index.html").read_text()

def test_snapshot_write_failure():
    root = fixture("write-failed", {})
    assert run("collect.py", str(root), "--refresh").returncode == 0
    saved = (root / "facts" / f"{dt.date.today()}.json").read_bytes()
    original_replace = Path.replace
    def deny_snapshot(path, target):
        if Path(target).parent == root / "facts": raise PermissionError("fixture: facts write denied")
        return original_replace(path, target)
    output = io.StringIO()
    from contextlib import redirect_stderr
    with patch.object(Path, "replace", deny_snapshot), patch.object(sys, "argv", ["collect.py", str(root), "--refresh"]), redirect_stdout(output), redirect_stderr(output):
        try: collect.main()
        except SystemExit as e: assert e.code == 2
    assert "facts write denied" in output.getvalue() and "rerun collect.py HOME --refresh" in output.getvalue()
    assert (root / "facts" / f"{dt.date.today()}.json").read_bytes() == saved
    assert not list((root / "facts").glob(".pending-*")), "failed atomic writes must clean up"
    result = run("build.py", str(root)); assert result.returncode == 2
    assert "FAILED: refresh" in (root / "out/index.html").read_text()

def test_manifest_write_failure():
    root = fixture("manifest-denied", {})
    assert run("collect.py", str(root), "--refresh").returncode == 0
    original_write = collect.atomic_write
    def deny_manifest(path, text):
        if path.name == "refresh.json": raise PermissionError("fixture: manifest denied")
        return original_write(path, text)
    from contextlib import redirect_stderr
    output = io.StringIO()
    with patch.object(collect, "atomic_write", side_effect=deny_manifest), patch.object(sys, "argv", ["collect.py", str(root), "--refresh"]), redirect_stdout(output), redirect_stderr(output):
        try: collect.main()
        except SystemExit as e: assert e.code == 2
    assert "no build was attempted" in output.getvalue()
    result = run("build.py", str(root)); assert result.returncode == 2 and "latest refresh failed" in result.stderr
    assert "FAILED: refresh" in (root / "out/index.html").read_text()
    assert run("collect.py", str(root), "--refresh").returncode == 0

def test_refresh_manifest_and_partial():
    root = fixture("partial-refresh", {"notion": {"url": "x"}})
    gather(root, tickets=[OLD_TICKET])
    result = run("collect.py", str(root), "--refresh", "--script-only")
    assert result.returncode == 1 and "built " in result.stdout, result.stdout + result.stderr
    manifest = json.loads((root / "refresh.json").read_text())
    assert manifest["status"] == "partial" and manifest["run_id"] == snapshot(root)["run_id"]
    assert page_data(root)["projects"][0]["counts"]["wait"] == 0
    result = run("build.py", str(root), "--run-id", "wrong-run")
    assert result.returncode == 2 and "run_id does not match" in result.stderr and "built " not in result.stdout
    assert run("collect.py", str(root), "--refresh", "--script-only").returncode == 1
    result = run("build.py", str(root), "--snapshot", str(root / "facts" / "other.json"))
    assert result.returncode == 2 and "snapshot does not match" in result.stderr

def test_five_ticket_states():
    labels = {"empty": "Read successfully, 0 tickets.", "not_connected": "No Linear or Notion source.",
              "failed": "Ticket read failed", "partial": "Ticket read partly failed", "stale": "Ticket data is stale"}
    for status in labels:
        root = fixture("state-" + status, {} if status == "not_connected" else {"notion": {"url": "x"}})
        if status != "not_connected":
            gather(root, status="failed" if status == "failed" else "ok", tickets=[OLD_TICKET] if status in ("failed", "stale", "partial") else [])
        if status == "partial":
            inv = json.loads((root / "inventory.json").read_text())
            inv["projects"][0]["sources"]["linear"] = {"project": "P"}
            (root / "inventory.json").write_text(json.dumps(inv))
            gathered = root / "gathered" / f"{dt.date.today()}.json"
            g = json.loads(gathered.read_text())
            g["p"]["sources"]["linear"] = {"status": "failed", "error": "403", "fetched_at": "2026-09-01T00:00:00+00:00"}
            gathered.write_text(json.dumps(g))
        with patch.dict(os.environ, {}, clear=True):
            result = run("collect.py", str(root))
        assert result.returncode == (0 if status in ("empty", "not_connected", "stale") else 1), result.stdout + result.stderr
        if status == "stale":
            for _ in range(3):
                assert run("collect.py", str(root)).returncode == 1, "reused gather must stay stale on every run"
        p = page_data(root)["projects"][0]; fragments = rendered(root)[0]
        assert p["ticket_state"]["status"] == status, p["ticket_state"]
        assert labels[status] in fragments["tickets"] and 'data-panel="tickets"' in fragments["project"]
        if status in ("failed", "partial", "stale"):
            assert p["trend_tickets"] is None and labels[status] in fragments["trends"]
            assert "Check source permissions and gather again." in fragments["tickets"]
            assert "Last successful read:" in fragments["tickets"]
            assert "done in the last 7 days" not in fragments["now"]
            assert labels[status] in fragments["now"]
        if status == "partial":
            assert p["counts"]["wait"] == 1 and "available data only" in fragments["tickets"]
            assert "403" in fragments["tickets"] and "2026-09-01" in fragments["tickets"]
        elif status == "empty":
            assert p["trend_tickets"] and sum(p["trend_tickets"]["open"]) == 0
        else:
            assert sum(p["counts"].values()) == 0
        inv = json.loads((root / "inventory.json").read_text()); inv["lang"] = "zh-TW"
        (root / "inventory.json").write_text(json.dumps(inv))
        page_data(root)
        zh = {"empty": "已讀取，0 張待辦", "not_connected": "沒有接 Linear 或 Notion",
              "failed": "待辦讀取失敗", "partial": "待辦部分讀取失敗", "stale": "待辦資料已過期"}
        assert zh[status] in rendered(root)[0]["tickets"]


def test_partial_ticket_read():
    root = fixture("partial-source", {"notion": {"url": "x"}})
    gather(root, status="partial", tickets=[OLD_TICKET])
    assert run("collect.py", str(root)).returncode == 1
    p = page_data(root)["projects"][0]
    assert p["ticket_state"]["status"] == "partial" and p["trend_tickets"] is None
    assert p["counts"]["wait"] == 0 and "Previous data" in rendered(root)[0]["tickets"]


def test_old_and_legacy_ticket_states():
    root = fixture("aged-state", {"notion": {"url": "x"}})
    gather(root, tickets=[OLD_TICKET]); assert run("collect.py", str(root)).returncode == 0
    path = root / "facts" / f"{dt.date.today()}.json"
    snap = snapshot(root)
    snap["projects"]["p"]["sources"]["notion"]["fetched_at"] = "2000-01-01T00:00:00+00:00"
    path.write_text(json.dumps(snap))
    p = page_data(root)["projects"][0]
    assert p["ticket_state"]["status"] == "stale" and p["trend_tickets"] is None and p["counts"]["wait"] == 0
    snap["projects"]["p"].pop("sources")
    path.write_text(json.dumps(snap))
    p = page_data(root)["projects"][0]
    assert p["ticket_state"]["status"] == "stale" and p["counts"]["wait"] == 0
    assert "Source freshness was not recorded" in rendered(root)[0]["tickets"]
    snap["projects"]["p"]["errors"] = ["notion: 403"]
    path.write_text(json.dumps(snap))
    assert page_data(root)["projects"][0]["ticket_state"]["status"] == "failed"


def test_last_success_across_days():
    root = fixture("last-read-yesterday", {"notion": {"url": "x"}})
    gather(root); assert run("collect.py", str(root)).returncode == 0
    snap = snapshot(root); last = snap["projects"]["p"]["sources"]["notion"]["fetched_at"]
    current = root / "facts" / f"{dt.date.today()}.json"
    current.rename(root / "facts" / f"{dt.date.today() - dt.timedelta(days=1)}.json")
    (root / "gathered" / f"{dt.date.today()}.json").unlink()
    assert run("collect.py", str(root)).returncode == 1
    assert snapshot(root)["projects"]["p"]["sources"]["notion"]["fetched_at"] == last
    page_data(root); assert last in rendered(root)[0]["tickets"]

test_five_ticket_states()
test_partial_ticket_read()
test_old_and_legacy_ticket_states()
test_last_success_across_days()
test_fatal_refresh_inputs()
test_snapshot_write_failure()
test_manifest_write_failure()
test_refresh_manifest_and_partial()
test_git_fetch_failures()
test_same_day_reuse()
test_cron_takeover()
test_failed_source_keeps_tickets()
test_mcp_prs_per_repo()
os.environ.pop("LINEAR_API_KEY", None)

# --- Vercel -----------------------------------------------------------------------------------
vhome = tmp / "vhome"; (vhome / "out").mkdir(parents=True); (vhome / "out/index.html").write_text("x")
pv.TOKEN = "t"
real_call = pv.call
REAL_ANON = pv.anon_status
pv.shutil.which = lambda _: "/bin/vercel"
calls = []

def fake_call(method, path, body=None, team=None):
    calls.append((method, path, team))
    if method == "GET" and path.startswith("/v9/projects/") and "/domains?" not in path:
        return 200, {"id": "prj_1", "accountId": "acc", "ssoProtection": {"deploymentType": "all"}}
    if method == "PATCH":
        return 200, {"ssoProtection": {"deploymentType": "all"}}
    if "/domains?" in path:
        return 200, {"domains": [], "pagination": {"next": None}}
    return 200, {"alias": []}

def deploy(codes, *args, api=fake_call):
    pv.call = api
    pv.subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="https://x-1.vercel.app\n", stderr="")
    pv.anon_status = lambda url: codes(url) if callable(codes) else codes
    sys.argv = ["publish_vercel.py", str(vhome), "dash", *args]
    try:
        pv.main(); return "ok"
    except SystemExit as e:
        return str(e.code)

# an existing project this script did not make is never deployed over
calls.clear()
assert "already exists" in deploy(401)
assert not any(m == "PATCH" for m, _, _ in calls), "must stop before touching the project"
# --reuse takes it over and remembers it; the next run needs no flag
assert deploy("Vercel login redirect", "--reuse") == "ok"
assert json.loads((vhome / "vercel.json").read_text()) == {"dash": "prj_1"}
assert deploy("Vercel login redirect") == "ok"
# only a login wall proves the lock: 200 is public, 404 and "unreachable" prove nothing
assert deploy(302) != "ok"
for bad in (200, 401, 403, 404, 500, 302, "unreachable (x)"):
    assert "could not confirm the page is locked" in deploy(bad), bad

# a redirect counts as the lock only when it goes to Vercel's sign-in
import email.message
def redirect_to(loc):
    h = email.message.Message(); h["Location"] = loc
    def opener(*_):
        def open_(url, timeout):
            raise urllib.error.HTTPError(url, 302, "Found", h, None)
        return types.SimpleNamespace(open=open_)
    return opener
pv.urllib.request.build_opener = redirect_to("https://vercel.com/sso-api?url=https%3A%2F%2Fx%2F")
assert REAL_ANON("https://x/") == "Vercel login redirect"
pv.urllib.request.build_opener = redirect_to("https://example.com/")
assert REAL_ANON("https://x/") == "302 to https://example.com/"

def test_vercel_fail_closed():
    def verify(api, codes="Vercel login redirect"):
        output = io.StringIO()
        from contextlib import redirect_stdout
        with redirect_stdout(output):
            result = deploy(codes, api=api)
        assert result != "ok" and result.startswith("FAILED:"), result
        assert "deployed:" not in output.getvalue(), output.getvalue()
        assert "Deployment Protection" in result and "PUBLIC" in result, result
        return result
    for endpoint in ("/v13/deployments/", "/domains?"):
        for status in (403, 429):
            def api(method, path, body=None, team=None):
                return (status, {}) if endpoint in path else fake_call(method, path, body, team)
            assert f"API {status}" in verify(api)
    for aliases in (None, {}, "dash.vercel.app", [None], ["x/attack"]):
        def api(method, path, body=None, team=None):
            return (200, {"alias": aliases}) if "/v13/" in path else fake_call(method, path, body, team)
        verify(api)
    visited = []
    def api(method, path, body=None, team=None):
        if "/v13/" in path:
            return 200, {"alias": ["dash.vercel.app", "public-exception.vercel.app"]}
        if "/domains?" in path:
            return 200, {"domains": [{"name": "private.example.com"}, {"name": "public.example.com"}],
                         "pagination": {"next": None}}
        return fake_call(method, path, body, team)
    for public in ("public.example.com", "public-exception.vercel.app"):
        visited.clear()
        def codes(url):
            visited.append(url)
            return 200 if public in url else "Vercel login redirect"
        assert public in verify(api, codes)
        assert len(visited) == 5, visited  # deployment, both aliases and both custom domains
    for bad in ("unreachable (timeout)", "302 to https://vercel.com/docs", 401, 403):
        verify(api, lambda url: bad if "private.example.com" in url else "Vercel login redirect")
    def pages(method, path, body=None, team=None):
        if "/domains?" in path:
            return (200, {"domains": [{"name": "page2.example.com"}], "pagination": {"next": None}}) if "until=" in path else (200, {"domains": [], "pagination": {"next": 123}})
        return fake_call(method, path, body, team)
    assert "page2.example.com" in verify(pages, lambda url: 200 if "page2" in url else "Vercel login redirect")
    for domains in ({}, {"domains": "x"}, {"domains": [None]}, {"domains": [{"name": "x/y"}]},
                    {"domains": [], "pagination": {}}):
        def malformed(method, path, body=None, team=None):
            return (200, domains) if "/domains?" in path else fake_call(method, path, body, team)
        verify(malformed)

def test_vercel_login_redirect():
    for loc in ("https://vercel.com/", "https://vercel.com/docs", "https://vercel.com/login",
                "https://vercel.com.evil/sso-api?url=https%3A%2F%2Fx%2F", "https://vercel.com/sso-api?url=wrong"):
        pv.urllib.request.build_opener = redirect_to(loc)
        assert REAL_ANON("https://x/") != "Vercel login redirect", loc
    def offline(*_):
        def open_(url, timeout):
            raise urllib.error.URLError("offline")
        return types.SimpleNamespace(open=open_)
    pv.urllib.request.build_opener = offline
    assert "unreachable" in REAL_ANON("https://x/")

test_vercel_fail_closed()
test_vercel_login_redirect()

# team: an id goes as teamId=, a slug as slug=
class R(io.BytesIO):
    status = 200
urls = []
urllib.request.urlopen = lambda req, timeout: urls.append(req.full_url) or R(b"{}")
real_call("GET", "/v9/projects/x", team="team_abc"); real_call("GET", "/v9/projects/x", team="my-team")
assert urls == ["https://api.vercel.com/v9/projects/x?teamId=team_abc", "https://api.vercel.com/v9/projects/x?slug=my-team"], urls

def test_vercel_access_scope():
    from contextlib import redirect_stdout
    output = io.StringIO()
    with redirect_stdout(output):
        assert deploy("Vercel login redirect", "--team", "team_abc") == "ok"
    text = output.getvalue()
    assert "account=acc team=team_abc project=dash (prj_1)" in text
    assert "Vercel-authorized users" in text and "sharing and bypass settings" in text
    repo = S.parents[2]
    for path, bad in [(repo / "README.md", "only your logged-in Vercel account"),
                      (repo / "說明書.md", "只有登入你 Vercel 帳號的人"),
                      (S.parent / "SKILL.md", "only the user's logged-in Vercel account")]:
        assert bad not in path.read_text(), path
    assert "only the owner's" not in pv.__doc__

test_vercel_access_scope()
print("OK")
