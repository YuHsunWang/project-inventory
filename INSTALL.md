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
  The only questions allowed are the missing-Python question in step 1 and
  confirmation before updating an existing installation in step 5.
- Never automatically overwrite, delete, migrate, or reinstall an existing
  installation. Keep it and verify it. Propose an update only in the final report
  and wait for explicit user approval before running it. If multiple methods already
  exist, report the duplicate and stop; do not remove either. A skill and plugin
  with the same name can load twice.
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
  report, with one readable reason line even if the command produced no output.
  Classify sandbox denials as permission problems, naming the blocked operation
  and required access; do not report only “cannot read” or “exit code 1, no output”.
  Do not claim success for checks you did not run.

## TODO

- [ ] Check runtime.
- [ ] Detect and preserve existing installations.
- [ ] Install once, or keep the existing installation.
- [ ] Build and verify the fictional demo.
- [ ] Report results and the next step.

## 1. Check runtime

The agent needs network access to fetch these instructions and the installer, and
write access to the home directory to install the skill or plugin. Codex sandboxes
may deny network access or home-directory writes. If either is denied, stop and
report a **permission problem**, the blocked command/path, and the access needed.
Use the host's permission mechanism; do not treat a sandbox denial as a missing
file or switch installation methods.

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
repeat this check, otherwise stop and report. If Git is missing,
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
  claude plugin list || {
    printf '%s\n' 'FAILED: Claude plugin detection failed; see command output (check permissions)'
    exit 1
  }
else
  printf '%s\n' 'Claude CLI unavailable; plugin list not applicable to this host'
fi
if command -v npx >/dev/null 2>&1; then
  npx -y skills ls -g || {
    printf '%s\n' 'FAILED: Skills CLI detection failed; see command output (check network/home permissions)'
    exit 1
  }
fi
printf '%s\n' 'Detection complete; inspect results before installing'
```

Inspect the output, including disabled or project-scoped project-inventory plugins.
Symlinks pointing to the same skill count as one method. For other agents, also
inspect their known skill directories as well as the Skills CLI listing above
to detect agent-specific installs.
A failed plugin list on a Claude Code host makes detection incomplete: stop rather
than risk a duplicate. Preserve broken symlinks and incomplete installations too;
report them as failures instead of replacing them. If the skill directory can be
located, run step 4 to list all missing files before reporting the failure.

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
`PI_SKILL` and its method: Skills CLI, Claude Code plugin, manual Codex copy, or
manual Hermes copy. Use the installer listing/metadata and symlink target to
identify the method; a Codex/Hermes path alone does not prove a manual copy.
If the method is unclear, report it as unknown rather than guess an update command.
Run step 4's file checks even for an incomplete existing installation; never repair
it by overwriting files. If metadata shows an older version, record that version
for the update proposal in step 5.

## 4. Self-check using only the bundled demo

Set `PI_SKILL` to the absolute directory found in step 3 **in the same shell call**
as this entire block. Do not assume a repository checkout or the current directory.
Keep the temporary demo so the user can open the page. Every script receives the
explicit demo directory, never the default inventory home.

```sh
(
  PI_CHECK='starting self-check'
  trap 'pi_status=$?; if [ "$pi_status" -ne 0 ]; then printf "SELF-CHECK FAILED: %s (exit %s)\n" "$PI_CHECK" "$pi_status" >&2; fi' 0
  set -eu
  PI_CHECK='PI_SKILL must name the installed skill directory from step 3'
  test -n "${PI_SKILL:-}"
  PI_CHECK='required files missing or unreadable; existing installation left untouched'
  pi_missing=0
  for pi_file in \
    SKILL.md \
    reference/demo.py \
    reference/example-inventory.json \
    reference/demo-tasks.json \
    scripts/collect.py \
    scripts/build.py \
    scripts/validation.py \
    scripts/template.html
  do
    if [ ! -f "$PI_SKILL/$pi_file" ]; then
      printf 'MISSING: %s\n' "$PI_SKILL/$pi_file" >&2
      pi_missing=1
    elif [ ! -r "$PI_SKILL/$pi_file" ]; then
      printf 'PERMISSION PROBLEM: cannot read %s\n' "$PI_SKILL/$pi_file" >&2
      pi_missing=1
    fi
  done
  test "$pi_missing" -eq 0
  PI_CHECK='could not create temporary demo directory; check temporary-directory permissions'
  PI_DEMO=$(mktemp -d "${TMPDIR:-/tmp}/project-inventory-demo.XXXXXX")
  PI_CHECK='demo generation failed; see command output (check execution/write permissions)'
  python3 "$PI_SKILL/reference/demo.py" "$PI_DEMO"
  PI_CHECK='demo collection failed; see command output (check execution/write permissions)'
  python3 "$PI_SKILL/scripts/collect.py" "$PI_DEMO"
  PI_CHECK='demo HTML build failed; see command output (check execution/write permissions)'
  python3 "$PI_SKILL/scripts/build.py" "$PI_DEMO"
  PI_CHECK='demo output index.html is missing or empty'
  test -s "$PI_DEMO/out/index.html"
  PI_CHECK='could not print self-check result'
  printf 'SELF-CHECK OK: %s/out/index.html\n' "$PI_DEMO"
)
```

On failure, include every `MISSING:` line and the `SELF-CHECK FAILED:` reason in
the final report. If the host denies a file probe, report a permission problem
instead of concluding the file is absent. For a stale/incomplete existing install,
include the update proposal below and stop without changing its files.

This verifies demo generation, collection and HTML generation. It does not verify
browser layout or that a running host has reloaded the installed skill.

## 5. One final report

Report once, in the user's language:

- Status: installed, kept existing, or failed; current agent and installation method.
- Absolute installation path, or the blocker and manual-install link if unsupported.
- Runtime versions; self-check commands and their actual output; absolute demo page path.
- Browser layout and host loading: UNVERIFIED unless actually checked.
- Confirm user configuration, schedules and publishing were not changed.
- For an existing stale/incomplete install: name its method, every missing file
  (or the observed older version), and the matching update command below. State
  that files were preserved and ask **"May I update this existing installation
  using this command?"** Wait for approval; do not run an update in this workflow.
  If the method is unknown, report the missing method evidence and manual-install
  link; do not choose an updater.
- For permission failures: name the denied network/home operation and required
  permission, along with the failed command and actual output.
- On success, next step: reload plugins/start a new host session, then run
  `/project-inventory:project-inventory` for the Claude Code plugin, or invoke the
  standalone skill with “inventory my projects” to configure the user's projects.

Propose only the update matching the detected method, from the README:

| Existing method | Update to show the user (do not execute without approval) |
| --- | --- |
| Skills CLI | `npx skills update project-inventory -g` |
| Claude Code plugin | `claude plugin marketplace update project-inventory` then `claude plugin update project-inventory` |
| Manual Codex copy | From the updated repository checkout, rerun the README Codex `mkdir`, `cp`, `test` block: `cp -R skills/project-inventory/. ~/.codex/skills/project-inventory/` |
| Manual Hermes copy | From the updated repository checkout, rerun the README Hermes `mkdir`, `cp`, `test` block: `cp -R skills/project-inventory/. ~/.hermes/skills/project-inventory/` |

For a custom home/path, use the recorded existing destination in the matching copy
block. After an approved update, repeat step 4 before claiming success.
