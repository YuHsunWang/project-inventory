"""Issue #65: bounded discovery, explicit selection defaults and draft lifecycle."""
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

from test_support import case, summary

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "skills/project-inventory/scripts"
sys.path.insert(0, str(S))
import discover
from validation import validate_inventory

NOW = dt.datetime(2026, 10, 22, 12, tzinfo=dt.timezone.utc)


def marker(path):
    (path / ".git").mkdir(parents=True)
    return path


@case
def test_depth_skip_overlapping_roots_and_extra_folder():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        inv = home / "inventory"
        marker(home / "My App")
        marker(home / "group" / "Copper Stream")
        marker(home / "too" / "deep" / "Paper Grove")
        marker(home / "projects" / "group" / "Paper Grove")
        for path in (home / ".hidden" / "My App", home / "node_modules" / "My App", inv,
                     inv / "Copper Stream"):
            marker(path)
        (home / "alias").symlink_to(home / "My App", target_is_directory=True)
        # HOME's own .git is unrelated to inventory HOME and remains discoverable.
        (home / ".git").mkdir()
        with patch.object(discover, "command", return_value=None):
            result = discover.discover(home=home, cwd=home, inventory_home=inv, now=NOW)
        paths = {Path(p["path"]).relative_to(home).as_posix() for p in result["projects"]}
        assert paths == {".", "My App", "group/Copper Stream", "projects/group/Paper Grove"}, paths
        extra = home / "too" / "deep"
        with patch.object(discover, "command", return_value=None):
            result = discover.discover([extra, inv / "Copper Stream", inv / ".." / "inventory"], inv, home=home, cwd=home, now=NOW)
        assert all(inv not in Path(p["path"]).parents for p in result["projects"])
        assert any(p["path"] == str(extra / "Paper Grove") for p in result["projects"])


@case
def test_ninety_day_selection_boundary_not_push_or_mtime():
    for days, selected in ((0, True), (89, True), (90, True), (91, False), (-1, False)):
        stamp = (NOW - dt.timedelta(days=days)).isoformat()
        assert discover.recent(stamp, NOW) == selected
    assert not discover.recent(None, NOW)
    assert not discover.recent("unavailable", NOW)
    assert not discover.recent((NOW - dt.timedelta(days=90, seconds=1)).isoformat(), NOW)


@case
def test_github_merge_checkout_paths_and_issues_metadata():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        for name in ("My App", "Copper Stream", "Paper Grove"):
            marker(home / name)
        calls = []
        def command(args):
            calls.append(args)
            if args[:3] == ["gh", "auth", "status"]:
                return ""
            if args[:3] == ["gh", "repo", "list"]:
                return json.dumps([{"name": "My App", "nameWithOwner": "sample/My-App", "hasIssuesEnabled": True},
                                   {"name": "Copper Stream", "nameWithOwner": "sample/Copper-Stream", "hasIssuesEnabled": False}])
            if args[0] == "git":
                if "log" in args:
                    return NOW.isoformat()
                if Path(args[2]).name == "Paper Grove":
                    return "remote.upstream.url ssh://git@github.com/sample/Paper-Grove.git"
                return "remote.origin.url git@github.com:sample/My-App.git"
            if args[:3] == ["gh", "repo", "view"]:
                return json.dumps({"name": "Paper Grove", "nameWithOwner": "sample/Paper-Grove", "hasIssuesEnabled": False})
            if args[:2] == ["gh", "api"]:
                return json.dumps([{"commit": {"committer": {"date": (NOW - dt.timedelta(days=91)).isoformat()}}}])
            raise AssertionError(args)
        with patch.object(discover, "command", side_effect=command):
            result = discover.discover(home=home, cwd=home, now=NOW)
        assert result["github_available"] and len(result["projects"]) == 3, result
        rows = {p["github"]: p for p in result["projects"]}
        merged = rows["sample/My-App"]
        assert len(merged["paths"]) == 2 and merged["has_issues"] is True and merged["selected"]
        remote = rows["sample/Copper-Stream"]
        assert remote["path"] is None and remote["paths"] == [] and not remote["selected"]
        assert remote["has_issues"] is False
        assert rows["sample/Paper-Grove"]["has_issues"] is False
        assert sum(args[:3] == ["gh", "repo", "list"] for args in calls) == 1
        for url in ("https://user:secret@github.com/sample/My-App.git", "ssh://git@github.com/sample/My-App.git"):
            assert discover.github_repo(url) == "sample/My-App"
        assert discover.github_repo("https://gitlab.com/sample/My-App") is None


@case
def test_missing_gh_and_failed_listing_keep_local_results():
    with patch.object(discover.subprocess, "run", side_effect=FileNotFoundError):
        assert discover.command(["gh", "auth", "status"]) is None
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        marker(home / "My App")
        for authenticated in (False, True):
            def command(args):
                return "" if authenticated and args == ["gh", "auth", "status"] else None
            with patch.object(discover, "command", side_effect=command):
                result = discover.discover(home=home, cwd=home, now=NOW)
            assert len(result["projects"]) == 1 and not result["projects"][0]["selected"]
            assert result["github_available"] == authenticated
            assert bool(result["warnings"]) == authenticated


