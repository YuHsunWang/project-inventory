"""Turn inventory.json + the newest fact snapshot into one self-contained HTML page.

    python3 build.py <home>          # -> <home>/out/index.html and <home>/out/artifact.html

Screenshots named in a step's `media` are embedded in the page, so the one file works as a local
file, a claude.ai Artifact, on Vercel and on GitHub Pages.
"""
import argparse, base64, hashlib, re, datetime as dt, html as htmllib, json, struct, sys, zlib
from pathlib import Path
from collect import atomic_write
from validation import validate_inventory, validate_snapshot, calendar_date

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


def ticket_series(tickets, today, days=90, zone="UTC"):
    """Estimate history only for rows with a coherent lifecycle; report the rest as unknown."""
    known, reasons = [], {}
    for i, t in enumerate(tickets):
        dates = {field: calendar_date(t[field], zone, f"tickets[{i}].{field}") if t.get(field) else None
                 for field in ("created", "completed", "canceled", "reopened")}
        state = t.get("state")
        end = dates["completed"] if state == "done" else dates["canceled"] if state == "dead" else None
        reason = None
        if not dates["created"]:
            reason = "missing_created"
        elif dates["reopened"] or (state in ("open", "wait") and (dates["completed"] or dates["canceled"])):
            reason = "reopened"
        elif state == "done" and not end:
            reason = "missing_completed"
        elif state == "dead" and not end:
            reason = "missing_canceled"
        elif any(d and d > today for d in dates.values()):
            reason = "future_date"
        elif (end and end < dates["created"]) or (dates["completed"] and dates["canceled"]):
            reason = "inconsistent_dates"
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
        else:
            known.append((dates["created"], end, state))
    unknown = len(tickets) - len(known)
    out = {"days": [], "done": [], "open": [], "canceled": [], "unknown": [],
           "coverage": {"known": len(known), "total": len(tickets),
                        "ratio": len(known) / len(tickets) if tickets else 1, "reasons": reasons}}
    for n in range(days - 1, -1, -1):
        d = today - dt.timedelta(days=n)
        out["days"].append(d.isoformat())
        out["done"].append(sum(state == "done" and end <= d for created, end, state in known))
        out["open"].append(sum(created <= d and (end is None or end > d) for created, end, state in known))
        out["canceled"].append(sum(state == "dead" and end <= d for created, end, state in known))
        # Unknown is a current undated pool, not an invented creation/completion history.
        out["unknown"].append(unknown)
    return out


