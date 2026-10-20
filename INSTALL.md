# Agent installation instructions

## OBJECTIVE

Install project-inventory for the agent reading this file, verify it with the
bundled fictional demo, and give the user one report. No repository checkout is
needed. Start from these instructions even when fetched from the raw URL.

## DONE WHEN

- One installation method is available to the current agent; existing files are preserved.
- Python 3 and Git work, and the installed demo passes collect + build in a fresh temporary directory.
- A nonempty demo HTML page exists and the final report gives its absolute path and the next step.

## Rules

- Infer the current agent from your host/session. Ask no setup or preference questions.
  The only question allowed is the missing-Python question in step 1.
- Never overwrite, delete, migrate, or reinstall an existing installation. Keep it
  and verify it. If multiple methods already exist, report the duplicate and stop;
  do not remove either. A skill and plugin with the same name can load twice.
- Install only one way: Claude Code uses its plugin; other agents use Skills CLI.
  Do not try a second installer after a failure.
- Use only the commands below, which follow the repository README installation methods.
  An unsupported agent must stop with the manual-install link in the report.
- Run all commands belonging to a step in one shell call. Use a POSIX shell;
  keep discovered paths in your working notes and pass them explicitly in later calls
  if your shell tool does not preserve environment variables.
- Do not run skill setup during installation. Do not create a user `inventory.json`,
  configure schedules, publish, or read/write the user's `~/.project-inventory`.
  Only the bundled demo may generate a fictional `inventory.json`, inside its new
  temporary directory. Never collect the user's projects for this self-check.
- Stop on failure and include the failed command and its output in the single final
  report. Do not claim success for checks you did not run.

## TODO

- [ ] Check runtime.
- [ ] Detect and preserve existing installations.
- [ ] Install once, or keep the existing installation.
- [ ] Build and verify the fictional demo.
- [ ] Report results and the next step.

## 1. Check runtime

Run this block as one shell call:

```sh
if command -v python3 >/dev/null 2>&1; then
  python3 --version
else
  printf '%s\n' 'MISSING: Python 3'
fi
if command -v git >/dev/null 2>&1; then
  git --version
else
  printf '%s\n' 'MISSING: Git (required by the bundled demo)'
fi
```

If Python 3 is missing, ask once: **"Python 3 is required. May I install it using
this system's package manager?"** Wait for the answer; on approval install it and
repeat this check, otherwise stop and report. Ask nothing else. If Git is missing,
stop and report that prerequisite. The demo and collect/build use Python's standard
library; no pip packages or service credentials are required. Chromium is needed
only for the optional `scripts/check_page.py` browser/layout check, which is outside
this installation self-check. Without it, report layout as UNVERIFIED.

## 2. Detect existing installations

Before any install command, run this block as one shell call:

```sh
for pi_path in \
  "$HOME/.agents/skills/project-inventory" \
  "$HOME/.claude/skills/project-inventory" \
  "$HOME/.codex/skills/project-inventory" \
  "$HOME/.hermes/skills/project-inventory" \
  "${CLAUDE_CONFIG_DIR:+$CLAUDE_CONFIG_DIR/skills/project-inventory}" \
  "${CODEX_HOME:+$CODEX_HOME/skills/project-inventory}" \
  "${HERMES_HOME:+$HERMES_HOME/skills/project-inventory}"
do
  if [ -e "$pi_path" ] || [ -L "$pi_path" ]; then
    printf 'EXISTING: %s\n' "$pi_path"
  fi
done
if command -v claude >/dev/null 2>&1; then
  claude plugin list
else
  printf '%s\n' 'Claude CLI unavailable; plugin list not applicable to this host'
fi
if command -v npx >/dev/null 2>&1; then
  npx -y skills ls -g
fi
printf '%s\n' 'Detection complete; inspect results before installing'
```

Inspect the output, including disabled or project-scoped project-inventory plugins.
Symlinks pointing to the same skill count as one method. For other agents, also
inspect their known skill directories as well as the Skills CLI listing above
to detect agent-specific installs.
A failed plugin list on a Claude Code host makes detection incomplete: stop rather
than risk a duplicate. Preserve broken symlinks and incomplete installations too;
report them as failures instead of replacing them.

