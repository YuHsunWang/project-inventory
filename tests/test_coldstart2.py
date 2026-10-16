"""Regressions for cold-start issues 41–46; no deployment or private home writes."""
from contextlib import redirect_stdout
import base64
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from test_support import case, summary

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "skills/project-inventory/scripts"
sys.path.insert(0, str(S))
import build, capture_shots, check_page, collect, publish_vercel, validation

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGP4DwQACfsD/fteaysAAAAASUVORK5CYII=")


def inventory(home, sources=None, **extra):
    inv = {"lang": "en", "projects": [{"key": "p", "name": "Project", "sources": sources or {},
            "nodes": [{"id": 1, "title": "View"}]}], **extra}
    (home / "inventory.json").write_text(json.dumps(inv))
    return inv


def collect_build(home):
    with redirect_stdout(io.StringIO()):
        code, path, _ = collect.collect_snapshot(home)
        build.build_page(home)
    return code, json.loads(path.read_text())["projects"]["p"]


@case
def test_issue41_capture_timestamp_and_caption():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        inv = inventory(home)
        media = {"capture": "https://example.com/private-source", "caption": "Live site: report"}
        inv["projects"][0]["nodes"][0]["media"] = [media]
        with patch.object(capture_shots, "screenshot", return_value=PNG), redirect_stdout(io.StringIO()):
            capture_shots.capture_shots(home, inv)
        stamp = media.get("captured_at")
        assert stamp, "successful capture must record when the image was taken"
        assert dt.datetime.fromisoformat(stamp).tzinfo is not None
        saved = json.loads((home / "inventory.json").read_text())
        assert saved["projects"][0]["nodes"][0]["media"][0]["captured_at"] == stamp
        collect_build(home)
        page = (home / "out/index.html").read_text()
        result = subprocess.run(["node", str(ROOT / "tests/html_collection.js")], input=page,
                                text=True, capture_output=True, check=True)
        rendered = json.loads(result.stdout)[0]["project"]
        assert stamp in rendered and "Live site: report" in rendered, rendered
        for name in ("index.html", "artifact.html"):
            assert media["capture"] not in (home / "out" / name).read_text()
        with patch.object(capture_shots, "screenshot", side_effect=RuntimeError("offline")), redirect_stdout(io.StringIO()):
            capture_shots.capture_shots(home, inv)
        assert media["captured_at"] == stamp, "failed capture must retain last-good time"
        import auto_refresh
        before = auto_refresh.inventory_fingerprint(inv)
        media["captured_at"] = "2026-10-16T23:00:00+00:00"
        assert auto_refresh.inventory_fingerprint(inv) == before, "capture time alone must not invalidate unchanged pixels"
        media["caption"] = "Local build output: report"
        assert auto_refresh.inventory_fingerprint(inv) != before, "caption edits must invalidate the page"

        skill = (S.parent / "SKILL.md").read_text()
        assert "caption" in skill and "live site or a local build output" in skill


def browser_check(home):
    from demo_fixture import offline_fonts
    offline_fonts(home)
    return subprocess.run([sys.executable, str(S / "check_page.py"), str(home)],
                          capture_output=True, text=True, timeout=180)


@case
def test_issue42_long_title_menu_and_clipped_control():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        inv = inventory(home, title="A very long inventory title with three real projects")
        inv["projects"][0]["name"] = "A very long project name that should wrap or truncate"
        (home / "inventory.json").write_text(json.dumps(inv))
        collect_build(home)
        original = check_page.CDP.overflow
        def inspect(c, where):
            original(c, where)
            assert not c.evaluate("document.querySelector('#menubtn').scrollWidth > document.querySelector('#menubtn').clientWidth"), "menu text is clipped"
            assert c.evaluate("document.querySelector('#menubtn').getBoundingClientRect().width >= 90"), "menu must remain usable"
        from demo_fixture import offline_fonts
        offline_fonts(home)
        output = io.StringIO()
        with patch.object(check_page.CDP, "overflow", inspect), patch.object(sys, "argv", ["check_page.py", str(home)]), redirect_stdout(output):
            code = check_page.main()
        assert code == 0, output.getvalue()
        page = home / "out/index.html"
        page.write_text(page.read_text().replace("</style>", "#menubtn{width:30px!important;min-width:0!important;max-width:30px!important;overflow:hidden;display:block}</style>"))
        result = browser_check(home)
        assert result.returncode != 0 and "clipped control text: #menubtn" in result.stdout, result.stdout