def now(f, today):
    """The facts behind the project's one-line status: last change, tickets done this week, waiting."""
    since = (today - dt.timedelta(days=14)).isoformat()
    # Older snapshots have project history but no aggregate; prefer it over capped repo lists.
    history_commits = f.get("commits", [c for r in f["repos"] for c in r["recent"]])
    commits = {c["hash"]: c["date"] for c in history_commits if c["date"] >= since}
    last = max(commits.values(), default=None) or max((r["last_commit"][:10] for r in f["repos"] if r["last_commit"]), default=None)
    week = (today - dt.timedelta(days=7)).isoformat()
    return {"last": last, "c14": f.get("commit_count_14", len(commits)), "err": bool(f["errors"]),
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


MAX_SHOT = 8 * 2**20
MAX_PIXELS = 16_000_000


def checked_png(raw):
    """Validate PNG chunks, CRCs and bounded decoded scanlines; never embed opaque file contents."""
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("only PNG, WebP or JPEG screenshots are supported")
    offset, chunks, payload, header, palette = 8, [], bytearray(), None, False
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ValueError("truncated PNG chunk")
        size = int.from_bytes(raw[offset:offset + 4], "big")
        kind = raw[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(raw):
            raise ValueError("truncated PNG chunk")
        data = raw[offset + 8:end - 4]
        if zlib.crc32(kind + data) != int.from_bytes(raw[end - 4:end], "big"):
            raise ValueError("broken PNG checksum")
        if not chunks and kind != b"IHDR":
            raise ValueError("missing PNG header")
        if kind == b"IHDR":
            if chunks or size != 13:
                raise ValueError("invalid PNG header")
            header = struct.unpack(">IIBBBBB", data)
        elif kind == b"PLTE":
            if palette or b"IDAT" in chunks or not size or size % 3 or size > 768:
                raise ValueError("invalid PNG palette")
            palette = True
        elif kind == b"IDAT":
            if b"IDAT" in chunks and chunks[-1] != b"IDAT":
                raise ValueError("non-contiguous PNG image data")
            payload.extend(data)
        elif kind == b"IEND":
            if size or end != len(raw):
                raise ValueError("invalid PNG end or trailing content")
            chunks.append(kind)
            break
        elif kind not in (b"tRNS",) and not (kind[0] & 32):
            raise ValueError("unsupported critical PNG chunk")
        chunks.append(kind)
        offset = end
    if not header or not chunks or chunks[-1] != b"IEND" or not payload:
        raise ValueError("incomplete PNG")
    w, h, depth, color, compression, filtering, interlace = header
    depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
    if not w or not h or w * h > MAX_PIXELS:
        raise ValueError("PNG dimensions exceed 16 million pixels or are empty")
    if depth not in depths.get(color, ()) or compression or filtering or interlace not in (0, 1):
        raise ValueError("invalid PNG encoding")
    if color == 3 and not palette:
        raise ValueError("missing PNG palette")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    passes = [(0, 0, 1, 1)] if not interlace else [(0,0,8,8), (4,0,8,8), (0,4,4,8),
                                                               (2,0,4,4), (0,2,2,4), (1,0,2,2), (0,1,1,2)]
    rows = []
    for x, y, dx, dy in passes:
        pw, ph = max(0, (w - x + dx - 1) // dx), max(0, (h - y + dy - 1) // dy)
        if pw and ph:
            rows.append((1 + (pw * channels * depth + 7) // 8, ph))
    expected = sum(size * n for size, n in rows)
    decoder = zlib.decompressobj()
    try:
        decoded = decoder.decompress(payload, expected + 1)
    except zlib.error as e:
        raise ValueError("broken PNG compressed data") from e
    if len(decoded) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("invalid PNG scanline size or compressed stream")
    offset = 0
    for size, count in rows:
        for _ in range(count):
            if decoded[offset] > 4:
                raise ValueError("invalid PNG scanline filter")
            offset += size
    return "image/png"


def checked_image(raw):
    """PNG is fully decoded; WebP/JPEG only get container checks (RIFF length, SOI/EOI markers)."""
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        if int.from_bytes(raw[4:8], "little") + 8 != len(raw):
            raise ValueError("truncated or padded WebP")
        return "image/webp"
    if raw[:3] == b"\xff\xd8\xff":
        if not raw.endswith(b"\xff\xd9"):
            raise ValueError("truncated JPEG")
        return "image/jpeg"
    return checked_png(raw)


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
                m.pop("src", None)  # a rejected shot cannot fall back to a supplied source
                try:
                    if not path.is_file():
                        raise FileNotFoundError(f"screenshot not found: {path}")
                    if not 0 < path.stat().st_size <= MAX_SHOT:
                        raise ValueError("screenshot is empty or exceeds 8 MiB")
                    with path.open("rb") as image:
                        raw = image.read(MAX_SHOT + 1)
                    if len(raw) > MAX_SHOT:
                        raise ValueError("screenshot exceeds 8 MiB")
                    mime = checked_image(raw)
                    m["src"] = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
                    print(f"ASSET step {n.get('id')}: {path.resolve()} ({len(raw)} bytes, {mime})")
                except (OSError, ValueError) as e:
                    m["missing"] = str(path)
                    warn(f"step {n.get('id')}: {e}" if isinstance(e, FileNotFoundError)
                         else f"step {n.get('id')}: screenshot rejected: {path}: {e}")


def build_page(home, snapshot=None, run_id=None):
    manifest_f = home / "refresh.json"
    manifest = json.loads(manifest_f.read_text(encoding="utf-8")) if manifest_f.exists() else None
    last_page = home / "out" / "index.html"
    if last_page.exists():
        marker = re.search(r'data-refresh-failure-at="([^"]+)"', last_page.read_text(encoding="utf-8"))
        if marker and (not manifest or dt.datetime.fromisoformat(marker[1]) >=
                       dt.datetime.fromisoformat(manifest["attempted_at"])):
            raise ValueError("latest refresh failed; rerun collect.py HOME --refresh before rebuilding")
    if manifest:
        if manifest.get("status") not in ("ok", "partial"):
            raise ValueError(manifest.get("error") or "latest refresh is incomplete; rerun collect.py HOME --refresh")
        expected = Path(manifest["snapshot"])
        if snapshot and snapshot.resolve() != expected.resolve():
            raise ValueError("snapshot does not match the latest refresh; rerun collect.py HOME --refresh")
        if run_id and run_id != manifest["run_id"]:
            raise ValueError("run_id does not match the latest refresh; rerun collect.py HOME --refresh")
        snapshot, run_id = expected, manifest["run_id"]
    inv = validate_inventory(json.loads((home / "inventory.json").read_text(encoding="utf-8")))
    snaps = sorted((home / "facts").glob("*.json"))
    if not snaps and snapshot is None:
        raise ValueError("no snapshot in facts/ - run collect.py HOME --refresh first")
    snap = validate_snapshot(json.loads((snapshot or snaps[-1]).read_text(encoding="utf-8")), inv)
    if run_id and snap.get("run_id") != run_id:
        raise ValueError("snapshot run_id differs from this refresh; rerun collect.py HOME --refresh")
    today = dt.date.fromisoformat(snap["date"])
    sums_f = home / "summaries.json"
    sums = json.loads(sums_f.read_text(encoding="utf-8")) if sums_f.exists() else {}
    warnings, projects, need = [], [], {}
    for p in inv["projects"]:
        f = snap["projects"].get(p["key"])
        if f is None:
            raise ValueError(f"project {p['key']} is not in this snapshot - run collect.py HOME --refresh again")
        zone = inv.get("timezone", "UTC")
        for ticket in f["tickets"]:
            for field in ("created", "completed", "canceled", "reopened"):
                if ticket.get(field):
                    ticket[field] = calendar_date(ticket[field], zone).isoformat()
        availability = ticket_state(p, f, snap)
        on_node = {t: n["id"] for n in p.get("nodes", []) for t in n.get("tickets", [])}  # ticket id -> step
        f["tickets"] = [{**t, "node": t.get("node", on_node.get(t.get("id")))} for t in f["tickets"]]
        embed_media(p.get("nodes", []), home, lambda s, k=p["key"]: warnings.append(f"{k}: {s}"))
        projects.append({**p, "facts": f, "ticket_state": availability, "counts": {s: sum(t.get("state") == s for t in f["tickets"]) for s in STATES},
                         "todo": todos(p, f), "now": now(f, today), "history": history(f, sums.get(p["key"], {})),
                         "weekly": f.get("weekly") if f["repos"] else None,
                         "trend_tickets": ticket_series(f["tickets"], today, zone=zone) if availability["status"] in ("ready", "empty") else None})
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
    atomic_write(out, html)
    # claude.ai Artifact: the host adds doctype/html/head/body and the meta tags itself
    head = html.split("<head>", 1)[1].split("</head>", 1)[0]
    head = "\n".join(l for l in head.splitlines() if not l.lstrip().startswith("<meta"))
    body = html.split("<body>", 1)[1].rsplit("</body>", 1)[0]
    atomic_write(out.parent / "artifact.html", head.strip() + "\n" + body.strip() + "\n")
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


def mark_failed_page(home, manifest):
    message = manifest.get("error") or "Refresh did not complete. Rerun collect.py HOME --refresh."
    banner = ('<!--refresh-failure--><div role="alert" data-refresh-failure-at="' +
              htmllib.escape(manifest.get("attempted_at", ""), quote=True) + '" style="padding:16px;background:#fff0ed;color:#8c1d10">'
              '<strong>FAILED: refresh / 更新失敗</strong><p>' + htmllib.escape(message) + '</p><p>' +
              htmllib.escape(manifest.get("attempted_at", "")) +
              ' · Last good data and time retained / 保留上次資料與時間</p></div><!--/refresh-failure-->')
    for name in ("index.html", "artifact.html"):
        path = home / "out" / name
        try:
            old = path.read_text(encoding="utf-8") if path.exists() else "<html><body></body></html>"
            old = re.sub(r"<!--refresh-failure-->.*?<!--/refresh-failure-->", "", old, flags=re.S)
            text = old.replace("<body>", "<body>" + banner, 1) if "<body>" in old else banner + old
            atomic_write(path, text)
        except OSError as e:
            print(f"FAILED: cannot mark {path}: {e}; last page was not refreshed", file=sys.stderr)


def ticket_state(p, f, snap):
    """Only complete, recent reads of this run can produce current ticket metrics."""
    names = [name for name in ("linear", "notion") if (p.get("sources") or {}).get(name)]
    states, good = {}, []
    for name in names:
        state = dict(f.get("sources", {}).get(name, {}))
        if not state:
            error = next((e for e in f["errors"] if e.startswith(name + ":")), None)
            state = {"status": "failed" if error else "stale", "fetched_at": None,
                     "error": error or "Source freshness was not recorded; gather again"}
        if state.get("status") == "ok":
            try:
                fetched = dt.datetime.fromisoformat(state["fetched_at"])
                if fetched.tzinfo is None:
                    fetched = fetched.astimezone()
                recent = dt.timedelta(0) <= dt.datetime.now().astimezone() - fetched <= dt.timedelta(days=1)
            except (ValueError, KeyError, TypeError):
                recent = False
            if not (state.get("complete") and recent and snap.get("run_id") and state.get("run_id") == snap["run_id"]):
                state.update(status="stale", error="Read is old or incomplete; gather the source again")
            else:
                good.append(name)
        states[name] = state
        f.setdefault("sources", {})[name] = state
        if state["status"] != "ok" and not any(e.startswith(name + ":") for e in f["errors"]):
            f["errors"].append(f"{name}: {state.get('error') or state['status']}")
    current = [t for t in f["tickets"] if t.get("source") in good]
    f.setdefault("stale_tickets", []).extend(t for t in f["tickets"] if t.get("source") not in good)
    f["tickets"] = current
    if not names:
        status = "not_connected"
    elif len(good) == len(names):
        status = "ready" if current else "empty"
    elif good or any(s["status"] == "partial" for s in states.values()):
        status = "partial"
    elif all(s["status"] == "stale" for s in states.values()):
        status = "stale"
    else:
        status = "failed"
    return {"status": status, "sources": states}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("home", nargs="?", default="~/.project-inventory")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    home = Path(args.home).expanduser()
    try:
        build_page(home, args.snapshot, args.run_id)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        message = f"FAILED: build could not complete: {e}. Fix the input or directory permissions and rerun collect.py HOME --refresh."
        manifest = {"error": message, "attempted_at": dt.datetime.now().astimezone().isoformat()}
        mark_failed_page(home, manifest)
        print(message, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