Keep an installation that the current agent can load and skip step 3's install
commands. A plugin used only by another host does not replace this host's skill.
If an existing installation cannot be loaded by this agent, stop and report its
location and the manual-install link rather than creating a second copy.

## 3. Install one way and locate the skill

**Claude Code:** if no applicable installation exists, run these commands together.
If the marketplace is already registered, keep it and omit the first command;
do not update or replace it:

```sh
claude plugin marketplace add YuHsunWang/project-inventory &&
claude plugin install project-inventory@project-inventory --scope user &&
claude plugin list
```

Use the installation path from the plugin listing. If it omits the path, inspect
Claude's installed-plugin metadata under `${CLAUDE_CONFIG_DIR:-$HOME/.claude}`
(read-only). The skill directory is `skills/project-inventory` inside the plugin
installation, containing `SKILL.md`, `reference/`, and `scripts/`.

**Other agents:** check that Node.js/npm and npx are available. If unavailable,
stop and report the missing installer runtime; do not ask another question. Infer
the Skills CLI agent identifier from the current host (for example, `codex` for
Codex or `hermes` for Hermes). Substitute that identifier for `<agent>` and run
both commands in one shell call:

```sh
npx -y skills add YuHsunWang/project-inventory -g -y -a <agent> &&
npx -y skills ls -g
```

If Skills CLI rejects or does not recognize the agent, stop. Include
[README manual installation](https://github.com/YuHsunWang/project-inventory#manual-codex-standalone-copy)
in the report; Hermes instructions follow that section. Do not fall back to a copy,
plugin, or another agent identifier. On success, locate the installed skill from the
listing (normally `~/.agents/skills/project-inventory`).

For either a new or preserved installation, record the absolute skill directory as
`PI_SKILL`. Check that `SKILL.md`, `reference/demo.py`,
`reference/example-inventory.json`, `reference/demo-tasks.json`,
`scripts/collect.py`, and `scripts/build.py` exist. If anything is missing, stop;
never repair by overwriting an existing install.

## 4. Self-check using only the bundled demo

Set `PI_SKILL` to the absolute directory found in step 3 **in the same shell call**
as this entire block. Do not assume a repository checkout or the current directory.
Keep the temporary demo so the user can open the page. Every script receives the
explicit demo directory, never the default inventory home.

```sh
(
  set -eu
  : "${PI_SKILL:?Set PI_SKILL to the installed skill directory from step 3}"
  test -f "$PI_SKILL/SKILL.md"
  test -f "$PI_SKILL/reference/demo.py"
  test -f "$PI_SKILL/reference/example-inventory.json"
  test -f "$PI_SKILL/reference/demo-tasks.json"
  test -f "$PI_SKILL/scripts/collect.py"
  test -f "$PI_SKILL/scripts/build.py"
  PI_DEMO=$(mktemp -d "${TMPDIR:-/tmp}/project-inventory-demo.XXXXXX")
  python3 "$PI_SKILL/reference/demo.py" "$PI_DEMO"
  python3 "$PI_SKILL/scripts/collect.py" "$PI_DEMO"
  python3 "$PI_SKILL/scripts/build.py" "$PI_DEMO"
  test -s "$PI_DEMO/out/index.html"
  printf 'SELF-CHECK OK: %s/out/index.html\n' "$PI_DEMO"
)
```

This verifies demo generation, collection and HTML generation. It does not verify
browser layout or that a running host has reloaded the installed skill.

## 5. One final report

Report once, in the user's language:

- Status: installed, kept existing, or failed; current agent and installation method.
- Absolute installation path, or the blocker and manual-install link if unsupported.
- Runtime versions; self-check commands and their actual output; absolute demo page path.
- Browser layout and host loading: UNVERIFIED unless actually checked.
- Confirm user configuration, schedules and publishing were not changed.
- Next step: reload plugins/start a new host session, then run
  `/project-inventory:project-inventory` for the Claude Code plugin, or invoke the
  standalone skill with “inventory my projects” to configure the user's projects.
