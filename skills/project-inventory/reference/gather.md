# Gathering through MCP

Read when a configured source cannot be read by the scripts: Notion, Linear without `LINEAR_API_KEY`, or
GitHub when `gh` is missing, logged out or denied. Write the result to `HOME/gathered/<today>.json`. `HOME` and `SCRIPTS` mean what `SKILL.md` says.

- Linear: skip this if `LINEAR_API_KEY` is set in the environment — collect.py then reads
  Linear itself (faster, exact). Otherwise: every issue of the project, archived ones included (`list_issues` with the
  confirmed project UUID (resolve legacy names uniquely first), `includeArchived: true`, `limit: 250`; it returns one page at a time — pass the
  returned `cursor` back until there is no next page).
  Map exactly as collect.py does: status type completed → `done`, canceled → `dead`, status
  name containing "review" → `wait`, everything else → `open`. Ask for the `createdAt`,
  `completedAt` and `canceledAt` fields and keep them as `created` / `completed` / `canceled`
  (the page's ticket chart is rebuilt from these dates).
- Notion: follow the connector playbook in `reference/schema.md#notion-connector-playbook`.
  Resolve database versus data source identity before querying; paginate every query and
  recursively paginate child blocks until `has_more: false`. Normalize raw statuses using
  the saved `sources.notion.status_map`; to-do `checked` maps to done/open. Preserve full
  page/block IDs, raw status, date availability and date coverage. Unknown statuses or any
  unread page/child make the source partial/failed, never a complete current list.
  This contract has offline mock coverage only; validate it in an authorized workspace
  before claiming a real Notion integration succeeded.
- GitHub Issues: only repos explicitly saved in `sources.github_issues` are read by
  collect.py using the existing `gh` access. It paginates all open and closed Issues
  (not pull requests). Open → `open`; closed → `done`; `stateReason: NOT_PLANNED` →
  `dead` (canceled). Creation/closure dates rebuild ticket trends on the first run.
  Missing/unauthenticated `gh` or a failed page stays visible as a source failure.
- GitHub PRs: scripts paginate every open PR with `gh api graphql`. If `gh` is missing,
  not logged in (`gh auth status` fails), or cannot read the repo, use GitHub MCP instead.
  Follow every returned cursor, put normalized `number`, `title`, `url`, `createdAt`,
  `isDraft`, `headRefName`, and `repo` under `prs`. Mark the per-repo source `ok` and
  `complete: true` only after the final page, including zero PRs. A denied later page is
  `failed`/`partial` with its error, never a complete short list. A fresh MCP gather takes
  precedence even when `gh` is installed; collect.py otherwise reports CLI failures.
- Create a unique `_run.run_id` for this gather. For each source write
  `run_id`, `attempted_at`, `fetched_at`, `status`, `complete`, and `error` under `sources`
  (see schema). Track MCP PRs per `github:<owner/repo>`. Never reuse a gather run.
- List every source you read in `read`. If a source fails, write the error into `errors`
  (start the text with the source name) — never drop it silently.
