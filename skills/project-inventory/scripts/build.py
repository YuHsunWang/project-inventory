"""Turn inventory.json + the newest fact snapshot into one self-contained HTML page.

    python3 build.py <home>          # -> <home>/out/index.html and <home>/out/artifact.html

Screenshots named in a step's `media` are embedded in the page, so the one file works as a local
file, a claude.ai Artifact, on Vercel and on GitHub Pages.
"""
import base64, hashlib, re, datetime as dt, html as htmllib, json, mimetypes, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATES = ("wait", "open", "done", "dead")
MATHJAX = ('<script>window.MathJax = {tex:{inlineMath:[["\\\\(","\\\\)"]], displayMath:[["\\\\[","\\\\]"]]}, '
           'svg:{fontCache:"global"}, startup:{typeset:false}};</script>\n'
           '<script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-svg.min.js" defer></script>')
BIG = 8 * 2**20  # claude.ai Artifacts stop at 16 MB; warn well before that


def todos(p, f):
    """What waits on the owner. kind: pr / review / git / data / err. A checkout's git problems are one row."""
    k, out = p["key"], []
    if f["prs"]:
        out.append({"kind": "pr", "n": len(f["prs"]), "t": "prs", "go": f"#{k}/facts"})
    wait = [t for t in f["tickets"] if t.get("state") == "wait"]
    if wait:
        out.append({"kind": "review", "n": len(wait), "t": "review", "go": f"#{k}/tickets"})
    for r in f["repos"]:
        parts = []
        if r["dirty"]:
            parts.append([r["dirty"], "dirty"])
        if r["ahead"]:
            parts.append([r["ahead"], "unpushed"])
        if r["has_origin"] and not r["upstream"] and r["branch"] != "(detached)":
            parts.append([None, "no_upstream"])
        if parts:
            out.append({"kind": "git", "n": None, "where": r["label"], "parts": parts, "go": f"#{k}/facts"})
    stale = [d for d in f["data"] if d.get("stale")]
    if stale:
        out.append({"kind": "data", "n": len(stale), "t": "stale", "go": f"#{k}/facts"})
    if f["errors"]:
        out.append({"kind": "err", "n": len(f["errors"]), "t": "errors", "go": f"#{k}/facts"})
    return out


def ticket_series(tickets, today, days=90):
    """Per day: tickets done so far, and tickets open (created, not yet done or canceled).
    Rebuilt from the tickets' own dates, so the chart has history from the first run."""
    def end(t):  # a done/canceled ticket without its date stops counting as open from the day it was made
        return t.get("completed") or t.get("canceled") or (t.get("created") if t.get("state") in ("done", "dead") else None)
    out = {"days": [], "done": [], "open": []}
    for n in range(days - 1, -1, -1):
        d = (today - dt.timedelta(days=n)).isoformat()
        out["days"].append(d)
        out["done"].append(sum(1 for t in tickets if t.get("state") == "done" and (t.get("completed") or "9")[:10] <= d))
        out["open"].append(sum(1 for t in tickets if (t.get("created") or "9")[:10] <= d and not (end(t) or "9")[:10] <= d))
    return out


def now(f, today):
    """The facts behind the project's one-line status: last change, tickets done this week, waiting."""
    commits = {c["hash"]: c["date"] for r in f["repos"] for c in r["recent"]}
    last = max(commits.values(), default=None) or max((r["last_commit"][:10] for r in f["repos"] if r["last_commit"]), default=None)
    week = (today - dt.timedelta(days=7)).isoformat()
    return {"last": last, "c14": len(commits), "err": bool(f["errors"]),
            "done7": sum(1 for t in f["tickets"] if t.get("state") == "done" and (t.get("completed") or "") >= week),
            "wait": sum(1 for t in f["tickets"] if t.get("state") == "wait")}


def history(f, sums):
    """Everything that happened, newest week first: commits, finished tickets, PRs opened.
    Each week carries its plain-words summary from summaries.json; `fresh` is false when the
    summary is missing or was written for a different number of items (new work arrived)."""
    items = [{"date": c["date"], "kind": "commit", "text": c["subject"], "ref": c["hash"], "where": c.get("where")}
             for c in f.get("commits", [])]
    items += [{"date": t["completed"][:10], "kind": "done", "text": t["title"], "ref": t.get("id"), "url": t.get("url"),
               "note": t.get("benefit")} for t in f["tickets"] if t.get("state") == "done" and t.get("completed")]
    items += [{"date": pr["createdAt"][:10], "kind": "pr", "text": pr["title"], "ref": f'#{pr["number"]}', "url": pr["url"]}
              for pr in f["prs"] if pr.get("createdAt")]
    weeks = {}
    for x in sorted(items, key=lambda x: x["date"], reverse=True):
        d = dt.date.fromisoformat(x["date"])
        weeks.setdefault((d - dt.timedelta(days=d.weekday())).isoformat(), []).append(x)
    return [{"week": w, "items": its, "summary": (sums.get(w) or {}).get("text"),
             "fresh": (sums.get(w) or {}).get("n") == len(its)} for w, its in weeks.items()]


