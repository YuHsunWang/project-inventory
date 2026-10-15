"""Print/install/remove one marked cron entry or Windows scheduled task (explicit opt-in)."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from collect import atomic_write
from plain_words import read_json


def marker(home):
    return "project-inventory-" + hashlib.sha256(str(home.resolve()).encode()).hexdigest()[:12]


def executable_path():
    paths = [str(Path.home() / ".local/bin"), str(Path.home() / "bin"), "/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"]
    paths += os.environ.get("PATH", "").split(os.pathsep)
    for command in ("git", "gh", "codex", "claude", "vercel"):
        found = shutil.which(command)
        if found:
            paths.append(str(Path(found).parent))
    return os.pathsep.join(dict.fromkeys(p for p in paths if p))


def cron_line(home, every=2, start=8, end=22):
    hours = ",".join(str(h) for h in range(start, end + 1, every))
    command = shlex.join([sys.executable, str(Path(__file__).with_name("auto_refresh.py").resolve()), str(home.resolve())])
    line = f"0 {hours} * * * PATH={shlex.quote(executable_path())} {command} >> {shlex.quote(str(home.resolve() / 'state' / 'schedule.log'))} 2>&1"
    return line.replace("%", r"\%") + " # " + marker(home)


def cron_update(content, home, line=None):
    kept = [row for row in content.splitlines() if not row.endswith(" # " + marker(home))]
    if line:
        kept.append(line)
    return "\n".join(kept).rstrip("\n") + ("\n" if kept else "")


def windows_command(home, action, every=2, start=8, end=22):
    if action == "remove":
        return ["schtasks", "/Delete", "/TN", marker(home), "/F"]
    task = subprocess.list2cmdline([sys.executable, str(Path(__file__).resolve()), "_run", str(home.resolve()), "--path", executable_path()])
    return ["schtasks", "/Create", "/TN", marker(home), "/SC", "DAILY", "/ST", f"{start:02}:00",
            "/RI", str(every * 60), "/DU", f"{end - start:02}:01", "/TR", task, "/F"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["print", "install", "remove", "_run"])
    parser.add_argument("home", nargs="?", default="~/.project-inventory")
    parser.add_argument("--every", type=int)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--crontab-file", type=Path, help="test/offline crontab file; never invokes crontab")
    parser.add_argument("--platform", choices=["unix", "windows"], default="windows" if os.name == "nt" else "unix")
    parser.add_argument("--path", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    home = Path(args.home).expanduser().resolve()
    if args.action == "_run":
        return subprocess.run([sys.executable, str(Path(__file__).with_name("auto_refresh.py")), str(home)],
                              env={**os.environ, "PATH": args.path or executable_path()}).returncode
    saved = read_json(home / "inventory.json").get("auto_refresh", {}).get("schedule") or {}
    every = args.every if args.every is not None else saved.get("every_hours", 2)
    start = args.start if args.start is not None else saved.get("start_hour", 8)
    end = args.end if args.end is not None else saved.get("end_hour", 22)
    if not (1 <= every <= 24 and 0 <= start <= end <= 23):
        parser.error("require 1 <= every <= 24 and 0 <= start <= end <= 23")
    command = windows_command(home, args.action, every, start, end) if args.platform == "windows" else None
    line = cron_line(home, every, start, end)
    print(subprocess.list2cmdline(command) if command else (line if args.action != "remove" else "remove entry marked " + marker(home)), flush=True)
    if args.action == "print":
        return 0
    if args.platform == "windows":
        subprocess.run(command, check=True, capture_output=True, text=True)
    else:
        if args.crontab_file:
            content = args.crontab_file.read_text(encoding="utf-8") if args.crontab_file.exists() else ""
        else:
            old = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if old.returncode and "no crontab for" not in old.stderr.lower():
                raise RuntimeError("cannot read crontab: " + old.stderr.strip())
            content = old.stdout
        updated = cron_update(content, home, line if args.action == "install" else None)
        if args.crontab_file:
            atomic_write(args.crontab_file, updated)
        else:
            subprocess.run(["crontab", "-"], input=updated, text=True, check=True)
    if args.action == "install":
        (home / "state").mkdir(parents=True, exist_ok=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"FAILED: schedule: {exc}")