@case
def test_issue43_scroll_before_each_full_page_capture():
    with tempfile.TemporaryDirectory() as td:
        events = []
        c = object.__new__(check_page.CDP)
        def evaluate(expression):
            events.append(("evaluate", expression))
        def call(method, **params):
            assert events and events[-1][0] == "evaluate" and "scrollTo" in events[-1][1], "scroll to top must precede each full-page screenshot"
            assert params["captureBeyondViewport"] is True
            events.append((method, params))
            return {"data": base64.b64encode(PNG).decode()}
        c.evaluate, c.call = evaluate, call
        for name in ("road", "opened-step", "progress"):
            c.shot(Path(td), name)
            assert (Path(td) / (name + ".png")).read_bytes() == PNG
        assert len([e for e in events if e[0] == "Page.captureScreenshot"]) == 3


@case
def test_issue44_refresh_cli_token_before_reading_auth():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        auth = home / ".local/share/com.vercel.cli/auth.json"
        auth.parent.mkdir(parents=True)
        auth.write_text(json.dumps({"token": "expired"}))
        def refresh(cmd, **kwargs):
            assert cmd == ["vercel", "whoami"] and kwargs["timeout"] > 0
            auth.write_text(json.dumps({"token": "refreshed"}))
            return SimpleNamespace(returncode=0, stdout="user", stderr="")
        with patch.dict(os.environ, {}, clear=True), patch.object(publish_vercel.Path, "home", return_value=home), patch.object(publish_vercel.platform, "system", return_value="Linux"):
            with patch.object(publish_vercel.subprocess, "run", side_effect=refresh) as command:
                assert publish_vercel.token() == "refreshed", "read auth.json only after whoami refreshes it"
                assert command.call_count == 1
            for failure in (SimpleNamespace(returncode=1, stdout="", stderr="expired"), OSError("missing CLI"), subprocess.TimeoutExpired("vercel", 60)):
                kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
                with patch.object(publish_vercel.subprocess, "run", **kwargs):
                    try:
                        publish_vercel.token()
                    except SystemExit as exc:
                        assert "vercel whoami" in str(exc) and "FAILED" in str(exc), str(exc)
                    else:
                        raise AssertionError("failed refresh must not read stale credentials")
            with patch.dict(os.environ, {"VERCEL_TOKEN": "explicit"}), patch.object(publish_vercel.subprocess, "run", side_effect=AssertionError("must skip whoami")):
                assert publish_vercel.token() == "explicit"


@case
def test_issue45_obsidian_excludes_and_refresh_scope():
    import auto_refresh
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        vault = home / "vault"
        for folder in ("tasks", "templates", "templates/sub", "templates-other", "marp", ".superpowers", ".obsidian", ".trash"):
            path = vault / folder
            path.mkdir(parents=True, exist_ok=True)
            (path / "note.md").write_text("- [ ] task in " + folder + "\n- [x] done in " + folder + "\n")
        source = {"path": str(vault), "exclude": ["templates", "marp", ".superpowers"]}
        inv = inventory(home, {"obsidian": [source]})
        code, facts = collect_build(home)
        note = facts["obsidian"][0]
        assert code == 0 and note["open"] == 2 and note["done"] == 2, note
        assert {x["file"] for x in note["items"]} == {"tasks/note.md", "templates-other/note.md"}
        before, failed = auto_refresh.fingerprints(home, inv)
        (vault / "templates/sub/note.md").write_text("".join(f"- [ ] changed excluded task {i}\n" for i in range(10)))
        after, failed2 = auto_refresh.fingerprints(home, inv)
        assert before == after and not failed and not failed2, "excluded notes must not trigger scheduled refresh"
        assert collect.obsidian_tasks(vault)["open"] == 15, "legacy source scans all non-internal Markdown files"
        for value in ("templates", ["../outside"], ["/absolute"], ["."], [4], ["C:/outside"]):
            source["exclude"] = value
            try:
                validation.validate_inventory(inv)
            except ValueError as exc:
                assert ".exclude" in str(exc), str(exc)
            else:
                raise AssertionError("invalid exclude accepted: " + repr(value))
        assert "which folders hold real tasks" in (S.parent / "SKILL.md").read_text()


def issue(number, state="OPEN", reason=None):
    return {"__typename": "Issue", "number": number, "title": "Issue " + str(number),
            "url": "https://github.com/o/r/issues/" + str(number), "state": state,
            "stateReason": reason, "createdAt": "2026-01-01T00:00:00Z",
            "closedAt": "2026-02-01T00:00:00Z" if state == "CLOSED" else None,
            "updatedAt": "2026-02-01T00:00:00Z"}


def issue_api(cmd, **kwargs):
    query = next(x for x in cmd if x.startswith("query="))
    assert "issues(first:" in query and "pullRequests" not in query, "PRs must not enter the ticket connection"
    second = "after=next" in cmd
    nodes = [issue(1), issue(2, "CLOSED", "COMPLETED")] if not second else [issue(3, "CLOSED", "NOT_PLANNED"), issue(4, "CLOSED")]
    return json.dumps({"data": {"repository": {"issues": {"nodes": nodes,
        "pageInfo": {"hasNextPage": not second, "endCursor": None if second else "next"}}}}})


