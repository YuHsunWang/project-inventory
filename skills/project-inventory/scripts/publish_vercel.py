"""Deploy <home>/out to a Vercel project that only the owner's logged-in Vercel account can open.

    python3 publish_vercel.py <home> <project-name> [--team <team id or slug>]

Order matters: the project is created and locked ("Vercel Authentication" on all deployments,
free on Hobby) BEFORE anything is deployed, and the page is checked from outside afterwards.
Needs the Vercel CLI, logged in (`vercel login`). Exit 1 on any failure; never leaves a public page
without saying so.
"""
import json, os, platform, shutil, subprocess, sys, urllib.error, urllib.request
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
    url = API + path + (f"{sep}teamId={team}" if team else "")
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
        return e.code


def main():
    args = sys.argv[1:]
    team = None
    if "--team" in args:
        i = args.index("--team"); team = args[i + 1]; del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    out, name = Path(args[0]).expanduser() / "out", args[1]
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
    url = r.stdout.strip().splitlines()[-1]
    st, d = call("GET", f"/v13/deployments/{url.removeprefix('https://')}", team=team)
    alias = next((a for a in d.get("alias", []) if a.startswith(name)), None) or url
    code = anon_status(f"https://{alias.removeprefix('https://')}/")
    if code == 200:
        sys.exit(f"FAILED: https://{alias} answers 200 to an anonymous visitor - the page is PUBLIC. Check the project's Deployment Protection.")
    print(f"deployed: https://{alias.removeprefix('https://')}  (anonymous visitor gets {code}, i.e. locked)")


if __name__ == "__main__":
    TOKEN = token()
    main()
