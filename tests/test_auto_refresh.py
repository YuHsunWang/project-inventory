"""Offline refresh regressions. Assertions name the behavior they guard; no live services."""
from contextlib import redirect_stdout
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch, Mock

from test_support import case, summary
S = Path(__file__).resolve().parents[1] / "skills/project-inventory/scripts"
sys.path.insert(0, str(S))
import auto_refresh as ar
import build
import collect
import plain_words as pw
import schedule
from refresh_lock import refresh_lock, RefreshBusy


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(root, model="none"):
    home = root / "home"
    save(home / "inventory.json", {"lang": "en", "auto_refresh": {"model": model}, "projects": [{"key": "p", "name": "Project", "sources": {}, "nodes": []}]})
    return home


def fake_refresh(home, args):
    snapshot = {"date": dt.date.today().isoformat(), "generated_at": dt.datetime.now().isoformat(), "run_id": "test", "projects": {"p": {"sources": {}, "errors": [], "commits": [], "prs": [], "tickets": [], "repos": [], "obsidian": [], "data": []}}}
    save(home / "facts/test.json", snapshot)
    save(home / "refresh.json", {"snapshot": str(home / "facts/test.json"), "run_id": "test", "status": "ok", "attempted_at": dt.datetime.now().isoformat()})
    (home / "out").mkdir(exist_ok=True)
    (home / "out/index.html").write_text("<html>page</html>")
    return 0


@case
def test_unchanged_has_no_collection_build_model_or_publish():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td), "claude")
        with patch.object(collect, "refresh", side_effect=fake_refresh) as refresh, patch.object(pw, "model_call") as model, patch.object(build, "build_page") as renderer, patch.object(ar, "publish") as publish:
            assert ar.run(home) == 0
            refresh.reset_mock(); model.reset_mock(); renderer.reset_mock(); publish.reset_mock()
            text = io.StringIO()
            with redirect_stdout(text):
                assert ar.run(home) == 0
            assert "UNCHANGED" in text.getvalue(), "equal fingerprints must take the fast exit"
            assert [m.call_count for m in (refresh, model, renderer, publish)] == [0, 0, 0, 0], "fast exit must precede every expensive stage"


@case
def test_failed_source_always_runs_and_builds_failure():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td))
        inv = pw.read_json(home / "inventory.json")
        inv["projects"][0]["data"] = [{"path": str(home / "missing.json"), "kind": "json", "column": "date"}]
        save(home / "inventory.json", inv)
        with patch.object(ar, "publish"), patch.object(pw, "model_call") as model:
            assert ar.run(home) == 1
            assert ar.run(home) == 1, "failed source must not be cached as unchanged"
            page = (home / "out/index.html").read_text()
            assert "missing.json" in page and '"error"' in page, "full run must expose the actual collection failure"
            assert not pw.read_json(home / "state/fingerprints.json")["cacheable"]
            model.assert_not_called()


