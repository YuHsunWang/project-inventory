"""Unattended refresh: python3 auto_refresh.py HOME. No chat session is started."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import collect
from capture_shots import capture_shots
from plain_words import read_json, write_notes
from refresh_lock import refresh_lock, RefreshBusy
from validation import validate_inventory, timezone
from step_refresh import rewrite_steps, revert_step

HERE = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def inventory_fingerprint(inv):
    # Capture time alone does not change the pixels or require rebuilding an unchanged page.
    config = json.loads(json.dumps(inv))
    for project in config["projects"]:
        for node in project.get("nodes", []):
            for media in node.get("media", []):
                media.pop("captured_at", None)
    return digest(config)


def file_fingerprint(path, pattern=None, exclude=()):
    path = Path(path).expanduser()
    if path.is_dir():
        def included(candidate):
            parts = candidate.relative_to(path).parts
            if pattern == "*.parquet":
                return not any(part.startswith((".", "_")) for part in parts)
            if pattern == "*.md":
                return not collect.obsidian_excluded(candidate, path, exclude)
            return True
        files = sorted(p for p in path.rglob(pattern or "*") if p.is_file() and included(p))
    else:
        files = [path]
        files += [sidecar for suffix in ("-wal", ".wal") if (sidecar := Path(str(path) + suffix)).exists()]
    if not files and pattern != "*.md":
        raise OSError("source has no matching files")
    stats = [p.stat() for p in files]
    return [len(stats), sum(s.st_size for s in stats), max((s.st_mtime_ns for s in stats), default=0)]


def screenshot_fingerprint(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return "missing"
    return [True, stat.st_size, stat.st_mtime_ns]


def local_git(path):
    def git(*args):
        return collect.run(["git", *args], cwd=Path(path).expanduser())
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    records = iter(status.split("\0"))
    dirty = untracked = 0
    for record in records:
        if not record:
            continue
        if record.startswith("??"):
            untracked += 1
        else:
            dirty += 1
            if "R" in record[:2] or "C" in record[:2]:
                next(records, None)  # porcelain -z follows a rename/copy with its old path
    return {"refs": git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/remotes"),
            "head": git("rev-parse", "HEAD"), "branch": git("symbolic-ref", "-q", "HEAD") if git("branch", "--show-current").strip() else "detached",
            "dirty": dirty, "untracked": untracked, "status": digest(status)}


def fingerprints(home, inv):
    sources, failed, probes = {}, [], {}
    def probe(key, call):
        probes[key] = call
    for project in inv["projects"]:
        key, src = project["key"], project.get("sources", {})
        for checkout in src.get("local", []):
            path = checkout["path"]
            def git_probe(path=path, fetch=checkout.get("fetch", True)):
                result = local_git(path)
                if not fetch:  # fetch:false never contacts the remote; local refs above are the fingerprint
                    return result
                remotes = collect.run(["git", "remote"], cwd=Path(path).expanduser()).splitlines()
                result["remote_refs"] = {remote: collect.run(["git", "ls-remote", remote], cwd=Path(path).expanduser()) for remote in remotes if remote == "origin"}
                return result
            probe(f"{key}:git:{path}", git_probe)
        for repo in src.get("github", []):
            probe(f"{key}:github:{repo}", lambda repo=repo: sorted([[p["number"], p["updatedAt"]] for p in collect.gh_prs(repo)]))
        for repo in src.get("github_issues", []):
            probe(f"{key}:github_issues:{repo}", lambda repo=repo: digest(sorted(collect.gh_issues(repo), key=lambda ticket: ticket["source_id"])))
        if src.get("linear") and os.environ.get("LINEAR_API_KEY"):
            probe(f"{key}:linear", lambda spec=src["linear"]: digest(sorted(collect.linear_tickets(spec), key=lambda ticket: ticket["source_id"])))
        for obsidian in src.get("obsidian", []):
            probe(f"{key}:obsidian:{obsidian['path']}", lambda o=obsidian: file_fingerprint(o["path"], "*.md", o.get("exclude", [])))
        for node in project.get("nodes", []):
            for media in node.get("media", []):
                if "shot" in media:
                    path = Path(media["shot"]).expanduser()
                    path = path if path.is_absolute() else home / path
                    probe(f"{key}:shot:{path}", lambda path=path: screenshot_fingerprint(path))
        for i, spec in enumerate(project.get("data", [])):
            probe(f"{key}:data:{i}", lambda spec=spec: file_fingerprint(spec["path"], "*.parquet" if spec["kind"] == "parquet" else None))
    probe("input:inventory.json", lambda: inventory_fingerprint(inv))
    # User edits and new MCP gathers must not be hidden behind an unchanged source cache.
    inputs = [home / "summaries.json", home / "state" / "notes.json", home / "state" / "steps.json", home / "step_history.json"]
    inputs += sorted((home / "gathered").glob("*.json"))
    for path in inputs:
        if path.exists():
            probe(f"input:{path.relative_to(home)}", lambda path=path: hashlib.sha256(path.read_bytes()).hexdigest())
    # Independent read-only probes overlap network latency, without starting any model.
    with ThreadPoolExecutor(max_workers=6) as pool:
        pending = {key: pool.submit(call) for key, call in probes.items()}
        for key, future in pending.items():
            try:
                sources[key] = future.result()
            except Exception as exc:
                failed.append(key)
                sources[key] = {"failed": type(exc).__name__}
                print(f"FINGERPRINT failed: {key}; full refresh required")
    return {"day": dt.datetime.now(timezone(inv.get("timezone", "UTC"))).date().isoformat(),
            "sources": sources}, failed


def publish(home, inv):
    spec = inv.get("publish", {})
    if spec.get("to") != "vercel":
        return
    page_hash = hashlib.sha256((home / "out" / "index.html").read_bytes()).hexdigest()
    receipt = home / "state" / "deployed.json"
    identity = {"project": spec.get("project"), "team": spec.get("team")}
    if read_json(receipt) == {**identity, "hash": page_hash}:
        print("PUBLISH unchanged; skipped")
        return
    if not spec.get("project"):
        raise ValueError("publish.project is required for automatic Vercel deployment")
    command = [sys.executable, str(HERE / "publish_vercel.py"), str(home), spec["project"]]
    if spec.get("team"):
        command += ["--team", spec["team"]]
    subprocess.run(command, check=True, timeout=1000)
    atomic_json(receipt, {**identity, "hash": page_hash})


def atomic_json(path, value):
    collect.atomic_write(path, json.dumps(value, ensure_ascii=False, indent=1))


def build_page_or_fail(home, manifest):
    import build
    try:
        build.build_page(home)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        message = f"FAILED: page build could not complete: {exc}. Fix the input or directory permissions and rerun auto_refresh.py HOME."
        manifest.update(status="fatal", error=message)
        try:
            atomic_json(home / "refresh.json", manifest)
        except OSError as record_error:
            print(f"FAILED: cannot record refresh failure: {record_error}", file=sys.stderr)
        build.mark_failed_page(home, manifest)
        print(message, file=sys.stderr)
        return False
    return True


def run(home):
    with refresh_lock(home):
        inv = validate_inventory(read_json(home / "inventory.json"))
        capture_shots(home, inv)
        current, failures = fingerprints(home, inv)
        cache = home / "state" / "fingerprints.json"
        previous = read_json(cache)
        if not failures and previous.get("cacheable") and previous.get("fingerprints") == current and (home / "out" / "index.html").exists():
            print("UNCHANGED: no collect/build/model/publish")
            return 0
        args = argparse.Namespace(run_id=None, refresh=False, script_only=True)
        code = collect.refresh(home, args)
        if code == 2:
            return 2
        manifest = read_json(home / "refresh.json")
        snapshot = read_json(Path(manifest["snapshot"]))
        rewrite_steps(home, inv)
        if not build_page_or_fail(home, manifest):
            return 2
        notes = write_notes(home, inv, snapshot)
        if notes and not build_page_or_fail(home, manifest):
            return 2
        publish(home, inv)
        # Collection may update tracking refs; generated text and step state are build inputs.
        for project in inv["projects"]:
            for checkout in project.get("sources", {}).get("local", []):
                key = f"{project['key']}:git:{checkout['path']}"
                if key not in failures:
                    current["sources"][key].update(local_git(checkout["path"]))
        current["sources"]["input:inventory.json"] = inventory_fingerprint(read_json(home / "inventory.json"))
        for path in [home / "summaries.json", home / "state" / "notes.json", home / "state" / "steps.json", home / "step_history.json"]:
            if path.exists():
                current["sources"][f"input:{path.relative_to(home)}"] = hashlib.sha256(path.read_bytes()).hexdigest()
        script_errors = []
        for project in inv["projects"]:
            facts = snapshot["projects"][project["key"]]
            for error in facts.get("errors", []):
                if error.startswith(("git ", "data ", "obsidian ", "github_issues:")) or (error.startswith("linear:") and os.environ.get("LINEAR_API_KEY")) or (error.startswith("github:") and any(state.get("via") == "gh" and state.get("status") != "ok" for name, state in facts.get("sources", {}).items() if name.startswith("github:"))):
                    script_errors.append(error)
        atomic_json(cache, {"fingerprints": current, "cacheable": not failures and not script_errors and not notes.pending})
        print("REFRESH complete" + (" (partial sources; see page)" if code else ""))
        return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("home", nargs="?", default="~/.project-inventory")
    parser.add_argument("--revert-step", nargs=2, metavar=("PROJECT_KEY", "STEP_ID"))
    args = parser.parse_args()
    try:
        home = Path(args.home).expanduser().resolve()
        if args.revert_step:
            with refresh_lock(home):
                revert_step(home, *args.revert_step)
            return 0
        return run(home)
    except RefreshBusy as exc:
        print(f"BUSY: {exc}")
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"FAILED: auto refresh: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
