"""Create three fictional, offline projects with local history, tasks and data.

    python3 skills/project-inventory/reference/demo.py .tmp/demo
    python3 skills/project-inventory/scripts/collect.py .tmp/demo
    python3 skills/project-inventory/scripts/build.py .tmp/demo
"""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys


REFERENCE = Path(__file__).resolve().parent
COMMIT_DATES = ("2026-10-01T10:00:00+00:00", "2026-10-08T10:00:00+00:00",
                "2026-10-15T10:00:00+00:00")


def git(repo, *args, date=None):
    # Ignore machine identity, signing, hooks and templates; never configure a remote.
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "Sample Author", "GIT_AUTHOR_EMAIL": "sample@example.invalid",
           "GIT_COMMITTER_NAME": "Sample Author", "GIT_COMMITTER_EMAIL": "sample@example.invalid"}
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                    *args], cwd=repo, env=env, check=True, capture_output=True)


def main():
    home = Path(sys.argv[1]).expanduser().resolve()
    if (home / "inventory.json").exists():
        sys.exit("Refusing to overwrite an existing inventory home; use a new directory.")
    home.mkdir(parents=True, exist_ok=True)
    inventory = json.loads((REFERENCE / "example-inventory.json").read_text())
    fixtures = json.loads((REFERENCE / "demo-tasks.json").read_text())
    today = dt.datetime.now(dt.timezone.utc).date()
    summaries = {}
    for project in inventory["projects"]:
        fixture = fixtures[project["key"]]
        repo = home / project["sources"]["local"][0]["path"]
        # Refuse to repurpose a pre-existing sample checkout, too.
        repo.mkdir(parents=True)
        git(repo, "init", "-q", "--initial-branch=main", "--template=")
        (repo / "README.md").write_text("# " + project["name"] + "\n\n" + project["tag"] +
                                      "\n\nFictional sample only. No services or credentials.\n")
        for node in project["nodes"]:
            for relative in node["paths"]:
                path = repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(node["detail"] + "\n")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "Outline " + project["name"], date=COMMIT_DATES[0])

        for data in project["data"]:
            path = home / data["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            # Freshness follows UTC today; Git history always has the same dates/hashes.
            sample_day = today - dt.timedelta(days=10 if fixture["stale"] else 0)
            path.write_text("sample_id,created_at\n1," + sample_day.isoformat() + "\n2," + sample_day.isoformat() + "\n")
            data["path"] = str(path)
        # Keep clock-relative data outside Git so commit IDs remain deterministic.
        (repo / ".gitignore").write_text("data/\n")
        git(repo, "rm", "-q", "--cached", "-r", "--ignore-unmatch", "data")
        (repo / "notes/tasks.md").write_text("# Next review\n\n- [x] " + fixture["done"] +
                                            "\n" + "".join("- [ ] " + task + "\n" for task in fixture["open"]))
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "Prepare local samples and review checklist", date=COMMIT_DATES[1])
        (repo / "CHANGELOG.md").write_text("# Sample progress\n\n- Outline ready.\n- Local examples prepared.\n- Next review recorded in notes/tasks.md.\n")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "Record progress for the next review", date=COMMIT_DATES[2])
        summaries[project["key"]] = {}
        for date, text in zip(COMMIT_DATES, (
                "Outlined the steps for " + project["name"] + ".",
                "Prepared local samples and a review checklist.",
                "Recorded progress; the next decisions are in the notes tasks.")):
            day = dt.date.fromisoformat(date[:10])
            week = (day - dt.timedelta(days=day.weekday())).isoformat()
            summaries[project["key"]][week] = {"n": 1, "text": text}
        project["sources"]["local"][0]["path"] = str(repo)
        project["sources"]["obsidian"][0]["path"] = str(repo / "notes")
    (home / "summaries.json").write_text(json.dumps(summaries, indent=2) + "\n")
    (home / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    print("Created sample-only home: " + str(home))


if __name__ == "__main__":
    main()
