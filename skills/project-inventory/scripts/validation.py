"""Stdlib contracts for inventory, gathered rows and snapshots. Errors name the input field."""
import datetime as dt
import json
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

STATES = ("wait", "open", "done", "dead")
RESERVED = {"home", "projects", "brand", "menubtn", "menulabel", "stamp", "menu", "menuitems", "foot"}


def fail(path, message):
    raise ValueError(f"{path}: {message}")


def typed(value, kind, path):
    if not isinstance(value, kind) or isinstance(value, bool):
        fail(path, f"expected {kind.__name__}")
    return value


def string(value, path):
    typed(value, str, path)
    if not value.strip():
        fail(path, "expected nonempty string")
    return value


def choice(value, options, path):
    if value not in options:
        fail(path, f"expected one of {', '.join(options)}")


def parse_date(value, path="date"):
    """Accept ISO calendar dates or timestamps, preserving their offsets."""
    string(value, path)
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return dt.date.fromisoformat(value)
        if not re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", value):  # SQL engines print a space
            raise ValueError()
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(path, f"invalid ISO date/timestamp {json.dumps(value)}")


def optional_date(value, path):
    if value not in (None, ""):
        parse_date(value, path)


def url(value, path):
    string(value, path)
    try:
        u = urlsplit(value)
        valid = u.scheme in ("http", "https") and u.hostname and not u.username and not u.password
        u.port
    except ValueError:
        valid = False
    if not valid or re.search(r'[\s<>"\\]', value):
        fail(path, "expected absolute HTTP/HTTPS URL")


def links(value, path):
    for i, pair in enumerate(typed(value, list, path)):
        at = f"{path}[{i}]"
        typed(pair, list, at)
        if len(pair) != 2:
            fail(at, "expected [label, URL]")
        string(pair[0], at + "[0]")
        url(pair[1], at + "[1]")


