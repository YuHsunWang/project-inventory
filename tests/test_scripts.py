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

def test_shot_validation():
    for name, raw in [("private.txt", b"AUDIT_FAKE_PRIVATE_MARKER"), ("empty.png", b""),
                      ("broken.png", b"\x89PNG\r\n\x1a\nBAD"), ("vector.svg", b"<svg onload='x'/>") ,
                      ("oversized.png", PNG + b"x" * build.MAX_SHOT),
                      ("truncated.png", PNG[:-8]), ("checksum.png", PNG[:-1] + b"x"),
                      ("trailing.png", PNG + b"PRIVATE")]:
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


# --- Vercel -----------------------------------------------------------------------------------
vhome = tmp / "vhome"; (vhome / "out").mkdir(parents=True); (vhome / "out/index.html").write_text("x")
pv.TOKEN = "t"
real_call = pv.call
REAL_ANON = pv.anon_status
pv.shutil.which = lambda _: "/bin/vercel"
calls = []

def fake_call(method, path, body=None, team=None):
    calls.append((method, path, team))
    if method == "GET" and path.startswith("/v9/projects/"):
        return 200, {"id": "prj_1", "accountId": "acc"}
    if method == "PATCH":
        return 200, {"ssoProtection": {"deploymentType": "all"}}
    return 200, {"alias": []}

def deploy(codes, *args):
    pv.call = fake_call
    pv.subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="https://x-1.vercel.app\n", stderr="")
    pv.anon_status = lambda url: codes
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
assert deploy(401, "--reuse") == "ok"
assert json.loads((vhome / "vercel.json").read_text()) == {"dash": "prj_1"}
assert deploy(401) == "ok"
# only a login wall proves the lock: 200 is public, 404 and "unreachable" prove nothing
assert deploy(302) == "ok"
for bad in (200, 404, "unreachable (x)"):
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
pv.urllib.request.build_opener = redirect_to("https://vercel.com/sso-api?url=x")
assert REAL_ANON("https://x/") == 302
pv.urllib.request.build_opener = redirect_to("https://example.com/")
assert REAL_ANON("https://x/") == "302 to https://example.com/"

# team: an id goes as teamId=, a slug as slug=
class R(io.BytesIO):
    status = 200
urls = []
urllib.request.urlopen = lambda req, timeout: urls.append(req.full_url) or R(b"{}")
real_call("GET", "/v9/projects/x", team="team_abc"); real_call("GET", "/v9/projects/x", team="my-team")
assert urls == ["https://api.vercel.com/v9/projects/x?teamId=team_abc", "https://api.vercel.com/v9/projects/x?slug=my-team"], urls

print("OK")