@case
def test_manual_and_auto_share_lock_and_crashes_release_it():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td))
        with refresh_lock(home), patch.object(ar, "fingerprints") as probe:
            try:
                ar.run(home)
                assert False, "auto refresh must reject an existing lock"
            except RefreshBusy:
                pass
            probe.assert_not_called()
            result = subprocess.run([sys.executable, str(S / "collect.py"), str(home), "--refresh"], capture_output=True, text=True)
            assert result.returncode == 0 and "BUSY:" in result.stdout, "manual path must use the very same lock"
            assert not (home / "refresh.json").exists(), "busy manual refresh must not touch the run manifest"
            result = subprocess.run([sys.executable, str(S / "build.py"), str(home)], capture_output=True, text=True)
            assert result.returncode == 0 and "BUSY:" in result.stdout, "standalone manual build must also honor the lock"
            assert not (home / "out/index.html").exists(), "busy standalone build must not alter the page"
        with refresh_lock(home):
            pass
        child = subprocess.Popen([sys.executable, "-c", "from pathlib import Path; from refresh_lock import refresh_lock; import sys;\nwith refresh_lock(Path(sys.argv[1])):\n print('LOCKED', flush=True); sys.stdin.read()", str(home)], cwd=S, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            assert child.stdout.readline().strip() == "LOCKED"
            child.terminate(); child.wait(timeout=5)
            with refresh_lock(home):
                pass  # acquiring here proves no stale lock survives process death
        finally:
            if child.poll() is None:
                child.kill(); child.wait()


@case
def test_model_none_and_cache_only_send_missing_items():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td))
        inv = pw.read_json(home / "inventory.json")
        snap = {"projects": {"p": {"commits": [{"hash": "old", "subject": "CACHED SUBJECT"}, {"hash": "new", "subject": "NEW SUBJECT"}], "prs": [{"url": "https://example.com/pr/1", "title": "CACHED PR"}, {"url": "https://example.com/pr/2", "title": "NEW PR"}]}}}
        save(home / "state/notes.json", {"old": "Old note", "https://example.com/pr/1": "Old PR note"})
        with patch.object(pw, "model_call") as call:
            assert not pw.write_notes(home, inv, snap)
            call.assert_not_called()  # none must return before any model dispatch
        inv["auto_refresh"]["model"] = "claude"
        save(home / "out/summaries-needed.json", {"p": [{"week": "2026-10-12", "n": 2, "items": ["listed work"]}]})
        def reply(provider, prompt):
            payload = json.loads(prompt.split("\n", 1)[1])
            assert len(payload) == 3, "one batch must contain one week and only two uncached notes"
            assert "CACHED SUBJECT" not in prompt and "CACHED PR" not in prompt, "cached identities must never be sent again for notes"
            return {key: "A plain explanation." for key in payload}
        with patch.object(pw, "model_call", side_effect=reply) as call:
            assert pw.write_notes(home, inv, snap)
            assert call.call_count == 1, "only one batched call per project"
        notes = pw.read_json(home / "state/notes.json")
        assert notes["old"] == "Old note" and notes["new"] == "A plain explanation."
        assert notes["https://example.com/pr/2"] == "A plain explanation.", "PR notes must cache by full URL"
        assert pw.read_json(home / "summaries.json")["p"]["2026-10-12"]["n"] == 2, "summary must preserve build's item count"
        (home / "out/summaries-needed.json").unlink()
        with patch.object(pw, "model_call") as call:
            assert not pw.write_notes(home, inv, snap)
            call.assert_not_called()


@case
def test_first_run_is_batched_and_a_bad_batch_loses_only_itself():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td), "codex")
        inv = pw.read_json(home / "inventory.json")
        snap = {"projects": {"p": {"commits": [{"hash": f"c{i}", "subject": f"S{i}"} for i in range(90)], "prs": []}}}
        calls = []
        def reply(provider, prompt):
            payload = json.loads(prompt.split("\n", 1)[1])
            calls.append(len(payload))
            if len(calls) == 2:
                raise ValueError("broken JSON from the model")
            return {key: "A plain explanation." for key in payload}
        with patch.object(pw, "model_call", side_effect=reply):
            assert pw.write_notes(home, inv, snap)
        assert calls == [40, 40, 10], "a first run with hundreds of commits must not be one giant prompt"
        notes = pw.read_json(home / "state/notes.json")
        assert len(notes) == 50 and "c0" in notes and "c89" in notes and "c40" not in notes, "only the failed batch stays unwritten"


@case
def test_model_failure_and_language_validation():
    assert pw.valid_text("修好資料日期。", "zh-TW")
    assert not pw.valid_text("简体说明", "zh-TW"), "Big5 check must reject simplified-only characters"
    assert not pw.valid_text("English only", "zh-TW"), "Chinese page requires Chinese script"
    assert not pw.valid_text("中文說明", "en"), "English page rejects a Chinese reply"
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td), "codex")
        snap = {"projects": {"p": {"commits": [{"hash": "new", "subject": "Fix dates"}]}}}
        with patch.object(pw, "model_call", side_effect=RuntimeError("offline")):
            assert not pw.write_notes(home, pw.read_json(home / "inventory.json"), snap), "failed optional call must not abort refresh"
        assert not (home / "state/notes.json").exists(), "failed output must never enter the cache"


