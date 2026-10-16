"""Screenshot capture contracts; real Chromium, local files and no project servers."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from test_support import case, summary

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "skills/project-inventory/scripts"
sys.path.insert(0, str(S))
import build
import collect
import validation


def fixture(home, media=None):
    inv = {"lang": "en", "projects": [{"key": "p", "name": "Project", "sources": {},
            "nodes": [{"id": 1, "title": "View", "media": media or []}]}]}
    (home / "inventory.json").write_text(json.dumps(inv))
    return inv


def capture(home, **env):
    return subprocess.run([sys.executable, str(S / "capture_shots.py"), str(home)],
                          capture_output=True, text=True, env=dict(os.environ, **env), timeout=100)


@case
def test_capture_local_html():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        page = home / "existing report.html"
        page.write_text("<!doctype html><title>Report</title><h1>Existing UI</h1>")
        fixture(home, [{"capture": page.name, "caption": "Report"}])
        result = capture(home)
        assert result.returncode == 0, result.stdout + result.stderr
        media = json.loads((home / "inventory.json").read_text())["projects"][0]["nodes"][0]["media"][0]
        shot = home / media["shot"]
        assert shot == home / "shots/p-1.png" and shot.stat().st_size > 1000
        assert build.checked_image(shot.read_bytes()) == "image/png"
        assert media["capture"] == page.name and media["caption"] == "Report"


@case
def test_capture_failure_keeps_previous_image_and_warns():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        shot = home / "shots/p-1.png"
        shot.parent.mkdir()
        shot.write_bytes(b"previous image")
        inv = fixture(home, [{"capture": "missing.html", "shot": "shots/p-1.png"}])
        before = (home / "inventory.json").read_bytes()
        result = capture(home)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "WARN" in result.stdout and "p" in result.stdout and "1" in result.stdout
        assert shot.read_bytes() == b"previous image", "failed capture must retain the last image"
        assert (home / "inventory.json").read_bytes() == before
        # Browser launch failure also cannot replace a user-supplied screenshot.
        (home / "existing.html").write_text("<h1>UI</h1>")
        inv["projects"][0]["nodes"][0]["media"][0]["capture"] = "existing.html"
        (home / "inventory.json").write_text(json.dumps(inv))
        result = capture(home, CHROMIUM_BIN=str(home / "absent-browser"))
        assert result.returncode == 0 and "WARN" in result.stdout, result.stdout + result.stderr
        assert shot.read_bytes() == b"previous image"


@case
def test_no_capture_or_shot_renders_no_screenshot_or_placeholder():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        fixture(home)
        before = (home / "inventory.json").read_bytes()
        result = capture(home, CHROMIUM_BIN=str(home / "absent-browser"))
        assert result.returncode == 0 and "WARN" not in result.stdout, result.stdout + result.stderr
        assert not (home / "shots").exists() and (home / "inventory.json").read_bytes() == before
        assert collect.collect_snapshot(home)[0] == 0
        for lang in ("en", "zh-TW"):
            inv = json.loads(before); inv["lang"] = lang
            (home / "inventory.json").write_text(json.dumps(inv))
            build.build_page(home)
            result = subprocess.run(["node", str(ROOT / "tests/html_collection.js")],
                                    input=(home / "out/index.html").read_text(), capture_output=True, text=True, check=True)
            rendered = json.loads(result.stdout)[0]["project"]
            assert "<img" not in rendered and 'class="tagx shot"' not in rendered
            assert all(text not in rendered.lower() for text in
                       ("image not found", "no screenshot", "找不到圖檔", "沒有截圖", "placeholder"))


@case
def test_failed_first_capture_adds_no_shot_and_continues():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "existing.html").write_text("<h1>Existing UI</h1>")
        fixture(home, [{"capture": "http://127.0.0.1:1/"}, {"capture": "existing.html"}])
        result = capture(home)
        assert result.returncode == 0 and "WARN" in result.stdout, result.stdout + result.stderr
        media = json.loads((home / "inventory.json").read_text())["projects"][0]["nodes"][0]["media"]
        assert "shot" not in media[0] and not (home / "shots/p-1.png").exists()
        assert media[1]["shot"] == "shots/p-1-media2.png", "multiple captures must not overwrite each other"
        assert (home / media[1]["shot"]).stat().st_size > 1000


@case
def test_capture_schema_validation():
    inv = {"projects": [{"key": "p", "name": "Project", "nodes": [{"id": 1, "media": [{}]}]}]}
    media = inv["projects"][0]["nodes"][0]["media"][0]
    for value in (None, False, 3, [], {}, "", "  ", "javascript:alert(1)", "ftp://example.com/a",
                  "https://", "https://user:secret@example.com", "script.py", "file://remote/a.html", "https://[bad", "file://[bad"):
        media["capture"] = value
        try:
            validation.validate_inventory(inv)
        except ValueError as exc:
            assert "projects[0].nodes[0].media[0].capture:" in str(exc), str(exc)
        else:
            raise AssertionError("invalid capture accepted: " + repr(value))
    for value in ("https://example.com/", "HTTPS://example.com/", "http://localhost:8080/", "docs/report.html", "/tmp/report.htm",
                  "~/report.html", "file:///tmp/report.html"):
        media["capture"] = value
        assert validation.validate_inventory(inv) == inv
    media.clear()  # legacy inventories require no migration
    assert validation.validate_inventory(inv) == inv


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except Exception as exc:
                failed += 1
                print(f"FAILED {name}: {type(exc).__name__}: {exc}", flush=True)
    print(("FAILED: " if failed else "OK: ") + summary() + f" ({failed} failed)")
    raise SystemExit(bool(failed))
