"""Turn inventory.json + the fact snapshots into one self-contained HTML page.

    python3 build.py <home>          # -> <home>/out/index.html

Uses the newest snapshot in <home>/facts/ for the page and every snapshot for the trend lines.
"""
import datetime as dt, html as htmllib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATES = ("wait", "open", "done", "dead")


def todos(p, f):
    """What waits on the owner. kind: pr / review / git / data / err."""
    k, out = p["key"], []
    if f["prs"]:
        out.append({"kind": "pr", "n": len(f["prs"]), "t": "prs", "go": f"#{k}/facts"})
    wait = [t for t in f["tickets"] if t.get("state") == "wait"]
    if wait:
        out.append({"kind": "review", "n": len(wait), "t": "review", "go": f"#{k}/tickets"})
    for r in f["repos"]:
        if r["dirty"]:
            out.append({"kind": "git", "n": r["dirty"], "t": "dirty", "where": r["label"], "go": f"#{k}/facts"})
        if r["ahead"]:
            out.append({"kind": "git", "n": r["ahead"], "t": "unpushed", "where": r["label"], "go": f"#{k}/facts"})
        if r["has_origin"] and not r["upstream"] and r["branch"] != "(detached)":
            out.append({"kind": "git", "n": None, "t": "no_upstream", "where": r["label"], "go": f"#{k}/facts"})
    stale = [d for d in f["data"] if d.get("stale")]
    if stale:
        out.append({"kind": "data", "n": len(stale), "t": "stale", "go": f"#{k}/facts"})
    if f["errors"]:
        out.append({"kind": "err", "n": len(f["errors"]), "t": "errors", "go": f"#{k}/facts"})
    return out


def activity(f, today):
    since = (today - dt.timedelta(days=14)).isoformat()
    seen, items = set(), []
    for r in f["repos"]:
        for c in r["recent"]:
            if c["hash"] not in seen:
                seen.add(c["hash"])
                items.append({"date": c["date"], "kind": "commit", "text": c["subject"], "ref": c["hash"], "where": r["label"]})
    for t in f["tickets"]:
        if t.get("state") == "done" and (t.get("completed") or "") >= since:
            items.append({"date": t["completed"][:10], "kind": "done", "text": t["title"], "ref": t.get("id"), "url": t.get("url")})
    for pr in f["prs"]:
        if pr.get("createdAt", "") >= since:
            items.append({"date": pr["createdAt"][:10], "kind": "pr", "text": pr["title"], "ref": f'#{pr["number"]}', "url": pr["url"]})
    return sorted(items, key=lambda x: x["date"], reverse=True)[:60]


def main():
    home = Path(sys.argv[1] if len(sys.argv) > 1 else "~/.project-inventory").expanduser()
    inv = json.loads((home / "inventory.json").read_text(encoding="utf-8"))
    snaps = sorted((home / "facts").glob("*.json"))
    if not snaps:
        sys.exit("FAILED: no snapshot in facts/ - run collect.py first")
    hist = [json.loads(s.read_text(encoding="utf-8")) for s in snaps]
    now = hist[-1]
    today = dt.date.fromisoformat(now["date"])
    projects = []
    for p in inv["projects"]:
        f = now["projects"].get(p["key"])
        if f is None:
            sys.exit(f"FAILED: project {p['key']} is not in the newest snapshot - run collect.py again")
        on_node = {t: n["id"] for n in p.get("nodes", []) for t in n.get("tickets", [])}  # ticket id -> step
        f["tickets"] = [{**t, "node": t.get("node", on_node.get(t.get("id")))} for t in f["tickets"]]
        counts = {s: sum(t.get("state") == s for t in f["tickets"]) for s in STATES}
        trend = []  # one point per snapshot day: open tickets, things waiting on the owner
        for h in hist:
            hf = h["projects"].get(p["key"])
            if hf:
                trend.append({"date": h["date"], "open": sum(t.get("state") in ("open", "wait") for t in hf["tickets"]),
                              "todo": sum(1 for _ in todos(p, hf))})
        projects.append({**p, "facts": f, "counts": counts, "todo": todos(p, f),
                         "activity": activity(f, today), "trend": trend})
    page = {"title": inv.get("title", "Projects"), "lang": inv.get("lang", "en"),
            "date": now["date"], "generated_at": now["generated_at"], "projects": projects}
    html = (HERE / "template.html").read_text(encoding="utf-8")
    html = html.replace("__LANG__", htmllib.escape(page["lang"])).replace("__TITLE__", htmllib.escape(page["title"]))
    html = html.replace("/*__DATA__*/null", json.dumps(page, ensure_ascii=False).replace("</", "<\\/"))
    out = home / "out" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    # claude.ai Artifact: the host adds doctype/html/head/body and the meta tags itself
    head = html.split("<head>", 1)[1].split("</head>", 1)[0]
    head = "\n".join(l for l in head.splitlines() if not l.lstrip().startswith("<meta"))
    body = html.split("<body>", 1)[1].rsplit("</body>", 1)[0]
    (out.parent / "artifact.html").write_text(head.strip() + "\n" + body.strip() + "\n", encoding="utf-8")
    print(f"built {out} ({len(html):,} bytes, {len(projects)} projects, snapshot {now['date']}, {len(hist)} days of history)")


if __name__ == "__main__":
    main()