@case
def test_schedule_idempotent_fake_crontab_and_windows_command():
    with tempfile.TemporaryDirectory(prefix="inventory space ") as td:
        home = fixture(Path(td))
        table = Path(td) / "fake-crontab"
        table.write_text("5 1 * * * unrelated-job\n")
        argv = ["install", str(home), "--crontab-file", str(table), "--platform", "unix"]
        with redirect_stdout(io.StringIO()), patch.object(schedule.subprocess, "run", side_effect=AssertionError("real crontab forbidden")):
            schedule.main(argv); first = table.read_text(); schedule.main(argv)
            assert table.read_text() == first, "install must replace its marker, never duplicate"
            assert first.count(" # " + schedule.marker(home)) == 1
            assert "unrelated-job" in first and "auto_refresh.py" in first
            assert "0 8,10,12,14,16,18,20,22 * * * PATH=" in first, "default window is inclusive 08:00–22:00"
            schedule.main(argv + ["--every", "3"])
            assert "0 8,11,14,17,20 * * *" in table.read_text(), "custom cadence must replace the old line"
            schedule.main(["remove", str(home), "--crontab-file", str(table), "--platform", "unix"])
            assert table.read_text() == "5 1 * * * unrelated-job\n", "remove must preserve unrelated jobs"
        command = schedule.windows_command(home, "install")
        assert command[-1] == "/F" and command[command.index("/RI") + 1] == "120", "Windows install must replace the named task"
        assert command[command.index("/DU") + 1] == "14:01", "Windows repetition includes 22:00"
        assert "_run" in command[command.index("/TR") + 1] and "--path" in command[command.index("/TR") + 1], "Windows task must restore executable PATH"


@case
def test_publish_hash_skip_and_failed_deploy_retry():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td)); fake_refresh(home, None)
        inv = {"publish": {"to": "vercel", "project": "fixture", "team": "team_fixture"}}
        with patch.object(ar.subprocess, "run", return_value=Mock(returncode=0)) as deploy:
            ar.publish(home, inv); ar.publish(home, inv)
            assert deploy.call_count == 1, "equal deployed page hash must skip Vercel entirely"
            command = deploy.call_args.args[0]
            assert "publish_vercel.py" in command[1] and "--reuse" not in command, "automatic deploy must preserve publisher's ownership and protection checks"
            (home / "out/index.html").write_text("changed page")
            ar.publish(home, inv)
            assert deploy.call_count == 2, "a different page must deploy"
        receipt = (home / "state/deployed.json").read_text()
        (home / "out/index.html").write_text("third page")
        with patch.object(ar.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "mock")):
            try:
                ar.publish(home, inv)
                assert False, "failed deploy must propagate for retry"
            except subprocess.CalledProcessError:
                pass
        assert (home / "state/deployed.json").read_text() == receipt, "only a verified deploy can advance the hash"
        with patch.object(ar.subprocess, "run") as deploy:
            ar.publish(home, {"publish": {"to": "github-pages"}})
            ar.publish(home, {"publish": {"to": "artifact"}})
            deploy.assert_not_called()


