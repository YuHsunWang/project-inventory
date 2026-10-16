"""Capture existing project UIs: python3 capture_shots.py HOME.

Only saved media.capture URLs/HTML files are opened; no servers or builds are started.
Python stdlib only; Chromium discovery and CDP are shared with check_page.py.
"""
import argparse
import base64
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import url2pathname

from check_page import CDP, chromium
from collect import atomic_write
from refresh_lock import refresh_lock, RefreshBusy
from validation import validate_inventory


def capture_url(value, home):
    parsed = urlsplit(value)
    if parsed.scheme in ("http", "https"):
        return value
    local = parsed.path
    if len(parsed.scheme) == 1:  # urlsplit treats a Windows drive letter as a scheme
        local = parsed.scheme + ":" + local
    path = Path(url2pathname(local)).expanduser()
    path = path if path.is_absolute() else home / path
    if not path.is_file():
        raise FileNotFoundError(f"HTML file not found: {path}")
    return urlsplit(path.resolve().as_uri())._replace(query=parsed.query, fragment=parsed.fragment).geturl()


def settle(c):
    """Wait at least 2s, then for 1s of stable resources/DOM; capture after 15s anyway."""
    deadline = time.monotonic() + 15
    time.sleep(2)
    expression = "[performance.getEntriesByType('resource').length, document.documentElement.outerHTML.length]"
    previous = c.evaluate(expression)
    quiet_since = time.monotonic()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(.25, remaining))
        current = c.evaluate(expression)
        now = time.monotonic()
        if current != previous:
            previous, quiet_since = current, now
        elif now - quiet_since >= 1:
            return


def screenshot(url):
    profile = tempfile.mkdtemp(prefix="capture-shots-")
    try:
        with open(Path(profile) / "browser.log", "w+") as log:
            browser = subprocess.Popen([chromium(), "--headless", "--no-sandbox", "--disable-dev-shm-usage",
                "--remote-debugging-port=0", "--user-data-dir=" + profile, "about:blank"], stdout=log, stderr=log)
            c = None
            try:
                portfile = Path(profile) / "DevToolsActivePort"
                deadline = time.monotonic() + 60
                while not portfile.exists():
                    if browser.poll() is not None or time.monotonic() > deadline:
                        log.flush(); log.seek(0)
                        raise RuntimeError("Chromium could not start: " + log.read()[-1500:])
                    time.sleep(.05)
                port, route = portfile.read_text().splitlines()[:2]
                c = CDP(f"ws://127.0.0.1:{port}{route}")
                target = c.call("Target.createTarget", url="about:blank")["targetId"]
                c.session = c.call("Target.attachToTarget", targetId=target, flatten=True)["sessionId"]
                c.call("Page.enable")
                c.call("Emulation.setDeviceMetricsOverride", width=1280, height=800,
                       deviceScaleFactor=1, mobile=False)
                result = c.call("Page.navigate", url=url)
                if result.get("errorText"):
                    raise RuntimeError(result["errorText"])
                c.wait("location.href !== 'about:blank' && document.readyState === 'complete'", "page loaded")
                status = c.evaluate("performance.getEntriesByType('navigation')[0]?.responseStatus || 0")
                if status >= 400:
                    raise RuntimeError(f"HTTP {status}")
                c.assets()
                settle(c)
                raw = base64.b64decode(c.call("Page.captureScreenshot", format="png")["data"], validate=True)
                if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Chromium returned no PNG")
                return raw
            finally:
                if c:
                    c.sock.close()
                browser.terminate()
                try:
                    browser.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    browser.kill(); browser.wait()
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def capture_shots(home, inv):
    """Caller holds the refresh lock. Capture failures are warnings, with last-good images retained."""
    changed = False
    for project in inv["projects"]:
        for node in project.get("nodes", []):
            number = 0
            for media in node.get("media", []):
                if "capture" not in media:
                    continue
                number += 1
                suffix = "" if number == 1 else f"-media{number}"
                relative = f"shots/{project['key']}-{node['id']}{suffix}.png"
                path = home / relative
                pending = None
                try:
                    raw = screenshot(capture_url(media["capture"], home))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if not path.exists() or path.read_bytes() != raw:
                        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pending-", delete=False) as f:
                            pending = Path(f.name)
                            f.write(raw)
                        pending.replace(path)
                    if media.get("shot") != relative:
                        media["shot"] = relative
                        changed = True
                    media["captured_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                    changed = True
                    print(f"CAPTURE {project['key']} step {node['id']}: {path} ({len(raw)} bytes)")
                except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
                    print(f"WARN {project['key']} step {node['id']}: capture failed: {exc}")
                finally:
                    if pending:
                        pending.unlink(missing_ok=True)
    if changed:
        try:
            atomic_write(home / "inventory.json", json.dumps(inv, ensure_ascii=False, indent=1))
        except OSError as exc:
            print(f"WARN capture: could not save inventory.json: {exc}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("home", type=Path)
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    try:
        with refresh_lock(home):
            inv = validate_inventory(json.loads((home / "inventory.json").read_text(encoding="utf-8")))
            capture_shots(home, inv)
    except RefreshBusy as exc:
        print(f"BUSY: {exc}")
    except (OSError, ValueError) as exc:
        print(f"FAILED: capture: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
