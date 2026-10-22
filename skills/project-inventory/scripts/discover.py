"""Deterministic, read-only Quick start discovery; JSON on stdout, no inventory writes.

    python3 discover.py [additional-folder ...] [--inventory-home HOME]

Depth is measured separately from every root (root=0). Dates are commit timestamps,
not filesystem mtimes or GitHub pushedAt. A missing tool or unreadable repo is nonfatal.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit


ROOT_NAMES = ("projects", "code", "src", "dev", "repos", "workspace")


def command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None


def github_repo(remote):
    """Normalize HTTPS, SSH and git GitHub remotes, without retaining credentials."""
    if remote.startswith("git@github.com:"):
        path = remote[len("git@github.com:"):]
    else:
        try:
            parsed = urlsplit(remote)
            if (parsed.hostname or "").lower() != "github.com":
                return None
            path = parsed.path.lstrip("/")
        except ValueError:
            return None
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path if re.fullmatch(r"[\w.-]+/[\w.-]+", path) else None


def recent(value, now):
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=dt.timezone.utc)
        return dt.timedelta(0) <= now - stamp <= dt.timedelta(days=90)
    except (ValueError, TypeError, AttributeError):
        return False


def local_repos(roots, inventory_home, warnings):
    found, visited = set(), set()
    for root in sorted(set(roots), key=str):
        if root.is_symlink():
            continue
        root = root.resolve()
        def walk(path, depth):
            # Revisit at a shallower depth when roots overlap, so each gets two levels.
            if path == inventory_home or inventory_home in path.parents or path.is_symlink():
                return
            visit = (path, depth)
            if visit in visited:
                return
            visited.add(visit)
            try:
                if (path / ".git").exists():  # worktrees use a .git file
                    found.add(path)
                if depth < 2:
                    for child in sorted(path.iterdir()):
                        if not child.name.startswith(".") and child.name != "node_modules" and child.is_dir():
                            walk(child, depth + 1)
            except OSError:
                warnings.append(f"Cannot scan folder: {path}")
        if root.is_dir():
            walk(root, 0)
    return sorted(found, key=str)


def discover(extra=(), inventory_home=None, *, home=None, cwd=None, now=None):
    home = Path(home or Path.home()).absolute()
    cwd = Path(cwd or Path.cwd()).absolute()
    inventory_home = Path(inventory_home or home / ".project-inventory").expanduser().resolve()
    roots = [cwd, home, *(home / name for name in ROOT_NAMES),
             *(Path(p).expanduser().absolute() for p in extra)]
    now = now or dt.datetime.now(dt.timezone.utc)
    warnings, projects = [], {}
    for path in local_repos(roots, inventory_home, warnings):
        # resolve after traversal: do not follow symlink directories while scanning.
        path = path.resolve()
        stamp = command(["git", "-C", str(path), "log", "--all", "-1", "--format=%cI"]) or None
        remotes = command(["git", "-C", str(path), "config", "--get-regexp", r"^remote\..*\.url$"]) or ""
        remotes = sorted((line.split(maxsplit=1) for line in remotes.splitlines()),
                         key=lambda pair: (pair[0] != "remote.origin.url", pair[0]))
        repo = next((repo for pair in remotes if len(pair) == 2 and (repo := github_repo(pair[1]))), None)
        key = "github:" + repo.lower() if repo else "local:" + str(path)
        row = projects.setdefault(key, {"name": path.name, "path": str(path), "paths": [],
                                        "last_commit": None, "github": repo, "has_issues": None})
        if str(path) not in row["paths"]:
            row["paths"].append(str(path))
        if stamp and (not row["last_commit"] or
                      dt.datetime.fromisoformat(stamp) > dt.datetime.fromisoformat(row["last_commit"])):
            row["last_commit"] = stamp
    available = command(["gh", "auth", "status"]) is not None
    metadata = {}
    if available:
        raw = command(["gh", "repo", "list", "--limit", "10000", "--json",
                       "name,nameWithOwner,hasIssuesEnabled"])
        try:
            entries = json.loads(raw) if raw is not None else None
            if not isinstance(entries, list):
                raise ValueError()
            for entry in entries:
                repo = entry["nameWithOwner"]
                if github_repo("https://github.com/" + repo):
                    metadata[repo.lower()] = entry
        except (ValueError, TypeError, KeyError):
            warnings.append("GitHub repository list unavailable; keeping local discoveries")
        # Local organization/collaborator repos may be absent from the account list.
        for row in list(projects.values()):
            repo = row["github"]
            if repo and repo.lower() not in metadata:
                raw = command(["gh", "repo", "view", repo, "--json", "name,nameWithOwner,hasIssuesEnabled"])
                try:
                    entry = json.loads(raw)
                    if isinstance(entry, dict) and entry.get("nameWithOwner", "").lower() == repo.lower():
                        metadata[repo.lower()] = entry
                    else:
                        raise ValueError()
                except (ValueError, TypeError):
                    warnings.append(f"GitHub metadata unavailable: {repo}")
        for key, entry in sorted(metadata.items()):
            repo = entry["nameWithOwner"]
            row = projects.setdefault("github:" + key, {"name": entry["name"], "path": None,
                                      "paths": [], "last_commit": None, "github": repo})
            row["has_issues"] = entry.get("hasIssuesEnabled") if isinstance(entry.get("hasIssuesEnabled"), bool) else None
            if not row["paths"]:
                raw = command(["gh", "api", f"repos/{repo}/commits?per_page=1"])
                try:
                    row["last_commit"] = json.loads(raw)[0]["commit"]["committer"]["date"]
                except (ValueError, TypeError, IndexError, KeyError):
                    warnings.append(f"GitHub last commit unavailable: {repo}")
    for row in projects.values():
        row["paths"].sort()
        row["selected"] = recent(row["last_commit"], now)
    return {"github_available": available,
            "projects": sorted(projects.values(), key=lambda p: (p["name"].casefold(), p["github"] or "", p["path"] or "")),
            "warnings": sorted(set(warnings))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="*", help="additional roots; default roots are always scanned")
    parser.add_argument("--inventory-home", help="inventory folder to exclude (default ~/.project-inventory)")
    args = parser.parse_args()
    print(json.dumps(discover(args.folders, args.inventory_home), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