def embed_media(nodes, home, warn):
    """Screenshots -> data: URIs inside the page. A missing file is shown as missing, never dropped."""
    for n in nodes:
        for m in n.get("media", []):
            if "src" in m and not re.fullmatch(r"data:image/(?:png|jpeg|gif|webp);base64,[A-Za-z0-9+/]+={0,2}", str(m["src"])):
                m.pop("src")
                m["missing"] = "rejected unsafe image source"
                warn(f"step {n.get('id')}: rejected unsafe image source")
            if "shot" in m:
                path = Path(m.pop("shot")).expanduser()
                path = path if path.is_absolute() else home / path
                if path.is_file():
                    mime = mimetypes.guess_type(path.name)[0] or "image/png"
                    m["src"] = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
                else:
                    m["missing"] = str(path)
                    warn(f"step {n.get('id')}: screenshot not found: {path}")


def main():
    home = Path(sys.argv[1] if len(sys.argv) > 1 else "~/.project-inventory").expanduser()
    inv = json.loads((home / "inventory.json").read_text(encoding="utf-8"))
    snaps = sorted((home / "facts").glob("*.json"))
    if not snaps:
        sys.exit("FAILED: no snapshot in facts/ - run collect.py first")
    snap = json.loads(snaps[-1].read_text(encoding="utf-8"))
    today = dt.date.fromisoformat(snap["date"])
    sums_f = home / "summaries.json"
    sums = json.loads(sums_f.read_text(encoding="utf-8")) if sums_f.exists() else {}
    warnings, projects, need = [], [], {}
    for p in inv["projects"]:
        f = snap["projects"].get(p["key"])
        if f is None:
            sys.exit(f"FAILED: project {p['key']} is not in the newest snapshot - run collect.py again")
        on_node = {t: n["id"] for n in p.get("nodes", []) for t in n.get("tickets", [])}  # ticket id -> step
        f["tickets"] = [{**t, "node": t.get("node", on_node.get(t.get("id")))} for t in f["tickets"]]
        embed_media(p.get("nodes", []), home, lambda s, k=p["key"]: warnings.append(f"{k}: {s}"))
        src = p.get("sources") or {}
        has_tk = bool(f["tickets"] or src.get("linear") or src.get("notion"))
        projects.append({**p, "facts": f, "counts": {s: sum(t.get("state") == s for t in f["tickets"]) for s in STATES},
                         "todo": todos(p, f), "now": now(f, today), "history": history(f, sums.get(p["key"], {})),
                         "weekly": f.get("weekly") if f["repos"] else None,
                         "trend_tickets": ticket_series(f["tickets"], today) if has_tk else None})
    for p in projects:
        weeks = [{"week": w["week"], "n": len(w["items"]), "old": w["summary"],
                  "items": [f'{x["date"]} {x["kind"]}: {x["text"]}' for x in w["items"]]} for w in p["history"] if not w["fresh"]]
        if weeks:
            need[p["key"]] = weeks
    page = {"title": inv.get("title", "Projects"), "lang": inv.get("lang", "en"),
            "date": snap["date"], "generated_at": snap["generated_at"], "projects": projects}
    has_math = any("math" in m for p in projects for n in p.get("nodes", []) for m in n.get("media", []))
    html = (HERE / "template.html").read_text(encoding="utf-8")
    html = html.replace("__LANG__", htmllib.escape(page["lang"])).replace("__TITLE__", htmllib.escape(page["title"]))
    html = html.replace("<!--__MATHJAX__-->", MATHJAX if has_math else "")
    html = html.replace("/*__DATA__*/null", json.dumps(page, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--"))
    hashes = ["'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
              for s in re.findall(r"<script>(.*?)</script>", html, re.S)]
    csp = ("default-src 'none'; script-src " + " ".join(hashes) + " https://cdnjs.cloudflare.com; "
           "style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
           "img-src data:; object-src 'none'; base-uri 'none'; form-action 'none'")
    html = html.replace("__CSP__", htmllib.escape(csp, quote=True))
    out = home / "out" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    # claude.ai Artifact: the host adds doctype/html/head/body and the meta tags itself
    head = html.split("<head>", 1)[1].split("</head>", 1)[0]
    head = "\n".join(l for l in head.splitlines() if not l.lstrip().startswith("<meta"))
    body = html.split("<body>", 1)[1].rsplit("</body>", 1)[0]
    (out.parent / "artifact.html").write_text(head.strip() + "\n" + body.strip() + "\n", encoding="utf-8")
    size = len(html.encode())
    if size > BIG:
        warnings.append(f"page is {size / 2**20:.1f} MB (screenshots); a claude.ai Artifact stops at 16 MB - shrink or crop them")
    need_f = out.parent / "summaries-needed.json"
    if need:
        need_f.write_text(json.dumps(need, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"SUMMARIES {sum(map(len, need.values()))} weeks need a summary: {need_f}")
    else:
        need_f.unlink(missing_ok=True)
    for w in warnings:
        print(f"WARN {w}")
    print(f"built {out} ({size:,} bytes, {len(projects)} projects, snapshot {snap['date']})")


if __name__ == "__main__":
    main()
