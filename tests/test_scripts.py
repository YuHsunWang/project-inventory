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
# Notion not gathered -> exit 1 (that is why the docs say `;`, not `&&`), and the hint names the other date
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


# --- Linear: an empty project is fine, a wrong name is an error -------------------------------
def fake_linear(projects):
    body = {"data": {"projects": {"nodes": projects}, "issues": {"nodes": [], "pageInfo": {"hasNextPage": False}}}}
    return lambda req, timeout: io.BytesIO(json.dumps(body).encode())

collect.os.environ["LINEAR_API_KEY"] = "k"
urllib.request.urlopen = fake_linear([{"id": "1"}])
assert collect.linear_tickets("New") == []
urllib.request.urlopen = fake_linear([])
try:
    collect.linear_tickets("Typo"); raise AssertionError("missing project must raise")
except RuntimeError as e:
    assert "no Linear project named" in str(e)


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
