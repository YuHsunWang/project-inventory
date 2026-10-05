"""Deploy <home>/out with Vercel Authentication for authorized users.
Access depends on team/project membership, granted access, sharing and bypass settings.

    python3 publish_vercel.py <home> <project-name> [--team <team id or slug>] [--reuse]

Order matters: the project is created and locked ("Vercel Authentication" on all deployments,
free on Hobby) BEFORE anything is deployed, and the page is checked from outside afterwards.
Needs the Vercel CLI, logged in (`vercel login`). Exit 1 on any failure; never leaves a public page
without saying so.

A project this script did not create is never overwritten unless you pass --reuse (once); the
project id is then remembered in <home>/vercel.json.
"""
import json, os, platform, re, shutil, subprocess, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API = "https://api.vercel.com"


def token():
    if os.environ.get("VERCEL_TOKEN"):
        return os.environ["VERCEL_TOKEN"]
    home = Path.home()
    cands = {"Darwin": [home / "Library/Application Support/com.vercel.cli/auth.json"],
             "Windows": [Path(os.environ.get("APPDATA", home)) / "com.vercel.cli/Data/auth.json"]}.get(platform.system(), [])
    cands.append(Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")) / "com.vercel.cli/auth.json")
    for c in cands:
        if c.exists():
            return json.loads(c.read_text())["token"]
    sys.exit("FAILED: Vercel CLI is not logged in. Run `vercel login` (or set VERCEL_TOKEN).")


def call(method, path, body=None, team=None):
    sep = "&" if "?" in path else "?"
    url = API + path + (f"{sep}{'teamId' if team.startswith('team_') else 'slug'}={team}" if team else "")
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def anon_status(url):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        return urllib.request.build_opener(NoRedirect).open(url, timeout=30).status
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location") or ""
        target = urllib.parse.urlsplit(loc)
        query = urllib.parse.parse_qs(target.query)
        back = query.get("url", [""])[0]
        if (e.code in (302, 303, 307, 308) and target.scheme == "https" and target.netloc == "vercel.com"
                and target.path == "/sso-api" and back == url):
            return "Vercel login redirect"
        return f"{e.code} to {loc or '?'}" if 300 <= e.code < 400 else e.code
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return f"unreachable ({e})"


def verification_failed(reason):
    sys.exit("FAILED: could not confirm the page is locked: " + reason
             + ". Deployment may be PUBLIC. In Vercel, open this project's Settings > Deployment Protection, "
               "enable Vercel Authentication for All Deployments, remove public exceptions and review bypass/share "
               "settings. Take the deployment offline if needed, then rerun verification before sharing its URL.")


def checked_get(path, team):
    try:
        st, data = call("GET", path, team=team)
    except (OSError, ValueError) as e:
        verification_failed(f"{path}: {e}")
    if not 200 <= st < 300 or not isinstance(data, dict):
        verification_failed(f"{path}: API {st}, invalid or unavailable response")
    return data


def checked_host(host):
    if (not isinstance(host, str) or len(host) > 253 or "." not in host
            or not all(re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", part)
                       for part in host.split("."))):
        verification_failed("invalid alias/domain structure")
    return host


def project_domains(project_id, team):
    hosts, seen, cursor = [], set(), None
    while True:
        path = f"/v9/projects/{project_id}/domains?limit=100"
        if cursor is not None:
            path += "&until=" + urllib.parse.quote(str(cursor), safe="")
        data = checked_get(path, team)
        if not isinstance(data.get("domains"), list):
            verification_failed("invalid project domains structure")
        for domain in data["domains"]:
            if not isinstance(domain, dict):
                verification_failed("invalid project domain entry")
            hosts.append(checked_host(domain.get("name")))
        pagination = data.get("pagination", {"next": None})
        if not isinstance(pagination, dict) or "next" not in pagination:
            verification_failed("invalid domains pagination")
        cursor = pagination["next"]
        if cursor is None:
            return hosts
        if type(cursor) is not int or cursor in seen or len(seen) >= 100:
            verification_failed("invalid or repeated domains pagination cursor")
        seen.add(cursor)


def main():
    args = sys.argv[1:]
    team = None
    reuse = "--reuse" in args
    if reuse:
        args.remove("--reuse")
    if "--team" in args:
        i = args.index("--team"); team = args[i + 1]; del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    home, name = Path(args[0]).expanduser(), args[1]
    out, mine_f = home / "out", home / "vercel.json"
    mine = json.loads(mine_f.read_text()) if mine_f.exists() else {}
    if not (out / "index.html").exists():
        sys.exit(f"FAILED: {out}/index.html not found - run build.py first")
    if not shutil.which("vercel"):
        sys.exit("FAILED: Vercel CLI not installed (npm i -g vercel)")

    st, proj = call("GET", f"/v9/projects/{name}", team=team)
    if st == 404:
        st, proj = call("POST", "/v11/projects", {"name": name, "framework": None}, team=team)
        if st >= 300:
            sys.exit(f"FAILED: create project: {st} {proj.get('error')}")
        print(f"created Vercel project {name}")
    elif st >= 300:
        sys.exit(f"FAILED: read project: {st} {proj.get('error')}")
    elif mine.get(name) != proj["id"] and not reuse:
        sys.exit(f"FAILED: Vercel project {name!r} already exists and was not made by this script. Deploying would "
                 "replace its live site. Pick a new name, or pass --reuse if this project is really for this page.")
    mine_f.write_text(json.dumps({**mine, name: proj["id"]}, indent=1))

    st, upd = call("PATCH", f"/v9/projects/{proj['id']}", {"ssoProtection": {"deploymentType": "all"}}, team=team)
    if st >= 300 or (upd.get("ssoProtection") or {}).get("deploymentType") != "all":
        sys.exit(f"FAILED: could not lock the project (no deploy made): {st} {upd.get('error')}")
    print("configured: Vercel Authentication on all deployments; verification pending")

    env = {**os.environ, "VERCEL_ORG_ID": proj["accountId"], "VERCEL_PROJECT_ID": proj["id"]}
    r = subprocess.run(["vercel", "deploy", str(out), "--prod", "--yes"], env=env, capture_output=True, text=True, timeout=900)
    log = r.stdout + r.stderr
    if r.returncode:
        print(log[-1500:])
        sys.exit("FAILED: vercel deploy. If it says 'Not authorized' or hangs on 'Building', check that the git "
                 "commit author email is on your Vercel account (Vercel blocks unknown commit authors).")
    # the CLI prints plain text to a terminal but JSON when it detects an agent: take the URL from either
    m = re.search(r"https://[a-z0-9-]+\.vercel\.app", r.stdout)
    if not m:
        print(log[-1500:])
        sys.exit("FAILED: deploy ran but no deployment URL found in the CLI output")
    url = m.group(0)
    d = checked_get(f"/v13/deployments/{url.removeprefix('https://')}", team)
    aliases = d.get("alias")
    if not isinstance(aliases, list):
        verification_failed("invalid deployment aliases structure")
    aliases = [checked_host(h) for h in aliases]
    domains = project_domains(proj["id"], team)
    policy = checked_get(f"/v9/projects/{proj['id']}", team)
    if (policy.get("ssoProtection") or {}).get("deploymentType") != "all":
        verification_failed("project no longer has All Deployments authentication")
    hosts = list(dict.fromkeys([url.removeprefix("https://"), *aliases, *domains]))
    codes = {h: anon_status(f"https://{h}/") for h in hosts}
    # Bare 401/403 can come from a firewall or app; require the Vercel SSO endpoint AND project policy.
    unproven = [h for h, c in codes.items() if c != "Vercel login redirect"]
    if unproven:
        verification_failed(", ".join(f"{h} -> {codes[h]}" for h in unproven))
    main_host = next((h for h in aliases if h.startswith(name + ".") or h.startswith(name + "-") and "-git-" not in h), hosts[0])
    print(f"scope: account={proj['accountId']} team={team or proj['accountId']} project={name} ({proj['id']})")
    print("access: Vercel-authorized users; actual access depends on team/project membership, "
          "granted access, sharing and bypass settings")
    print(f"deployed: https://{main_host}")
    print("anonymous visitor: " + ", ".join(f"{h} -> {c}" for h, c in codes.items())
          + "  (Vercel login redirect and All Deployments policy verified)")

if __name__ == "__main__":
    TOKEN = token()
    main()