def validate_inventory(inv):
    typed(inv, dict, "inventory")
    timezone(inv.get("timezone", "UTC"))
    keys = set()
    for field in ("title", "lang"):
        if field in inv:
            string(inv[field], field)
    for i, p in enumerate(typed(inv.get("projects"), list, "projects")):
        at = f"projects[{i}]"
        typed(p, dict, at)
        key = string(p.get("key"), at + ".key")
        if key in keys:
            fail(at + ".key", f"duplicate {json.dumps(key)}")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            fail(at + ".key", "use only letters, digits, underscores and hyphens")
        if key.lower() in RESERVED or key.startswith(("t-", "d-")):
            fail(at + ".key", f"reserved {json.dumps(key)}")
        keys.add(key)
        string(p.get("name"), at + ".name")
        if "links" in p:
            links(p["links"], at + ".links")
        nodes = typed(p.get("nodes", []), list, at + ".nodes")
        ids, spine = set(), set()
        for j, n in enumerate(nodes):
            np = f"{at}.nodes[{j}]"
            typed(n, dict, np)
            node_id = typed(n.get("id"), int, np + ".id")
            if node_id in ids:
                fail(np + ".id", f"duplicate {node_id}")
            ids.add(node_id)
            if "on" not in n:
                spine.add(node_id)
            if "side" in n:
                choice(n["side"], ("l", "r"), np + ".side")
            for m, media in enumerate(typed(n.get("media", []), list, np + ".media")):
                mp = f"{np}.media[{m}]"
                typed(media, dict, mp)
                if "link" in media:
                    links([media["link"]], mp + ".link")
            for field in ("paths", "tickets"):
                for k, v in enumerate(typed(n.get(field, []), list, np + "." + field)):
                    string(v, f"{np}.{field}[{k}]")
        for j, n in enumerate(nodes):
            if "on" in n:
                typed(n["on"], int, f"{at}.nodes[{j}].on")
                if n["on"] not in spine:
                    fail(f"{at}.nodes[{j}].on", f"must reference a spine node, got {n['on']}")
        src = typed(p.get("sources", {}), dict, at + ".sources")
        for name in ("linear", "notion"):
            if name in src:
                spec = typed(src[name], dict, at + ".sources." + name)
                if name == "linear" and not (spec.get("project_id") or spec.get("project")):
                    fail(at + ".sources.linear", "expected project_id or legacy project name")
                if name == "notion":
                    url(spec.get("url"), at + ".sources.notion.url")
                    for label, state in typed(spec.get("status_map", {}), dict, at + ".sources.notion.status_map").items():
                        choice(state, STATES, at + ".sources.notion.status_map." + label)
        for j, repo in enumerate(typed(src.get("github", []), list, at + ".sources.github")):
            if not isinstance(repo, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
                fail(f"{at}.sources.github[{j}]", "expected owner/repo")
        for name in ("local", "obsidian"):
            for j, spec in enumerate(typed(src.get(name, []), list, at + ".sources." + name)):
                sp = f"{at}.sources.{name}[{j}]"
                typed(spec, dict, sp)
                string(spec.get("path"), sp + ".path")
                if name == "local":
                    string(spec.get("label"), sp + ".label")
        for j, spec in enumerate(typed(p.get("data", []), list, at + ".data")):
            dp = f"{at}.data[{j}]"
            typed(spec, dict, dp)
            choice(spec.get("kind"), ("csv", "jsonl", "json", "sqlite", "parquet", "duckdb"), dp + ".kind")
            for field in ("path", "column"):
                string(spec.get(field), dp + "." + field)
            if spec["kind"] in ("sqlite", "duckdb"):
                string(spec.get("table"), dp + ".table")
            age = typed(spec.get("max_age_days", 1), int, dp + ".max_age_days")
            if age < 0:
                fail(dp + ".max_age_days", "must be nonnegative")
    return inv


def validate_rows(rows, path, prs=False, node_ids=None):
    """Validate before deduping; keep the first row for each stable provider identity."""
    out, seen = [], set()
    for i, row in enumerate(typed(rows, list, path)):
        at = f"{path}[{i}]"
        typed(row, dict, at)
        string(row.get("title"), at + ".title")
        if prs:
            repo = string(row.get("repo"), at + ".repo")
            if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
                fail(at + ".repo", "expected owner/repo")
            number = typed(row.get("number"), int, at + ".number")
            if number < 1:
                fail(at + ".number", "must be positive")
            identity = (repo, number)
            optional_date(row.get("createdAt"), at + ".createdAt")
        else:
            choice(row.get("state"), STATES, at + ".state")
            choice(row.get("source"), ("linear", "notion"), at + ".source")
            string(row.get("id"), at + ".id")
            # A short Notion display ID is not a unique page identity. Legacy page URLs are.
            source_id = row.get("source_id") or (row.get("url") if row["source"] == "notion" else row["id"])
            string(source_id, at + ".source_id")
            identity = (row["source"], source_id)
            for field in ("created", "completed", "canceled", "reopened"):
                optional_date(row.get(field), at + "." + field)
            if row.get("node") is not None and node_ids is not None:
                typed(row["node"], int, at + ".node")
                if row["node"] not in node_ids:
                    fail(at + ".node", "unknown node reference")
        if row.get("url") is not None:
            url(row["url"], at + ".url")
        if identity not in seen:
            out.append(row)
            seen.add(identity)
    return out


def validate_notes(rows, path):
    for i, row in enumerate(typed(rows, list, path)):
        at = f"{path}[{i}]"
        typed(row, dict, at)
        for field in ("open", "done"):
            if typed(row.get(field), int, at + "." + field) < 0:
                fail(at + "." + field, "must be nonnegative")
        items = typed(row.get("items"), list, at + ".items")
        for j, item in enumerate(items):
            ip = f"{at}.items[{j}]"
            typed(item, dict, ip)
            for field in ("text", "file"):
                string(item.get(field), ip + "." + field)
            if "line" in item and typed(item["line"], int, ip + ".line") < 1:
                fail(ip + ".line", "must be positive")
        if "total" in row or "shown" in row:
            total = typed(row.get("total"), int, at + ".total")
            shown = typed(row.get("shown"), int, at + ".shown")
            if total != row["open"] or shown != len(items) or not 0 <= shown <= min(total, 50):
                fail(at, "inconsistent notes total/shown counts")


def validate_project_rows(projects, inv, path):
    typed(projects, dict, path)
    configured = {p["key"]: p for p in inv["projects"]}
    for key, data in projects.items():
        if key == "_run":
            typed(data, dict, path + "._run")
            string(data.get("run_id"), path + "._run.run_id")
            continue
        at = path + "." + key
        if key not in configured:
            fail(at, "unknown project key")
        typed(data, dict, at)
        ids = {n["id"] for n in configured[key].get("nodes", [])}
        for name in ("tickets", "stale_tickets", "prs"):
            if name in data:
                data[name] = validate_rows(data[name], at + "." + name, name == "prs", ids)
        for name, state in typed(data.get("sources", {}), dict, at + ".sources").items():
            sp = at + ".sources." + name
            typed(state, dict, sp)
            choice(state.get("status"), ("ok", "failed", "partial", "stale", "unavailable"), sp + ".status")
            for field in ("attempted_at", "fetched_at"):
                optional_date(state.get(field), sp + "." + field)
            if "complete" in state and not isinstance(state["complete"], bool):
                fail(sp + ".complete", "expected bool")
        validate_notes(data.get("obsidian", []), at + ".obsidian")
        for i, error in enumerate(typed(data.get("errors", []), list, at + ".errors")):
            string(error, f"{at}.errors[{i}]")
    return projects


def validate_gathered(data, inv, path="gathered"):
    return validate_project_rows(data, inv, path)


def validate_snapshot(snap, inv):
    typed(snap, dict, "snapshot")
    parse_date(snap.get("date"), "snapshot.date")
    parse_date(snap.get("generated_at"), "snapshot.generated_at")
    validate_project_rows(snap.get("projects"), inv, "snapshot.projects")
    return snap


def timezone(name="UTC"):
    string(name, "timezone")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        fail("timezone", f"unknown IANA timezone {name!r}")


def normalize_date(value, zone="UTC", path="date"):
    """Dates keep their calendar day; naive timestamps use the inventory timezone."""
    parsed = parse_date(value, path)
    tz = timezone(zone)
    if isinstance(parsed, dt.datetime):
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=tz)).astimezone(tz)
    return parsed


def calendar_date(value, zone="UTC", path="date"):
    parsed = normalize_date(value, zone, path)
    return parsed.date() if isinstance(parsed, dt.datetime) else parsed


def date_order(value, zone="UTC", path="date"):
    parsed = normalize_date(value, zone, path)
    return parsed if isinstance(parsed, dt.datetime) else dt.datetime.combine(parsed, dt.time(), timezone(zone))
