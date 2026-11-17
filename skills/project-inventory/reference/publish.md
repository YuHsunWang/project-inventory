# Publishing

Read before sending the page anywhere other than the local file. `HOME` and `SCRIPTS` mean what `SKILL.md` says.

| Option | How | Who can see it |
|---|---|---|
| Local file (default) | `HOME/out/index.html`, open in a browser | only this computer |
| HTML for manual Artifact import | `HOME/out/artifact.html` is generated without document wrappers/meta tags; offer it for manual import only if the chosen host accepts it. No publishing API, capability detection or identity storage exists. | Host-dependent; publishing/sharing/access unverified. |
| Vercel | `python3 SCRIPTS/publish_vercel.py HOME <project-name>` (refuses an existing project it did not create; `--reuse` only after the user confirms that project is for this page) — creates the project, locks it (Vercel Authentication, all deployments) BEFORE deploying, then checks an anonymous visitor is turned away | Vercel-authorized users; actual access depends on team/project membership, granted access, sharing and bypass settings |
| GitHub Pages | see below | **everyone on the internet** |

Artifact end-to-end acceptance is **pending**: record the host/version, verify import,
create/update identity and URL behavior, external fonts/MathJax script restrictions,
CSP handling and sharing permissions before claiming support. The local file path
cannot establish artifact identity, a stable URL or private access.

**Standard GitHub Pages sites are public.** Check the account plan and repo visibility first:

| Path | Supported / visibility |
|---|---|
| GitHub Free + public repo | Supported; repo and site public. |
| GitHub Free + private repo | Not supported. Offer local/another host; never change visibility automatically. |
| GitHub Pro/Team + private repo | Supported; repo private, standard site public. |

[Official plan requirements](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).
Enterprise access-controlled Pages is separate and unverified in this workflow.
Preview `out/index.html`, its embedded facts and assets with the user: project names,
tickets, branches, paths and screenshots can be exposed. Offer a minimal public copy in
another home: only approved project names/tags/diagram text, empty `sources` and `data`,
no `notes`, node `paths` or `media`. Collect/build that home; preview again. No automatic
redaction exists. Get explicit approval for the exact content, plan and visibility before
publishing. Never make a private repository public to work around a failed deployment.

Use the repo the user names. If creating one, use `gh repo create <name> --public` only
for the approved Free/public path, or `--private` only with a confirmed supporting paid
plan. Copy the approved `out/index.html` to its root, commit, push, and enable Pages on
its default branch (`gh repo view <owner>/<repo> --json defaultBranchRef -q .defaultBranchRef.name`;
not always `main`): `gh api -X POST repos/<owner>/<repo>/pages -f "source[branch]=<branch>" -f "source[path]=/"`.
Each later run: preview, copy, commit, push within the agreed publishing scope.

Never send the page anywhere the user did not choose.
