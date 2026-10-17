"""Regenerate demo.gif from a fresh sample-only inventory, without service access.

    python3 skills/project-inventory/reference/demo_gif.py

Requires Pillow, Playwright and an installed Chromium (or CHROMIUM_BIN).
External browser requests are blocked; the page uses its fallback fonts.
"""
import argparse
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from check_page import chromium


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("demo.gif"))
    args = parser.parse_args()
    frames = []
    with tempfile.TemporaryDirectory(prefix="inventory-preview-") as td:
        home = Path(td) / "demo"
        for script in (Path(__file__).with_name("demo.py"), SCRIPTS / "collect.py", SCRIPTS / "build.py"):
            subprocess.run([sys.executable, str(script), str(home)], check=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chromium(), args=[
                "--no-sandbox", "--disable-dev-shm-usage", "--disable-background-networking",
                "--disable-component-update", "--disable-sync", "--no-first-run",
                "--host-resolver-rules=MAP * ~NOTFOUND",
            ])
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 900},
                                              color_scheme="light", reduced_motion="reduce",
                                              offline=True)
                context.route("**/*", lambda route: route.continue_()
                              if route.request.url.startswith(("file:", "data:")) else route.abort())
                page = context.new_page()
                page.goto((home / "out/index.html").as_uri())
                page.locator("#home").wait_for(state="visible")
                page.evaluate("document.fonts.ready")

                def capture():
                    page.evaluate("window.scrollTo(0, 0)")
                    page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                    with Image.open(BytesIO(page.screenshot())) as shot:
                        frames.append(shot.convert("RGB").quantize(colors=256))

                capture()
                page.locator('#home a.drawer[href="#myapp"]').click()
                project = page.locator('section[id="myapp"]')
                project.wait_for(state="visible")
                project.locator('.panel[data-panel="road"]').wait_for(state="visible")
                capture()
                node = project.locator('.panel[data-panel="road"] .node').first
                detail = node.get_attribute("aria-controls")
                node.click()
                page.locator('[id="' + detail + '"]').wait_for(state="visible")
                capture()
            finally:
                browser.close()
    output = BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:],
                   duration=[1800, 2200, 2200], loop=0, optimize=True, disposal=2)
    payload = output.getvalue()
    if len(payload) > 2_000_000:
        raise RuntimeError("Preview exceeds the 2 MB size limit")
    with Image.open(BytesIO(payload)) as preview:
        duration = 0
        for index in range(preview.n_frames):
            preview.seek(index)
            duration += preview.info["duration"]
        if preview.n_frames != 3 or duration > 8000:
            raise RuntimeError("Expected three distinct frames lasting at most eight seconds")
    args.output.write_bytes(payload)
    print(f"{args.output}: {len(payload)} bytes, 3 frames, {duration} ms")


if __name__ == "__main__":
    main()