@case
def test_fingerprints_cover_sources_and_day_and_failed_build():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); home = fixture(root)
        repo = root / "repo"; repo.mkdir()
        def git(*args):
            return subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com", *args], cwd=repo, check=True, capture_output=True)
        git("init", "-q"); git("commit", "-q", "--allow-empty", "-m", "initial")
        inv = pw.read_json(home / "inventory.json")
        inv["projects"][0]["sources"] = {"local": [{"path": str(repo), "label": "fixture"}], "github": ["fixture/repo"], "linear": {"project_id": "id"}}
        save(home / "inventory.json", inv)
        with patch.object(collect, "gh_prs", return_value=[{"number": 1, "updatedAt": "2026-10-12"}]), patch.object(collect, "linear_tickets", return_value=[]), patch.dict(os.environ, {"LINEAR_API_KEY": "fixture"}):
            first, errors = ar.fingerprints(home, inv)
            assert not errors and first["day"], "fingerprints must include the inventory calendar day"
            other = git("commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "other head").stdout.decode().strip()
            git("update-ref", "refs/heads/other", other)
            second, _ = ar.fingerprints(home, inv)
            assert first != second, "non-current local branch heads must invalidate the cache"
            (repo / "untracked").write_text("new")
            third, _ = ar.fingerprints(home, inv)
            assert third != second, "untracked count must invalidate the cache"
            with patch.object(collect, "gh_prs", return_value=[{"number": 1, "updatedAt": "2026-10-13"}]):
                fourth, _ = ar.fingerprints(home, inv)
                assert fourth != third, "PR updatedAt must invalidate even when number is unchanged"
        with patch.object(ar, "fingerprints", return_value=({"day": "today", "sources": {}}, [])), patch.object(collect, "refresh", return_value=2):
            assert ar.run(home) == 2
            assert not (home / "state/fingerprints.json").exists(), "fatal build/collection must never advance fingerprints"


@case
def test_needs_claude_banner_only_lists_allowed_work():
    inv = {"lang": "en", "publish": {"to": "artifact"}, "projects": [{"key": "p", "name": "<Project>"}]}
    snapshot = {"projects": {"p": {"sources": {"notion": {"status": "stale"}, "git:fixture": {"status": "failed"}, "github:fixture/repo": {"status": "ok", "complete": True}}}}}
    banner = build.needs_claude(inv, snapshot, {"p": [1, 2]})
    assert "Needs Claude" in banner and "&lt;Project&gt;" in banner
    assert banner.count("/project-inventory") == 3, "each MCP, missing-summary and Artifact row must give the exact command"
    assert "git:fixture" not in banner and "github:fixture/repo" not in banner, "banner excludes script failures and fresh sources"
    inv["lang"] = "zh-TW"
    assert "需要 Claude 協助" in build.needs_claude(inv, snapshot, {}), "banner labels must support zh-TW"


@case
def test_day_rollover_forces_run():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td))
        with patch.object(collect, "refresh", side_effect=fake_refresh) as refresh:
            ar.run(home)
            cache = pw.read_json(home / "state/fingerprints.json")
            cache["fingerprints"]["day"] = "2000-01-01"
            save(home / "state/fingerprints.json", cache)
            refresh.reset_mock()
            ar.run(home)
            assert refresh.call_count == 1, "date rollover must refresh moving week/date windows"


@case
def test_file_fingerprints_and_notes_are_rendered():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); home = fixture(root)
        vault = root / "vault"; vault.mkdir()
        assert ar.file_fingerprint(vault, "*.md") == [0, 0, 0], "an empty readable vault is a successful zero-file probe"
        (vault / "_notes.md").write_text("- [ ] task")
        before = ar.file_fingerprint(vault, "*.md")
        (vault / "_notes.md").write_text("- [x] completed task")
        assert before != ar.file_fingerprint(vault, "*.md"), "all Markdown that collect reads, including underscore names, must invalidate"
        data = root / "data.json"; data.write_text('{"date":"2000-01-01"}')
        first = ar.file_fingerprint(data)
        data.write_text('{"date":"2000-01-02","extra":true}')
        assert first != ar.file_fingerprint(data), "file size/mtime changes must invalidate a data check"
        fake_refresh(home, None)
        snap = pw.read_json(home / "facts/test.json")
        snap["projects"]["p"]["commits"] = [{"hash": "abc", "date": "2026-10-12", "subject": "Fix dates"}]
        save(home / "facts/test.json", snap)
        save(home / "state/notes.json", {"abc": "Correct the stored dates."})
        build.build_page(home)
        page = (home / "out/index.html").read_text()
        assert '"note": "Correct the stored dates."' in page, "cached notes must feed the existing history note UI"
        assert "Needs Claude" in page and "/project-inventory" in page, "a missing summary must show the actual top-page banner"


