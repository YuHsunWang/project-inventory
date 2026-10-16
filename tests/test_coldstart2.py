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
