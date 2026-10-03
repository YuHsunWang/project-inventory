"""Open the built page in headless Chromium and check it the way a person would use it.

    python3 check_page.py <home> [--shots <dir>]

Every project, every tab, every diagram step clicked, at 1280 px and 390 px wide.
Fails (exit 1) on a JS error, sideways scrolling, an empty tab, or a step whose panel does not open.
Needs: pip install playwright && python3 -m playwright install chromium
"""
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("SKIPPED: playwright not installed (pip install playwright && python3 -m playwright install chromium)")

args = sys.argv[1:]
shots = None
if "--shots" in args:
    i = args.index("--shots"); shots = Path(args[i + 1]); del args[i:i + 2]; shots.mkdir(parents=True, exist_ok=True)
page_file = (Path(args[0] if args else "~/.project-inventory").expanduser() / "out" / "index.html").resolve()

CLICK_ALL = """() => { const bad = [];
  for (const n of document.querySelectorAll('section.proj:not([hidden]) .node')) {
    n.click(); const p = document.getElementById(n.getAttribute('aria-controls'));
    if (!p || p.hidden || !p.textContent.trim()) bad.push(n.dataset.id);
    if (document.documentElement.scrollWidth > innerWidth) bad.push(n.dataset.id + ' scrolls sideways');
    n.click(); }
  return bad; }"""

bad, errs = [], []
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (1280, 390):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(page_file.as_uri()); pg.wait_for_timeout(500)
        if shots: pg.screenshot(path=str(shots / f"home-{w}.png"), full_page=True)
        for key in pg.evaluate("D.projects.map(p => p.key)"):
            tabs = pg.evaluate(f"[...document.getElementById({key!r}).querySelectorAll('.subnav a')].map(a => a.dataset.panel)")
            for tab in tabs:
                pg.evaluate(f"location.hash='{key}/{tab}'"); pg.wait_for_timeout(150)
                if not pg.inner_text(f"section[id='{key}'] .panel[data-panel={tab}]").strip():
                    bad.append(f"{w}px {key}/{tab}: empty")
                if pg.evaluate("document.documentElement.scrollWidth > innerWidth"):
                    bad.append(f"{w}px {key}/{tab}: scrolls sideways")
                if tab == "road":
                    bad += [f"{w}px {key} step {x}" for x in pg.evaluate(CLICK_ALL)]
                    if shots:
                        first = pg.query_selector("section.proj:not([hidden]) .node")
                        if first: first.click()
                        pg.screenshot(path=str(shots / f"{key}-{tab}-{w}.png"), full_page=True)
                        if first: first.click()
                elif shots:
                    pg.screenshot(path=str(shots / f"{key}-{tab}-{w}.png"), full_page=True)
            print(f"{w}px {key}: checked")
        pg.close()
    b.close()
bad += [f"JS error: {e}" for e in errs]
print("\n".join(["FAILED:"] + bad) if bad else "OK")
sys.exit(1 if bad else 0)