@case
def test_model_cli_contracts_without_running_any_cli():
    with patch.object(pw.subprocess, "run", return_value=Mock(returncode=0, stdout='{ "i0": "A note." }')) as call:
        assert pw.model_call("claude", "input") == {"i0": "A note."}
        argv = call.call_args.args[0]
        assert argv[:4] == ["claude", "-p", "--model", "claude-haiku-4-5-20251001"]
        assert argv[argv.index("--tools") + 1] == "" and "--strict-mcp-config" in argv and "--no-session-persistence" in argv, "Claude must disable tools, implicit MCP and persistent sessions"
        assert call.call_args.kwargs["input"] == "input", "prompt must go through stdin"
    def mock_codex(command, **kwargs):
        Path(command[command.index("-o") + 1]).write_text('{"i0":"A note."}')
        return Mock(returncode=0)
    with patch.object(pw.subprocess, "run", side_effect=mock_codex) as call:
        assert pw.model_call("codex", "input") == {"i0": "A note."}
        argv = call.call_args.args[0]
        assert argv[:4] == ["codex", "exec", "-m", "gpt-6-luna"]
        assert "model_reasoning_effort=max" in argv and argv[argv.index("-s") + 1] == "read-only"
        assert "--ephemeral" in argv and "--skip-git-repo-check" in argv and argv[-1] == "-", "Codex must remain ephemeral, read-only and isolated"


@case
def test_live_remote_refs_invalidate_without_fetching():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td))
        inv = pw.read_json(home / "inventory.json")
        inv["projects"][0]["sources"]["local"] = [{"label": "remote fixture", "path": str(home)}]
        remote = "old-ref"
        def git_command(command, **kwargs):
            if command == ["git", "remote"]:
                return "origin\n"
            if command == ["git", "ls-remote", "origin"]:
                return remote
            raise AssertionError("only read-only remote probes are allowed")
        with patch.object(ar, "local_git", side_effect=lambda path: {"refs": "local"}), patch.object(collect, "run", side_effect=git_command):
            before, errors = ar.fingerprints(home, inv)
            remote = "new-ref"
            after, _ = ar.fingerprints(home, inv)
            assert not errors and before != after, "live remote ref changes must invalidate even before local fetch"


