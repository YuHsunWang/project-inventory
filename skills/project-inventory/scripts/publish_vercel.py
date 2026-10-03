"""Deploy <home>/out to a Vercel project that only the owner's logged-in Vercel account can open.

    python3 publish_vercel.py <home> <project-name> [--team <team id or slug>] [--reuse]

Order matters: the project is created and locked ("Vercel Authentication" on all deployments,
free on Hobby) BEFORE anything is deployed, and the page is checked from outside afterwards.
Needs the Vercel CLI, logged in (`vercel login`). Exit 1 on any failure; never leaves a public page
without saying so.

A project this script did not create is never overwritten unless you pass --reuse (once); the
project id is then remembered in <home>/vercel.json.
"""
import json, os, platform, re, shutil, subprocess, sys, urllib.error, urllib.request
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
        if 300 <= e.code < 400 and not loc.startswith("https://vercel.com/"):
            return f"{e.code} to {loc or '?'}"  # a redirect that is not Vercel's sign-in proves nothing
        return e.code
    except urllib.error.URLError as e:
        return f"unreachable ({e.reason})"


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
    print("locked: Vercel Authentication on all deployments")

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
    st, d = call("GET", f"/v13/deployments/{url.removeprefix('https://')}", team=team)
    hosts = [url.removeprefix("https://"), *d.get("alias", [])]
    codes = {h: anon_status(f"https://{h}/") for h in hosts}
    # locked = the login wall: 401/403, or a redirect to Vercel's sign-in (anon_status turns any other
    # redirect into text). Anything else (200, 404, 500, unreachable) is not proof of a lock.
    unproven = [h for h, c in codes.items() if not (c in (401, 403) or isinstance(c, int) and 300 <= c < 400)]
    if unproven:
        sys.exit("FAILED: could not confirm the page is locked: " + ", ".join(f"{h} -> {codes[h]}" for h in unproven)
                 + ". 200 means PUBLIC. Check the project's Deployment Protection.")
    main_host = next((h for h in d.get("alias", []) if h.startswith(name + ".") or h.startswith(name + "-") and "-git-" not in h), hosts[0])
    print(f"deployed: https://{main_host}")
    print("anonymous visitor: " + ", ".join(f"{h} -> {c}" for h, c in codes.items()) + "  (401/403/redirect = locked)")

if __name__ == "__main__":
    TOKEN = token()
    main()
