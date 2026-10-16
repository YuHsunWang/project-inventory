"""Regressions for cold-start issues 48–49; fake data and repo-local homes only."""
from contextlib import redirect_stdout
import io
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from test_support import case, summary

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "skills/project-inventory/scripts"
sys.path.insert(0, str(S))
import build, collect, validation


@case
def test_issue48_blank_obsidian_checkboxes_collect_and_validate():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        vault = home / "vault"
        vault.mkdir()
        (vault / "tasks.md").write_text("- [ ]\n- [x]\n- [ ]   \n- [x] \t\n- [X]   \n- [ ] Buy milk\n")
        inv = {"lang": "en", "projects": [{"key": "app", "name": "My App",
               "sources": {"obsidian": [{"path": str(vault)}]}, "nodes": []}]}
        (home / "inventory.json").write_text(json.dumps(inv))
        with redirect_stdout(io.StringIO()):
            code, snapshot, _ = collect.collect_snapshot(home)
            build.build_page(home)
        facts = validation.validate_snapshot(json.loads(snapshot.read_text()), inv)
        note = facts["projects"]["app"]["obsidian"][0]
        assert code == 0 and note["open"] == 1 and note["done"] == 0, note
        assert note["total"] == note["shown"] == 1
        assert note["items"] == [{"text": "Buy milk", "file": "tasks.md", "line": 6}]
        note["items"][0]["text"] = ""
        try:
            validation.validate_snapshot(facts, inv)
        except ValueError as exc:
            assert ".text" in str(exc), str(exc)
        else:
            raise AssertionError("snapshot validation must still reject empty task text")


def build_ticket_page(home, lang, sources):
    inv = {"lang": lang, "projects": [
        {"key": "app", "name": "My App", "sources": sources, "nodes": []},
        {"key": "other", "name": "My Other App", "sources": {}, "nodes": []},
        {"key": "empty", "name": "My Empty App", "sources": {"github_issues": []}, "nodes": []}]}
    (home / "inventory.json").write_text(json.dumps(inv))
    with patch.dict(os.environ, {"LINEAR_API_KEY": ""}), patch.object(collect, "gh_issues", return_value=[]), patch.object(collect.shutil, "which", return_value="gh"), redirect_stdout(io.StringIO()):
        collect.collect_snapshot(home)
        build.build_page(home)
    return (home / "out/index.html").read_text()


def rendered_page(page):
    result = subprocess.run(["node", str(ROOT / "tests/html_collection.js")], input=page,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


@case
def test_issue49_configured_ticket_sources_in_built_page():
    providers = {"linear": {"project": "My App"}, "notion": {"url": "https://example.com/tasks"},
                 "github_issues": ["example/my-app"]}
    for lang in ("zh-TW", "en"):
        for names in (("github_issues",), (), ("linear",), ("notion",), tuple(providers)):
            with tempfile.TemporaryDirectory() as td:
                home = Path(td)
                page = build_ticket_page(home, lang, {key: providers[key] for key in names})
                labels = {"linear": "Linear", "notion": "Notion", "github_issues": "GitHub Issues"}
                for name, label in labels.items():
                    if name not in names:
                        for output in ("index.html", "artifact.html"):
                            assert label not in (home / "out" / output).read_text(), (lang, names, output, label)
                rows = rendered_page(page)
                prefix = "待辦：" if lang == "zh-TW" else "Tickets: "
                empty = "未設定待辦來源" if lang == "zh-TW" else "No ticket source set."
                for row in rows[1:]:
                    assert empty in row["tickets"], row["tickets"]
                assert (prefix in rows[0]["footer"]) == bool(names), rows[0]["footer"]
                for name, label in labels.items():
                    assert (label in rows[0]["footer"]) == (name in names), rows[0]["footer"]
                    assert (label in rows[0]["facts"]) == (name in names), rows[0]["facts"]
                    for row in rows[1:]:
                        assert label not in row["facts"], row["facts"]
                if "github_issues" in names:
                    hint = rows[0]["facts"].split("</p>", 1)[0]
                    assert "GitHub Issues" in hint, hint


@case
def test_issue49_empty_progress_has_no_chart_scaffolding():
    with tempfile.TemporaryDirectory() as td:
        page = build_ticket_page(Path(td), "en", {})
        empty = rendered_page(page)[1]
        assert 'class="trends"' not in empty["trends"], empty["trends"]
        assert "Hover a chart" not in empty["trends"], empty["trends"]
        assert '<div class="card"></div>' not in empty["history"], empty["history"]
        assert 'data-git-state="not_connected"' in empty["history"], empty["history"]


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