@case
def test_issue46_github_tickets_counts_trend_and_opt_in():
    import auto_refresh
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        inv = inventory(home, {"github_issues": ["o/r", "o/other"]})
        with patch.object(collect, "run", side_effect=issue_api), patch.object(collect.shutil, "which", return_value="gh"):
            code, f = collect_build(home)
            assert code == 0 and len(f["tickets"]) == 8, "explicit GitHub Issues repos must supply all pages of tickets"
            assert not f["prs"]
            assert len({t["source_id"] for t in f["tickets"]}) == 8, "issue numbers collide across repos"
            assert {t["state"] for t in f["tickets"]} == {"open", "done", "dead"}
            canceled = next(t for t in f["tickets"] if t["state"] == "dead")
            assert canceled["canceled"] and not canceled.get("completed")
            page = (home / "out/index.html").read_text()
            import re
            p = json.loads(re.search(r"const D = (.*?);\n", page).group(1))["projects"][0]
            assert p["ticket_state"]["status"] == "ready" and p["counts"] == {"open":2,"done":4,"dead":2,"wait":0}, p["counts"]
            trend = p["trend_tickets"]
            assert trend["open"][-1] == 2 and trend["done"][-1] == 4 and trend["canceled"][-1] == 2
            assert trend["coverage"]["known"] == 8
            rendered = subprocess.run(["node", str(ROOT / "tests/html_collection.js")], input=page, text=True, capture_output=True, check=True)
            assert "Issue 1" in json.loads(rendered.stdout)[0]["tickets"]
            before, failures = auto_refresh.fingerprints(home, inv)
            assert not failures and any("github_issues:" in key for key in before["sources"])
        result = browser_check(home)
        assert result.returncode == 0, result.stdout + result.stderr
        # PR repo configuration must never opt in to tickets.
        inventory(home, {"github": ["o/r"]})
        with patch.object(collect, "gh_prs", return_value=[]), patch.object(collect.shutil, "which", return_value="gh"), patch.object(collect, "run", side_effect=AssertionError("unexpected issue access")):
            code, f = collect_build(home)
        assert code == 0 and not f["tickets"] and "github_issues:o/r" not in f["sources"]
        for value in ("o/r", ["invalid"], [4]):
            inv = inventory(home, {"github_issues": value})
            try:
                validation.validate_inventory(inv)
            except ValueError as exc:
                assert "github_issues" in str(exc)
            else:
                raise AssertionError("invalid GitHub Issues repos accepted")
        skill = (S.parent / "SKILL.md").read_text()
        assert "Linear / Notion / GitHub Issues / none" in skill and "github_issues" in skill


@case
def test_issue46_failed_page_empty_repo_and_missing_gh():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        inventory(home, {"github_issues": ["o/r"]})
        def denied(cmd, **kwargs):
            if "after=next" in cmd:
                raise RuntimeError("second page denied")
            return issue_api(cmd, **kwargs)
        with patch.object(collect, "run", side_effect=denied), patch.object(collect.shutil, "which", return_value="gh"):
            code, f = collect_build(home)
        assert code == 1 and not f["tickets"], "failed later page must not publish an incomplete current list"
        state = f["sources"]["github_issues:o/r"]
        assert state["status"] == "failed" and not state["complete"] and "second page denied" in state["error"]
        assert "failed" in (home / "out/index.html").read_text()
        empty = json.dumps({"data":{"repository":{"issues":{"nodes":[],"pageInfo":{"hasNextPage":False,"endCursor":None}}}}})
        with patch.object(collect, "run", return_value=empty), patch.object(collect.shutil, "which", return_value="gh"):
            code, f = collect_build(home)
        assert code == 0 and not f["tickets"] and f["sources"]["github_issues:o/r"]["complete"]
        with patch.object(collect.shutil, "which", return_value=None):
            code, f = collect_build(home)
        assert code == 1 and "gh" in f["sources"]["github_issues:o/r"]["error"]
        stuck = json.dumps({"data":{"repository":{"issues":{"nodes":[],"pageInfo":{"hasNextPage":True,"endCursor":"same"}}}}})
        for response in (stuck, '{"errors":[{"message":"denied"}]}'):
            with patch.object(collect, "run", return_value=response):
                try:
                    collect.gh_issues("o/r")
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("invalid or non-advancing issue pages accepted")


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn) and (len(sys.argv) == 1 or name in sys.argv[1:]):
            try:
                fn()
            except Exception as exc:
                failed += 1
                print(f"FAILED {name}: {type(exc).__name__}: {exc}", flush=True)
    print(("FAILED: " if failed else "OK: ") + summary() + f" ({failed} failed)")
    raise SystemExit(bool(failed))
