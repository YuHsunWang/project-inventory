# project-inventory

[English](README.md) | [繁體中文](README.zh-TW.md) | **简体中文**

[![CI](https://github.com/YuHsunWang/project-inventory/actions/workflows/ci.yml/badge.svg)](https://github.com/YuHsunWang/project-inventory/actions/workflows/ci.yml) [![Pages](https://github.com/YuHsunWang/project-inventory/actions/workflows/pages.yml/badge.svg)](https://github.com/YuHsunWang/project-inventory/actions/workflows/pages.yml) [![Latest release](https://img.shields.io/github/v/release/YuHsunWang/project-inventory)](https://github.com/YuHsunWang/project-inventory/releases/latest) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> 为同时管理多个项目的人提供一页总览：了解各项目的运行流程、最近的变更、等待你处理的任务，以及哪些数据已经过期。

这是一份可跨工具使用的 [Agent Skill](https://agentskills.io/specification)，通过 [Skills CLI](https://skills.sh) 一条命令即可安装到多种智能体，也支持作为原生 Claude Code 插件安装。

![示例仪表盘：首页、项目和展开的步骤](skills/project-inventory/reference/demo.gif)

[在线演示 — 仅含示例数据](https://yuhsunwang.github.io/project-inventory/)

[桌面端 PNG](skills/project-inventory/reference/demo-desktop.png) · [移动端 PNG](skills/project-inventory/reference/demo-mobile.png)。GIF 和 PNG 仅使用示例数据。PNG 是 Chromium 在 1280、390 px 下截取的画面，不含真实项目信息或外部 API 的运行结果。

繁体中文详细手册：[說明書.md](說明書.md)。

## 目录

- [为什么使用 project-inventory？](#为什么使用-project-inventory)
- [调用方式](#调用方式)
- [安装](#安装)
- [卸载](#卸载)
- [使用方法](#使用方法)
- [无需账号的本地演示](#无需账号的本地演示)
- [环境要求](#环境要求)
- [发布与隐私](#发布与隐私)
- [脚本](#脚本)
- [定时刷新与 AI 文本](#定时刷新与-ai-文本)
- [验证状态](#验证状态)
- [常见问题](#常见问题)
- [目录结构](#目录结构)
- [许可证](#许可证)

---

## 为什么使用 project-inventory？

项目的信息分散在本地代码目录、工单、笔记和数据文件中。这个技能将各个来源汇总成一个页面，并在首页列出所有项目中等待你处理的事项。

| 来源 | 提供的内容 |
|---|---|
| 本地 Git 工作副本 | 分支、未提交文件、历史记录、远程仓库和未推送提交 |
| GitHub | 尚未关闭的 PR；仅从明确配置的 GitHub Issues 仓库读取工单 |
| Linear／Notion | 工单：已完成、等待审核、未完成、已取消 |
| Obsidian | Markdown 笔记中未完成的任务（`- [ ]`） |
| CSV／JSON／JSONL／SQLite／Parquet／DuckDB | 读取文件内容中的最新日期，而非文件时间戳 |

| 各项目页面 | 显示内容 |
|---|---|
| 运行流程 | 每个步骤都有图标；根据代码生成草稿，经你确认后保存。可展开截图、公式或输入／输出示意。 |
| 工单 | 已完成、等待你审核、未完成和已取消的任务 |
| 本地信息 | 工作副本、分支、未提交文件、数据文件和 Obsidian 笔记 |
| 云端信息 | 各工作副本的远程仓库和未推送提交、未关闭的 PR、Linear 项目、Notion 页面 |
| 数据时效 | 每份监控数据集内部的最新日期 |
| 趋势 | 每周提交次数，以及近 90 天未完成／已完成工单的变化；根据已知日期还原，并标注未知时段和不完整的日期覆盖范围。 |
| 每周进展 | 从第一条记录开始，每周用 2–3 句话说明，可展开查看每次提交、已完成工单和新建 PR。先显示 4 周，每次再加载 4 周。 |

页脚只列出已配置的工单来源。未配置来源的项目显示“未设置工单来源”。未配置工单或本地 Git 历史时，进度页会隐藏空的趋势图；来源读取失败仍会显示。

## 调用方式

| 工具／安装方式 | 如何调用 |
|---|---|
| Claude Code 插件 | `/project-inventory:project-inventory` |
| 独立技能 | `/project-inventory` |
| 任何智能体 | 直接说“inventory my projects”或「盤點專案」 |
| 其他可执行 shell 命令的工具 | 让工具读取 `skills/project-inventory/SKILL.md` 并按照其中的说明执行 |

插件命名空间来自 `.claude-plugin/plugin.json`。参见 [Claude Code 插件加载规则](https://code.claude.com/docs/en/plugins)。

> **Notice:** 安装“已验证”表示命令执行完成，文件已就位。运行行为仅在 Claude Code 和 Codex 上验证过，未记录宿主版本；仓库正式的宿主加载及服务验收限制仍见[验证状态](#验证状态)。

> **Tip:** 安装或替换后，请重新加载插件或启动新的工具会话。

## 安装

### Skills CLI：适用于多种智能体

以下命令默认安装到用户范围：

```sh
# install
npx skills add YuHsunWang/project-inventory -g
npx skills ls -g
# update
npx skills update project-inventory -g
```

2026-10-17 已在隔离的主目录中完成安装检查：技能和全部脚本安装到了 `~/.agents/skills/project-inventory`，由 Codex 和其他 universal 智能体共享，并通过符号链接提供给 Claude Code。`npx skills ls -g` 列出了 Claude Code 和 Codex。

### Claude Code 插件

```sh
# install
claude plugin marketplace add YuHsunWang/project-inventory
claude plugin install project-inventory@project-inventory --scope user
# update
claude plugin marketplace update project-inventory
claude plugin update project-inventory
```

> **Tip:** 会话中的 `/plugin install` 会询问安装范围，请选择 **User**。启动新会话或重新加载插件后，执行 `/project-inventory:project-inventory`。

### 手动复制 Codex 独立技能

安装技能不需要额外的 MCP 服务器。首次手动安装时，克隆一次仓库并进入工作目录：

```sh
# install — obtain the checkout once for either manual copy below
git clone https://github.com/YuHsunWang/project-inventory
cd project-inventory
# update — enter your existing, updated checkout and repeat the matching copy below
```

```sh
# install
mkdir -p ~/.codex/skills/project-inventory
cp -R skills/project-inventory/. ~/.codex/skills/project-inventory/
test -f ~/.codex/skills/project-inventory/SKILL.md && echo "Codex skill files OK"
# update — from your updated checkout
mkdir -p ~/.codex/skills/project-inventory
cp -R skills/project-inventory/. ~/.codex/skills/project-inventory/
test -f ~/.codex/skills/project-inventory/SKILL.md && echo "Codex skill files OK"
```

### 手动复制 Hermes 独立技能

使用同一份仓库工作副本：

```sh
# install
mkdir -p ~/.hermes/skills/project-inventory
cp -R skills/project-inventory/. ~/.hermes/skills/project-inventory/
test -f ~/.hermes/skills/project-inventory/SKILL.md && echo "Hermes skill files OK"
# update — from your updated checkout
mkdir -p ~/.hermes/skills/project-inventory
cp -R skills/project-inventory/. ~/.hermes/skills/project-inventory/
test -f ~/.hermes/skills/project-inventory/SKILL.md && echo "Hermes skill files OK"
```

即使工具的主目录已经存在但没有 `skills` 文件夹，这两种复制方法也适用。更新现有安装或重新安装时，在已有仓库目录中执行对应的 `mkdir`、`cp` 和 `test`。文件会原地更新，其他技能会保留，也不会多嵌套一层 `project-inventory`。完成后启动新的工具会话。Linear、Notion 需要该智能体自己的连接器；Linear 也可以使用 `LINEAR_API_KEY`。

### 项目范围（替代方案）

如果希望将 Claude Code 插件安装到当前项目，而不是用户范围：

```sh
# install
claude plugin marketplace add YuHsunWang/project-inventory
claude plugin install project-inventory@project-inventory --scope project
# update
claude plugin marketplace update project-inventory
claude plugin update project-inventory
```

## 卸载

只运行与你的安装方式对应的命令。手动复制方式的删除命令只移除该技能文件夹。

```sh
# Skills CLI — user scope
npx skills remove project-inventory -g
# Claude Code plugin — user scope
claude plugin uninstall project-inventory@project-inventory --scope user
# Claude Code plugin — project scope alternative
claude plugin uninstall project-inventory@project-inventory --scope project
# Manual Codex copy
rm -r ~/.codex/skills/project-inventory
# Manual Hermes copy
rm -r ~/.hermes/skills/project-inventory
```

## 使用方法

| 执行时机 | 处理流程 |
|---|---|
| 首次运行 | 智能体询问要纳入哪些项目、各项目位于何处；逐个确认工单来源是 Linear／Notion／GitHub Issues／none 并保存配置。配置 PR 仓库不会自动启用 Issues。工具会找出数据文件供你选择，再生成流程图草稿供你确认。 |
| UI 配置 | 查找现有网址或 HTML 输出，建议为哪些步骤截图，截图后先展示再保存；也可以提供已有截图。没有 UI 的项目不会显示截图占位。工具不会启动项目服务器，也不会执行项目代码或构建。 |
| 后续运行 | 重新读取所有来源并重建页面。补充缺少摘要或摘要生成后又有新工作的周，通常只涉及本周。首次运行需要覆盖过去所有周，因此耗时更长。 |

配置保存在 `~/.project-inventory/inventory.json`。每周摘要保存在 `~/.project-inventory/summaries.json`，一周结束后不会再改写。截图说明显示 `captured_at`，并注明来源是线上网站还是本地构建输出；HTML 中不包含截图来源网址。

### Git 与任务来源细节

| 来源 | 采集规则 |
|---|---|
| 本地 Git | 默认获取 `origin`，更新远程引用和 `.git/FETCH_HEAD`。在单个 `sources.local[]` 条目中设置 `"fetch": false` 后，仍会读取 HEAD、分支、未提交文件和历史记录，但领先／落后及相对远程仓库的未推送数量显示为未知。历史范围默认为 `git log --all`；`"history": "head"` 仅包含从 HEAD 可达的提交。进度页标注各工作副本的范围。未连接或读取失败的历史会在项目卡片和首页列表中显示为未采集，并附来源错误。 |
| GitHub Issues | 明确设置 `sources.github_issues: ["owner/repo"]`。采集所有未关闭和已关闭的 issue，排除 PR，根据创建／关闭日期重建趋势。以不再计划处理为由关闭的条目算已取消，其他已关闭条目算已完成。缺少 `gh` 访问权限或任何一页未能读取，都会显示来源失败。现有配置仍然有效。 |
| Obsidian | 配置时先询问哪些文件夹包含实际任务。每个来源递归扫描笔记库 `path` 下的 Markdown；可选的 `exclude` 文件夹相对于该路径。跳过 `.obsidian`、`.trash`、围栏代码块和空白复选框。同一来源中，完整文本经 `strip()` 后完全相同的任务只计一次，不做模糊匹配。任一副本已勾选就算完成，否则算未完成。列表指向包含未完成副本的最新文件，沿用路径字典序，不解析日期，也不使用修改时间。计数包含全部去重后的任务，列表只显示前 50 个未完成任务。无需新增配置。 |

## 无需账号的本地演示

在仓库工作目录中，使用尚不存在的演示目录：

```sh
mkdir -p .tmp
export TMPDIR="$PWD/.tmp"
python3 skills/project-inventory/reference/demo.py .tmp/demo
python3 skills/project-inventory/scripts/collect.py .tmp/demo
python3 skills/project-inventory/scripts/build.py .tmp/demo
python3 tests/demo_fixture.py .tmp/demo --offline-fonts
python3 skills/project-inventory/scripts/check_page.py .tmp/demo --shots .tmp/demo-shots
```

打开 `.tmp/demo/out/index.html`。辅助工具根据 `example-inventory.json` 生成配置，创建 3 个虚构项目：Web 应用、数据流水线和写作项目。每个项目都有本地 Git 历史、Markdown 待审核任务和示例 CSV，其中一份数据被故意设为过期。不需要账号、令牌或网络；已有 inventory 时工具会拒绝覆盖。collect／build 只需 Python 和 git；可选的浏览器检查还需要下文列出的 Playwright／Chromium。offline-fonts 辅助工具使用备用字体，避免请求字体 CDN。

要从全新的示例数据构建重新生成动画，需要 Playwright、Chromium 和 Pillow：

```sh
python3 skills/project-inventory/reference/demo_gif.py
```

## 环境要求

| 功能 | 需要什么 |
|---|---|
| 基础功能 | Python 3.9 及以上、git |
| Linear 工单 | Claude 中的 Linear MCP 连接器，或环境变量 `LINEAR_API_KEY`（更快，脚本无需 Claude 即可读取 Linear） |
| Notion 工单 | Claude 中的 Notion MCP 连接器 |
| GitHub Issues 工单 | 已登录的 `gh` CLI；明确确认的 `sources.github_issues` 仓库 |
| GitHub PR | 已登录的 `gh` CLI，或 GitHub MCP 连接器 |
| Parquet／DuckDB 数据检查 | `pip install duckdb` |
| UI 截图／页面检查 | `pip install playwright && python3 -m playwright install chromium`（可选） |
| Vercel 发布 | 已登录的 Vercel CLI（`vercel login`） |

## 发布与隐私

页面发布到哪里由你选择，默认保存在本地。

| 选项 | 谁能访问 |
|---|---|
| 本地文件 `~/.project-inventory/out/index.html` | 只有你 |
| 手动导入 claude.ai Artifact 的 HTML | 取决于宿主；发布、分享和访问权限尚未验证 |
| Vercel | Vercel 授权用户；实际访问范围取决于团队／项目成员身份、授权、分享和 bypass 设置（[访问规则](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments/vercel-authentication)）。首次部署前启用保护，每次部署后都从外部检查。 |
| GitHub Pages | **所有人**。首次发布前智能体会先询问。 |

`build.py` 还会生成 `out/artifact.html`：一个保留样式、脚本和页面内容，去掉文档外壳及 meta 标签的 HTML 片段，供兼容宿主手动导入。仓库没有 Artifact 发布 API、宿主能力检测或 artifact identity 保存机制；相同文件路径不保证相同网址。端到端导入／发布验收仍**待完成**。宣称支持前，需要记录宿主和版本，测试创建／更新 identity、固定网址、外部字体／MathJax 脚本、CSP 处理及分享权限。目前不保证私有访问或固定网址。

### GitHub Pages 套餐与预览

| 仓库／套餐 | 标准 Pages 路径 |
|---|---|
| GitHub Free、公开仓库 | 支持；仓库和网站均公开 |
| GitHub Free、私有仓库 | 不支持。保留本地页面或选择其他宿主，不可自动更改仓库可见性。 |
| GitHub Pro／Team、私有仓库 | 支持；仓库保持私有，但标准网站公开 |

参见 [GitHub 套餐要求](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)。Enterprise 的访问受限 Pages 是另一种方案，本流程尚未验证。

> **Notice:** 发布前先预览本地页面及内嵌资源。项目名称、工单、分支、文件路径和截图可能被公开。创建仓库或推送前，确认账号套餐、仓库可见性和确切的公开内容。

若只需要公开最少信息，请另建一个 inventory 主目录，只保留已批准公开的项目名称／标签／流程文字，将 `sources` 和 `data` 留空，省略 `notes`、节点的 `paths` 和 `media`。对该目录重新执行 collect、build 并预览。目前没有自动脱敏开关。

`publish_vercel.py` 不会覆盖并非由它创建的 Vercel 项目；若确定要使用现有项目，添加 `--reuse` 执行一次。未设置 `VERCEL_TOKEN` 时，程序先运行 `vercel whoami`，再读取 CLI 凭证。凭证刷新失败会停止发布并提示登录。

## 脚本

脚本位于 `skills/project-inventory/scripts/`，可以脱离 Claude 运行。手动使用前先克隆仓库；插件自己的副本位于 Claude 插件目录。以 [example-inventory.json](skills/project-inventory/reference/example-inventory.json) 为起点，手动编写 `~/.project-inventory/inventory.json`。

```sh
S=skills/project-inventory/scripts
python3 $S/collect.py ~/.project-inventory     # git, gh PRs/opted-in Issues, Obsidian tasks, data checks -> facts/<date>.json
python3 $S/capture_shots.py ~/.project-inventory # existing UI URLs/HTML -> shots/, updates shot paths
python3 $S/build.py   ~/.project-inventory     # -> out/index.html
python3 $S/check_page.py ~/.project-inventory  # headless browser check, every tab and step, 390 + 1280 px
python3 $S/publish_vercel.py ~/.project-inventory <vercel-project-name>
```

脱离 Claude 运行时，脚本不会刷新 Notion；Linear 则需要设置 `LINEAR_API_KEY`。未启用可选的文本 CLI 时，也不会生成每周摘要，新的一周显示“还没有摘要”，直到下一次 Claude 运行。`build.py` 在 `out/summaries-needed.json` 中列出待补内容。

使用 `python3 collect.py HOME --refresh` 执行一次刷新，只构建该次运行的快照。

| 退出码 | 含义／处理方法 |
|---|---|
| 0 | 成功 |
| 1 | 部分采集成功；页面显示失败的来源 |
| 2 | 严重失败；修复输入或权限后重试，不可发布。 |

`refresh.json` 记录本次运行和具体快照。严重失败时保留上一版页面的数据及时间，并显示失败摘要。独立运行的 build 会检查这份清单；没有清单的旧主目录仍可构建。文件格式见 [schema.md](skills/project-inventory/reference/schema.md)。

## 定时刷新与 AI 文本

Setup 时可选择启用无人值守刷新。`auto_refresh.model` 可选 `none`（默认，不调用 AI）、`claude`（Haiku）或 `codex`（gpt-6-luna）。只有获得同意后才会预览并安装一项系统定时任务：macOS／Linux 使用 cron，Windows 使用 schtasks。

以下命令使用[脚本](#脚本)一节设置的 `S`。

```sh
python3 $S/schedule.py print ~/.project-inventory
python3 $S/schedule.py install ~/.project-inventory  # only after reviewing the printed command
python3 $S/schedule.py remove ~/.project-inventory
python3 $S/auto_refresh.py ~/.project-inventory     # run once without installing anything
```

| 行为 | 细节 |
|---|---|
| 定时任务 | 计算机本地时间 08:00–22:00，每 2 小时一次，包含起止时间。可通过 `--every`、`--start`、`--end` 或 schema 中的 `auto_refresh.schedule` 调整。安装时只替换该主目录的标记条目，并保存供 git／gh／codex／claude／vercel 使用的 PATH。`LINEAR_API_KEY` 应放在定时任务环境中，不要写入打印的命令。移动技能或 CLI 后需要重新安装定时任务。不会安排聊天会话。 |
| 截图 | 检查指纹前，重新截取已保存的 `media.capture` 网址／HTML。失败时打印 `WARN`、保留旧图，下次重试；相同图片保持不变。 |
| 变更与锁 | 来源指纹和日期均相同时，跳过 collect／build／模型／发布。脚本读取失败时一定重试并显示错误；数据时效仍读取数据内容中的日期。手动与自动采集共用操作系统锁，进程崩溃后立即释放；仍在运行的任务不会因时间过长被移除。 |
| AI 摘要与说明 | 启用文本 CLI 后，每个项目批量调用一次，补充缺少的每周摘要和未缓存的 commit／PR 说明；失败则保留待补内容。 |
| 需要 Claude 协助 | 顶部仅列出需要重读的 MCP 来源、缺少的每周摘要和 Artifact 手动发布，每项均附完整的 `/project-inventory` 命令。 |
| 发布 | 有变更时始终先构建本地 HTML。Vercel（`publish.to: vercel`、`project`、可选 `team`）只在页面哈希改变时，通过受保护的发布程序部署。GitHub Pages 不会自动发布；Artifact 仍需手动发布。 |

### 流程文本更新与撤销

启用文本 CLI 后，提交如果涉及步骤的 `paths`，可以直接更新 `inventory.json` 中的 `title`、`sub` 和 `zone`。不会新增步骤、路径、详细说明或媒体；新增步骤需要先检查新文件，再手动加入（见 [SKILL.md](skills/project-inventory/SKILL.md) 中的 Setup）。`none` 会同时关闭步骤改写和说明。

首次运行只记录各工作副本的 HEAD。之后，同一项目的所有变更步骤共用一次只读会话，按 inventory 时区，每个自然日最多一次。模型可以读取项目，仓库内容一律视为数据。相对路径以各工作副本为基准解析；其中的绝对路径和 `~` 路径也会计入，所有工作副本以外的路径则忽略。不符合要求的步骤回复会保留先前检查的提交，留待之后的日期重试；有效的空对象表示无需修改。

更新后的方框显示“AI 自动更新（YYYY-MM-DD）”。旧文本保存在 `step_history.json`，检查过的提交及每日会话日期保存在 `state/steps.json`。要撤销某个步骤最近一次改写并在本地重建页面：

```sh
python3 $S/auto_refresh.py ~/.project-inventory --revert-step PROJECT_KEY STEP_ID
python3 $S/auto_refresh.py ~/.project-inventory
```

撤销只恢复文本并移除标签，保留节点的其他配置。如果改写后曾手动编辑任何步骤文本，就会拒绝撤销。模型会话失败也会占用当天额度，但不会推进相关步骤的检查提交。

## 验证状态

`inventory.json` 加上本次 MCP／API 读取 → `collect.py` → 已验证的运行快照与 `refresh.json` → `build.py` → HTML → 可选浏览器检查／经批准的发布。每周摘要由 AI 助手撰写，Python 不会自行生成；来源失败仍会显示。

下表将正式宿主加载验收与前述安装、运行检查分开记录。特定宿主版本的验收仍待完成。

| 宿主 | 验证范围／版本 |
|---|---|
| Claude Code 插件 | 预期兼容；未验证宿主版本。待人工重新加载／启动新会话，再执行 `/project-inventory:project-inventory` 验收加载。 |
| Codex 独立技能 | 已测试全新主目录、现有安装和重新安装的文件结构；未验证宿主版本。新会话中的实际加载待人工验收。 |
| Hermes 独立技能 | 同样测试过文件安装；预期兼容，未验证宿主版本。新会话中的实际加载待人工验收。 |

| 路径 | 当前支持范围 |
|---|---|
| 本地 Git、CSV／JSON／JSONL／SQLite、笔记 | Python 采集和回归测试，不需要服务连接器 |
| Parquet／DuckDB | 可选 DuckDB 包；有真实来源的回归验证 |
| GitHub／Linear | `gh`／API key 或本次 MCP 读取；需要登录来源服务 |
| Notion | 助手连接器流程有离线 mock 测试；真实工作区验收待完成 |
| 宿主技能加载／Artifact 发布 | 宿主及版本的人工验收待完成 |
| 页面布局 | Headless Chromium 检查桌面／移动端尺寸；浏览器依赖可选 |

完整检查：`python3 tests/release_gate.py`。GitHub CI 在推送／PR 到 main 时运行相同命令。[触发评估](evals/README.md) 需要 Claude 凭证；离线检查仅验证用例配置，不代表实测触发率。用例衡量技能是否被调用，不评估页面质量或配置行为。

开发与反馈：[CONTRIBUTING.md](CONTRIBUTING.md)。变更记录：[CHANGELOG.md](CHANGELOG.md)。

## 常见问题

| 现象 | 检查方法 |
|---|---|
| 找不到插件命令 | 重新加载插件或启动新会话；插件使用 `/project-inventory:project-inventory`，独立技能使用 `/project-inventory`。 |
| 脚本没有刷新 Notion、Linear 或每周摘要 | Notion 需要助手连接器；Linear 需要连接器或 `LINEAR_API_KEY`；摘要需要启用文本 CLI 或等待下次 Claude 运行。 |
| 来源失败／刷新退出码为 1 或 2 | 查看页面中的来源错误及 `refresh.json`，修复输入／权限后重试。退出码为 2 时不可发布。 |
| 趋势图为空 | 配置工单来源及／或本地 Git 历史；未知或不完整的工单日期会另行标注。 |
| Vercel 拒绝使用现有项目 | 仅在确定要使用该项目时，添加 `--reuse` 执行一次。 |
| Vercel 凭证刷新失败 | 按提示登录；未设置 `VERCEL_TOKEN` 时，发布前必须成功运行 `vercel whoami`。 |
| 截图失败 | 打印 `WARN` 并保留旧图，下次重试；不会启动项目服务器或执行构建。 |
| 流程步骤拒绝撤销 | AI 改写后文本曾被编辑，保护机制会保留你的修改。 |

## 目录结构

```text
project-inventory/
├── .claude-plugin/
│   ├── plugin.json                 # plugin identity and version
│   └── marketplace.json            # Claude Code marketplace entry
├── .github/workflows/
│   ├── ci.yml                      # offline release gate
│   └── pages.yml                   # sample-only Pages demo
├── skills/project-inventory/
│   ├── SKILL.md                    # setup and refresh instructions
│   ├── scripts/                    # collect, build, capture, schedule, publish
│   └── reference/                  # schema, example config, demo and screenshots
├── evals/                          # trigger cases and instructions
├── tests/                          # regressions and release gate
├── README.md                       # English
├── README.zh-TW.md                  # Traditional Chinese
├── README.zh-CN.md                  # Simplified Chinese
├── 說明書.md                         # detailed Traditional Chinese manual
├── CONTRIBUTING.md
├── CHANGELOG.md
└── LICENSE
```

全部盘点状态默认保存在 `~/.project-inventory`：`inventory.json` 是配置，`gathered/<date>.json` 是 MCP 读取结果，`facts/<date>.json` 是快照，`summaries.json` 是每周摘要，`shots/` 是截图，`out/` 是生成的页面。

## 许可证

[MIT](LICENSE)。