@case
def test_screenshot_changes_invalidate_and_missing_is_cacheable():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); home = fixture(root)
        absolute = root / "absolute.png"
        inv = pw.read_json(home / "inventory.json")
        inv["projects"][0]["nodes"] = [
            {"id": 1, "media": [{"shot": "relative.png"}]},
            {"id": 2, "media": [{"shot": str(absolute)}]}]
        save(home / "inventory.json", inv)
        with patch.object(collect, "refresh", side_effect=fake_refresh) as refresh, patch.object(ar, "publish"):
            ar.run(home); ar.run(home)
            assert refresh.call_count == 1, "finding 1: missing screenshots are stable, successful fingerprints"
            for shot in (home / "relative.png", absolute):
                before = refresh.call_count
                shot.write_bytes(b"image")
                ar.run(home); ar.run(home)
                assert refresh.call_count == before + 1, "finding 1: every newly present relative/absolute screenshot invalidates once"
                stat = shot.stat()
                os.utime(shot, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
                ar.run(home)
                assert refresh.call_count == before + 2, "finding 1: replacement with the same size invalidates by mtime_ns"
                stat = shot.stat()
                shot.write_bytes(b"larger image")
                os.utime(shot, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                ar.run(home)
                assert refresh.call_count == before + 3, "finding 1: size changes invalidate even with the same mtime"
                shot.unlink()
                ar.run(home); ar.run(home)
                assert refresh.call_count == before + 4, "finding 1: deletion invalidates once, then missing is stable"


@case
def test_unfinished_model_outputs_retry_until_complete():
    for invalid_kind in ("commit", "week"):
        with tempfile.TemporaryDirectory() as td:
            home = fixture(Path(td), "claude")
            def refresh_with_history(home, args):
                fake_refresh(home, args)
                snap = pw.read_json(home / "facts/test.json")
                snap["projects"]["p"]["commits"] = [
                    {"hash": "c1", "subject": "Fix dates", "date": snap["date"]},
                    {"hash": "c2", "subject": "Fix counts", "date": snap["date"]}]
                save(home / "facts/test.json", snap)
                build.build_page(home)
                return 0
            attempts = []
            def reply(provider, prompt):
                payload = json.loads(prompt.split("\n", 1)[1])
                attempts.append(payload)
                if len(attempts) == 1:
                    raise RuntimeError("offline")
                if len(attempts) == 2:
                    return {token: ("" if item["kind"] == invalid_kind else "A plain explanation.")
                            for token, item in payload.items()}
                assert all(item["kind"] == invalid_kind for item in payload.values()), "successful outputs must stay cached during retries"
                return {token: "A plain explanation." for token in payload}
            with patch.object(collect, "refresh", side_effect=refresh_with_history) as refresh, patch.object(pw, "model_call", side_effect=reply) as model, patch.object(ar, "publish"):
                ar.run(home)
                assert not pw.read_json(home / "state/fingerprints.json")["cacheable"], "finding 2: failed calls must leave the run retryable"
                ar.run(home)
                assert not pw.read_json(home / "state/fingerprints.json")["cacheable"], "finding 2: invalid notes or summaries must leave partial success retryable"
                ar.run(home)
                assert pw.read_json(home / "state/fingerprints.json")["cacheable"], "finding 2: all requested outputs written permits caching"
                ar.run(home)
                assert refresh.call_count == model.call_count == 3, "finding 2: unchanged runs retry unfinished work, then stop after completion"


@case
def test_script_only_preserves_unconsumed_gather_for_manual_run():
    for consumed in (None, "previous-gather"):
        with tempfile.TemporaryDirectory() as td:
            home = fixture(Path(td))
            inv = pw.read_json(home / "inventory.json")
            inv["projects"][0]["sources"] = {"notion": {"url": "https://notion.so/fixture"}}
            save(home / "inventory.json", inv)
            today = dt.datetime.now(dt.timezone.utc).date().isoformat()
            stamp = dt.datetime.now(dt.timezone.utc).isoformat()
            offered = "fresh-gather"
            save(home / "gathered" / f"{today}.json", {"_run": {"run_id": offered}, "p": {
                "sources": {"notion": {"run_id": offered, "fetched_at": stamp, "status": "ok", "complete": True}}, "tickets": []}})
            if consumed:
                save(home / "facts" / f"{today}.json", {"run_id": "previous-auto", "gathered_run_id": consumed, "projects": {}})
            with patch.object(collect.shutil, "which", return_value=None):
                for _ in range(2):
                    code, path, run_id = collect.collect_snapshot(home, script_only=True)
                    snap = pw.read_json(path)
                    assert code == 1 and run_id != offered
                    assert snap["gathered_run_id"] == consumed, "finding 3: script-only runs preserve the previous consumed gather id"
                code, path, run_id = collect.collect_snapshot(home)
                snap = pw.read_json(path)
                assert code == 0 and run_id == offered and snap["projects"]["p"]["sources"]["notion"]["status"] == "ok", "finding 3: the next manual run must consume the fresh gather"
                assert snap["gathered_run_id"] == offered


@case
def test_git_probe_ignores_unreachable_secondary_remote():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td))
        inv = pw.read_json(home / "inventory.json")
        inv["projects"][0]["sources"]["local"] = [{"label": "fixture", "path": str(home)}]
        for remotes in ("origin\nbackup\n", "backup\n"):
            def git_command(command, **kwargs):
                if command == ["git", "remote"]:
                    return remotes
                if command == ["git", "ls-remote", "origin"]:
                    return "origin-ref"
                raise RuntimeError("secondary remote is unreachable")
            with patch.object(ar, "local_git", return_value={"refs": "local"}), patch.object(collect, "run", side_effect=git_command) as probe:
                current, errors = ar.fingerprints(home, inv)
                assert not errors, "finding 4: unused secondary remotes cannot fail fingerprints"
                expected = {"origin": "origin-ref"} if "origin" in remotes.splitlines() else {}
                assert current["sources"][f"p:git:{home}"]["remote_refs"] == expected, "finding 4: only origin is probed, and no-origin repositories remain supported"
                assert all(call.args[0] != ["git", "ls-remote", "backup"] for call in probe.call_args_list)


