"""Check a built home in Chromium at 390/1280 px, in light and dark mode.

    python3 check_page.py HOME [--shots DIR]

Python stdlib only. Set CHROMIUM_BIN or install Chromium (a cached Playwright
Chromium also works). Missing browser is a failed check, never a successful skip.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import tempfile
import time
from urllib.parse import urlsplit


def chromium():
    configured = os.environ.get("CHROMIUM_BIN")
    if configured:
        return configured
    for name in ("chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    cache = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", Path.home() / ".cache/ms-playwright"))
    found = sorted(cache.glob("chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell"))
    if not found:
        found = sorted(cache.glob("chromium-*/chrome-linux*/chrome"))
    if found:
        return str(found[-1])
    raise RuntimeError("Chromium not found; install it or set CHROMIUM_BIN")


class CDP:
    """Small synchronous RFC6455 client for Chromium's local debugging socket."""
    def __init__(self, url):
        u = urlsplit(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\n"
                           f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                           "Sec-WebSocket-Version: 13\r\n\r\n").encode())
        header = b""
        while not header.endswith(b"\r\n\r\n"):
            header += self.read(1)
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if b" 101 " not in header or accept not in header:
            raise RuntimeError("Chromium websocket handshake failed")
        self.seq, self.session, self.errors = 0, None, []

    def read(self, n):
        data = b""
        while len(data) < n:
            part = self.sock.recv(n - len(data))
            if not part:
                raise RuntimeError("Chromium debugging socket closed")
            data += part
        return data

    def send(self, raw, opcode=1):
        mask = os.urandom(4)
        n = len(raw)
        header = bytes([0x80 | opcode, 0x80 | (n if n < 126 else 126 if n < 65536 else 127)])
        if n >= 126:
            header += struct.pack("!H" if n < 65536 else "!Q", n)
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(raw)))

    def receive(self):
        while True:
            first, second = self.read(2)
            n = second & 127
            if n == 126:
                n = struct.unpack("!H", self.read(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self.read(8))[0]
            mask = self.read(4) if second & 128 else None
            raw = self.read(n)
            if mask:
                raw = bytes(b ^ mask[i % 4] for i, b in enumerate(raw))
            if first & 15 == 9:
                self.send(raw, 10)
                continue
            if first & 15 == 8:
                raise RuntimeError("Chromium closed websocket")
            return json.loads(raw)

    def call(self, method, **params):
        self.seq += 1
        msg = {"id": self.seq, "method": method, "params": params}
        if self.session:
            msg["sessionId"] = self.session
        self.send(json.dumps(msg).encode())
        while True:
            response = self.receive()
            event = response.get("method")
            data = response.get("params", {})
            if event == "Runtime.exceptionThrown":
                self.errors.append("JS error: " + json.dumps(data["exceptionDetails"]))
            elif event == "Runtime.consoleAPICalled" and data.get("type") == "error":
                self.errors.append("console.error: " + json.dumps(data.get("args")))
            elif event == "Log.entryAdded" and data["entry"].get("level") == "error":
                self.errors.append("browser error: " + data["entry"].get("text", ""))
            if response.get("id") == self.seq:
                if "error" in response:
                    raise RuntimeError(str(response["error"]))
                return response.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in result:
            raise RuntimeError(str(result["exceptionDetails"]))
        return result.get("result", {}).get("value")

    def wait(self, expression, reason, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.evaluate(expression):
                return
            time.sleep(.05)
        raise RuntimeError("timeout: " + reason)

    def visible(self, selector):
        return self.evaluate(f"""(() => {{ const el = document.querySelector({json.dumps(selector)});
          if (!el) return false; const r = el.getBoundingClientRect(), s = getComputedStyle(el);
          return r.width > 0 && r.height > 0 && s.visibility === 'visible' && s.display !== 'none'
            && !!el.textContent.trim(); }})()""")

    def click(self, selector):
        point = self.evaluate(f"""(() => {{ const el = document.querySelector({json.dumps(selector)});
          if (!el) throw Error('Missing click target'); el.scrollIntoView({{block:'center'}});
          const r = el.getBoundingClientRect(), x = r.x + r.width/2, y = r.y + r.height/2;
          if (!r.width || !r.height || !el.contains(document.elementFromPoint(x,y)))
            throw Error('Click target hidden or covered: ' + {json.dumps(selector)});
          return {{x,y}}; }})()""")
        self.call("Input.dispatchMouseEvent", type="mousePressed", button="left", clickCount=1, **point)
        self.call("Input.dispatchMouseEvent", type="mouseReleased", button="left", clickCount=1, **point)

    def key(self, key, code, virtual):
        for kind in ("keyDown", "keyUp"):
            self.call("Input.dispatchKeyEvent", type=kind, key=key, code=code,
                      windowsVirtualKeyCode=virtual, nativeVirtualKeyCode=virtual,
                      text="\r" if kind == "keyDown" and key == "Enter" else "")

    def assets(self):
        self.evaluate("document.querySelectorAll('img').forEach(i => i.loading = 'eager')")
        self.wait("[...document.images].every(i => i.complete)", "images loaded")
        if self.evaluate("[...document.images].some(i => !i.naturalWidth)"):
            raise RuntimeError("image failed to load")
        self.evaluate("document.fonts.ready.then(() => true)")
        if self.evaluate("!!document.querySelector('script[src*=mathjax]')"):
            self.wait("!!window.MathJax?.startup?.promise", "MathJax startup")
            self.evaluate("MathJax.startup.promise.then(() => MathJax.typesetPromise()).then(() => true)")
        self.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    def overflow(self, where):
        if self.evaluate("document.documentElement.scrollWidth > innerWidth"):
            raise RuntimeError(where + ": horizontal overflow")

    def shot(self, directory, name):
        if directory:
            data = self.call("Page.captureScreenshot", captureBeyondViewport=True)["data"]
            (directory / (name + ".png")).write_bytes(base64.b64decode(data))


def check(c, page, expected, width, theme, shots):
    target = c.call("Target.createTarget", url="about:blank")["targetId"]
    c.session = c.call("Target.attachToTarget", targetId=target, flatten=True)["sessionId"]
    c.errors = []
    try:
        for domain in ("Page", "Runtime", "Log"):
            c.call(domain + ".enable")
        c.call("Page.bringToFront")
        c.call("Emulation.setFocusEmulationEnabled", enabled=True)
        c.call("Emulation.setDeviceMetricsOverride", width=width, height=900, deviceScaleFactor=1, mobile=False)
        c.call("Emulation.setEmulatedMedia", features=[{"name":"prefers-color-scheme", "value":theme},
                                                      {"name":"prefers-reduced-motion", "value":"reduce"}])
        c.call("Page.navigate", url=page.as_uri())
        c.wait("document.readyState === 'complete' && typeof D !== 'undefined'", "page loaded", seconds=60)
        c.assets()
        keys = c.evaluate("D.projects.map(p => p.key)")
        if not expected or keys != expected:
            raise RuntimeError(f"missing projects: expected {expected}, got {keys}")
        if not c.visible("#home"):
            raise RuntimeError("home not visible")
        c.overflow("home")
        c.shot(shots, f"home-{theme}-{width}")
        # Enter opens the project menu; Escape closes it and restores focus.
        c.evaluate("document.querySelector('#menubtn').focus()")
        c.key("Enter", "Enter", 13)
        c.wait("!document.querySelector('#menu').hidden", "keyboard opens menu")
        c.key("Escape", "Escape", 27)
        c.wait("document.querySelector('#menu').hidden && document.activeElement.id === 'menubtn'", "keyboard closes menu")
        for key in keys:
            c.click(f'#home a.drawer[href="#{key}"]')
            c.wait(f"!document.getElementById({json.dumps(key)})?.hidden", "project visible")
            section = f'section[id="{key}"]'
            tabs = c.evaluate(f"[...document.querySelectorAll({json.dumps(section + ' .subnav a')})].map(a => a.dataset.panel)")
            if not tabs:
                raise RuntimeError(key + ": missing tabs")
            for tab in tabs:
                c.click(section + f' .subnav a[data-panel="{tab}"]')
                panel = section + f' .panel[data-panel="{tab}"]'
                c.wait(f"location.hash === {json.dumps('#' + key + '/' + tab)} && !document.querySelector({json.dumps(panel)}).hidden", "tab navigation")
                if not c.visible(panel):
                    raise RuntimeError(key + "/" + tab + ": empty or invisible panel")
                c.assets()
                if tab == "tickets":
                    state = c.evaluate(f"D.projects.find(p => p.key === {json.dumps(key)}).ticket_state?.status")
                    if state and state != "ready":
                        notice = panel + f' [data-ticket-state="{state}"]'
                        if not c.visible(notice):
                            raise RuntimeError(key + ": ticket source state not visible: " + state)
                c.overflow(key + "/" + tab)
                if tab == "road":
                    count = c.evaluate(f"document.querySelectorAll({json.dumps(panel + ' .node')}).length")
                    for i in range(count):
                        node = panel + f' .node[data-id="' + str(c.evaluate(f"document.querySelectorAll({json.dumps(panel + ' .node')})[{i}].dataset.id")) + '"]'
                        detail = c.evaluate(f"document.querySelector({json.dumps(node)}).getAttribute('aria-controls')")
                        c.click(node)
                        c.assets()
                        if not c.visible(f'[id="{detail}"]'):
                            raise RuntimeError(key + ": step detail invisible")
                        c.overflow(key + "/step")
                        c.shot(shots, f"{key}-step-{i}-{theme}-{width}")
                        c.click(node)
                    if count:
                        node = panel + " .node"
                        c.evaluate(f"document.querySelector({json.dumps(node)}).focus()")
                        c.key("Enter", "Enter", 13)
                        if not c.evaluate(f"document.querySelector({json.dumps(node)}).getAttribute('aria-expanded') === 'true'"):
                            raise RuntimeError("keyboard did not open step")
                        c.key("Enter", "Enter", 13)
                c.shot(shots, f"{key}-{tab}-{theme}-{width}")
            c.evaluate("location.hash = ''")
            c.wait("!document.querySelector('#home').hidden", "return home")
        # Drain preceding asynchronous exception/console events before deciding.
        c.evaluate("true")
        if c.errors:
            raise RuntimeError("; ".join(c.errors))
    finally:
        c.session = None
        c.call("Target.closeTarget", targetId=target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("home", nargs="?", default="~/.project-inventory")
    parser.add_argument("--shots", type=Path)
    args = parser.parse_args()
    home = Path(args.home).expanduser().resolve()
    bad = []
    try:
        expected = [p["key"] for p in json.loads((home / "inventory.json").read_text())["projects"]]
        page = home / "out/index.html"
        if not page.is_file():
            raise RuntimeError("built page missing: " + str(page))
        if args.shots:
            args.shots.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="check-page-") as profile:
            with open(Path(profile) / "browser.log", "w+") as log:
                browser = subprocess.Popen([chromium(), "--headless", "--no-sandbox", "--disable-dev-shm-usage",
                    "--remote-debugging-port=0", "--user-data-dir=" + profile, "about:blank"], stdout=log, stderr=log)
                c = None
                try:
                    portfile = Path(profile) / "DevToolsActivePort"
                    deadline = time.monotonic() + 15
                    while not portfile.exists():
                        if browser.poll() is not None or time.monotonic() > deadline:
                            log.flush(); log.seek(0)
                            raise RuntimeError("Chromium could not start: " + log.read()[-1500:])
                        time.sleep(.05)
                    port, route = portfile.read_text().splitlines()[:2]
                    c = CDP(f"ws://127.0.0.1:{port}{route}")
                    for width in (390, 1280):
                        for theme in ("light", "dark"):
                            try:
                                check(c, page, expected, width, theme, args.shots)
                                print(f"{width}px {theme}: {len(expected)} projects checked", flush=True)
                            except (RuntimeError, OSError, ValueError) as e:
                                bad.append(f"{width}px {theme}: {e}")
                                print(bad[-1], flush=True)
                finally:
                    if c:
                        c.sock.close()
                    browser.terminate()
                    try:
                        browser.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        browser.kill()
                        browser.wait()
    except (RuntimeError, OSError, ValueError, KeyError) as e:
        bad.append(str(e))
    if bad:
        print("FAILED:\n" + "\n".join(bad))
    print("FAILED" if bad else "OK")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