@case
def test_draft_validation_and_renderer_all_languages():
    inv = {"projects": [{"key": "app", "name": "My App", "nodes": [{"id": 1}]}]}
    node = inv["projects"][0]["nodes"][0]
    validate_inventory(inv)  # existing inventory needs no draft field
    for value in (True, False):
        node["draft"] = value
        validate_inventory(inv)
    for value in (None, "true", 1, [], {}):
        node["draft"] = value
        try:
            validate_inventory(inv)
        except ValueError as error:
            assert "projects[0].nodes[0].draft: expected bool" in str(error)
        else:
            raise AssertionError(f"draft accepted {value!r}")
    result = subprocess.run(["node", str(ROOT / "tests/html_draft.js")],
                            input=(S / "template.html").read_text(), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    print(result.stdout.strip())


@case
def test_quick_start_real_isolated_home():
    """One selection response (all three) -> defaults, collect/build and real rendered labels."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        inv_home = home / ".project-inventory"
        env = {**os.environ, "HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
        # Only git on PATH: prove the CLI succeeds when gh is genuinely absent.
        bin_dir = home / "bin"
        bin_dir.mkdir()
        (bin_dir / "git").symlink_to(shutil.which("git"))
        env["PATH"] = str(bin_dir)
        flow = ('from pathlib import Path\n'
                'def main():\n'
                '    raw = Path("input.txt").read_text()\n'
                '    lines = raw.splitlines()\n'
                '    clean = [line.strip() for line in lines]\n'
                '    kept = [line for line in clean if line]\n'
                '    Path("output.txt").write_text("\\n".join(kept))\n'
                'if __name__ == "__main__":\n'
                '    main()\n')
        for name, days in (("My App", 1), ("Copper Stream", 30), ("Paper Grove", 120)):
            repo = home / "projects" / name
            repo.mkdir(parents=True)
            (repo / "README.md").write_text(f"# {name}\nmain.py reads input.txt, splits lines, strips whitespace, removes blank lines, writes output.txt.\n")
            (repo / "main.py").write_text(flow)
            stamp = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
            git_env = {**env, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
            for args in (["init", "-q"], ["add", "README.md", "main.py"], ["commit", "-qm", "Add documented text flow"]):
                result = subprocess.run(["git", "-c", "user.name=Example", "-c", "user.email=example@example.com", *args],
                                        cwd=repo, env=git_env, text=True, capture_output=True)
                assert result.returncode == 0, result.stderr
        result = subprocess.run([sys.executable, str(S / "discover.py"), "--inventory-home", str(inv_home)],
                                cwd=home, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        discovery = json.loads(result.stdout)
        assert len(discovery["projects"]) == 3 and not discovery["github_available"], discovery
        assert {p["name"]: p["selected"] for p in discovery["projects"]} == {
            "My App": True, "Copper Stream": True, "Paper Grove": False}
        print("DISCOVERY " + json.dumps(discovery, ensure_ascii=False, sort_keys=True))
        # Fixture's one answer selects all three, including the unchecked older repo.
        projects = []
        titles = ("Read input", "Split lines", "Strip whitespace", "Remove blank lines", "Write output")
        for row, color in zip(discovery["projects"], ("#C4452C", "#287A69", "#6856A3")):
            repo = Path(row["path"])
            assert "main.py" in (repo / "README.md").read_text()
            assert "def main():" in (repo / "main.py").read_text()
            projects.append({"key": row["name"].lower().replace(" ", "-"), "name": row["name"], "color": color,
                             "sources": {"local": [{"label": Path(p).name, "path": p} for p in row["paths"]]},
                             "data": [], "nodes": [{"id": i, "title": title, "icon": "gear", "paths": ["main.py"], "draft": True}
                                                    for i, title in enumerate(titles, 1)]})
        inv = {"lang": "zh-TW", "auto_refresh": {"model": "none"}, "publish": {"to": "local"}, "projects": projects}
        validate_inventory(inv)
        inv_home.mkdir()
        (inv_home / "inventory.json").write_text(json.dumps(inv, ensure_ascii=False))
        print('DEFAULTS {"auto_refresh":{"model":"none"},"publish":{"to":"local"},"data":[],"writing_skill":"absent","schedule":"absent","screenshots":"absent"}')
        for script, args in (("collect.py", ["--refresh"]), ("build.py", [])):
            result = subprocess.run([sys.executable, str(S / script), str(inv_home), *args],
                                    cwd=home, env=env, text=True, capture_output=True)
            assert result.returncode == 0, result.stdout + result.stderr
        page = (inv_home / "out/index.html").read_text()
        result = subprocess.run(["node", str(ROOT / "tests/html_draft.js"), "--built"],
                                input=page, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        print(result.stdout.strip())
        assert json.loads((inv_home / "inventory.json").read_text()) == inv
        for lang, label in (("en", "AI draft"), ("zh-TW", "AI 草稿")):
            assert label in page


if __name__ == "__main__":
    for test in (test_depth_skip_overlapping_roots_and_extra_folder,
                 test_ninety_day_selection_boundary_not_push_or_mtime,
                 test_github_merge_checkout_paths_and_issues_metadata,
                 test_missing_gh_and_failed_listing_keep_local_results,
                 test_draft_validation_and_renderer_all_languages,
                 test_quick_start_real_isolated_home):
        test()
    print("OK: " + summary())