@case
def test_url_less_gathered_pr_builds_without_requesting_note():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td), "claude")
        inv = pw.read_json(home / "inventory.json")
        inv["projects"][0]["sources"]["github"] = ["fixture/repo"]
        save(home / "inventory.json", inv)
        today = dt.datetime.now(dt.timezone.utc).date().isoformat()
        stamp = dt.datetime.now(dt.timezone.utc).isoformat()
        prs = [{"repo": "fixture/repo", "number": 1, "title": "PR without URL", "createdAt": today},
               {"repo": "fixture/repo", "number": 2, "title": "PR with URL", "createdAt": today, "url": "https://example.com/pr/2"}]
        save(home / "gathered" / f"{today}.json", {"_run": {"run_id": "gather"}, "p": {
            "sources": {"github:fixture/repo": {"run_id": "gather", "fetched_at": stamp, "status": "ok", "complete": True}}, "prs": prs}})
        with patch.object(collect.shutil, "which", return_value=None):
            code, path, _ = collect.collect_snapshot(home)
        assert code == 0
        save(home / "state/notes.json", {"": "Wrong note", prs[1]["url"]: "Cached PR note."})
        build.build_page(home)
        page = (home / "out/index.html").read_text()
        assert "PR without URL" in page and "Cached PR note." in page and "Wrong note" not in page, "finding 5: URL-less gathered PRs must build and preserve valid PR notes"
        # Isolate note generation from the separate weekly-summary request.
        (home / "out/summaries-needed.json").unlink()
        (home / "state/notes.json").unlink()
        def reply(provider, prompt):
            payload = json.loads(prompt.split("\n", 1)[1])
            assert [item["title"] for item in payload.values()] == ["PR with URL"], "finding 5: URL-less PRs must never request a note"
            return {token: "A plain explanation." for token in payload}
        with patch.object(pw, "model_call", side_effect=reply) as model:
            assert pw.write_notes(home, inv, pw.read_json(path))
            assert model.call_count == 1
        assert pw.read_json(home / "state/notes.json") == {prs[1]["url"]: "A plain explanation."}, "finding 5: notes must only use valid URL identities"


@case
def test_schedule_remove_never_reads_inventory():
    with tempfile.TemporaryDirectory() as td:
        home = fixture(Path(td))
        table = Path(td) / "fake-crontab"
        unrelated = "5 1 * * * unrelated-job\n"
        for malformed in ('{broken JSON', '{"auto_refresh":{"schedule":{"every_hours":0}}}', '{"auto_refresh":null}'):
            (home / "inventory.json").write_text(malformed)
            table.write_text(unrelated + "0 8 * * * old-job # " + schedule.marker(home) + "\n")
            with redirect_stdout(io.StringIO()), patch.object(schedule, "read_json", side_effect=AssertionError("inventory must not be read")), patch.object(schedule, "executable_path", side_effect=AssertionError("removal needs only its marker")), patch.object(schedule.subprocess, "run") as task:
                assert schedule.main(["remove", str(home), "--crontab-file", str(table), "--platform", "unix"]) == 0
                assert table.read_text() == unrelated, "finding 6: remove must work with malformed inventory and preserve unrelated jobs"
                task.assert_not_called()
                assert schedule.main(["remove", str(home), "--platform", "windows"]) == 0
                assert task.call_args.args[0] == ["schtasks", "/Delete", "/TN", schedule.marker(home), "/F"], "finding 6: Windows removal must also use only the home-derived marker"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("OK: " + summary())
