# Fomor

一个持续理解用户工作与学习过程、主动发现其他解决方案的 AI 探索助手，首个适配平台为 Trae。

## 当前架构

- 采集：Trae `UserPromptSubmit` Hook，事件写入本地
- 调度与分析：Trae 自动化任务，每天在配置的时间触发（默认 03:00）
- 补跑：`SessionStart` Hook 执行 `session-start`，先校验/静默补齐环境，再补上睡眠期间错过的每日分析
- 长期记忆：`~/.fomor/` 下的文件结构（可用 `FOMOR_HOME` 覆盖）
- 交付：自动化任务对话流 + `~/.fomor/reports/`（不做独立网页）
- 反馈：次日分析时先回看用户提问，有兴趣的移入长期记忆，其余到期删除

## 快速开始

```bash
scripts/fomor init
```

采集一条事件（模拟 Trae Hook 的 stdin）：

```bash
printf '%s' '{"session_id":"demo","prompt":"如何把本地数据库迁移到云端？","hook_event_name":"UserPromptSubmit"}' | scripts/fomor hook
```

跑一次分析（默认离线 mock 模型）：

```bash
scripts/fomor analyze
scripts/fomor status
```

报告写入 `~/.fomor/reports/latest.md`。

## 目录结构

```text
scripts/
└── fomor               唯一可执行入口（单文件，无扩展名）
hooks/
└── hooks.json          UserPromptSubmit 采集 + SessionStart 环境校验/补跑
references/
├── 00-system.md        分析引擎全局规则（由 scripts/fomor 自动加载）
├── 01-aggregate.md … 06-feedback.md   各阶段提示词契约（同上）
└── 07-data-model.md    ~/.fomor/ 目录与字段说明
skills/SKILL.md   用户调用时的部署检查 + 自动化任务模板
docs/                   维护者文档，不参与运行时
tests/                  标准库 unittest
.trae-plugin/plugin.json
```

约定：

- 可执行逻辑只在 `scripts/fomor` 与 `hooks/`
- `references/` 只放静态、按需读取的参考内容（提示词契约、数据模型）
- 同一个 SOP 只写一个 skill，不按步骤拆分
- `docs/` 是维护者文档，不注入运行时

运行时数据全部在 `~/.fomor/`：`events/`、`topics/`、`discoveries/{pending,promoted}`、`tombstones/`、`reports/`、`runtime/`、`logs/`、`backup/`。仓库不携带任何数据目录；首次使用时由 `SessionStart` 静默创建。

## 接入 Trae

分工：`SessionStart` 只做静默环境校验与补跑；**自动化任务由用户手动创建**，模板在 [skills/SKILL.md](skills/SKILL.md)。

1. 插件清单 [.trae-plugin/plugin.json](.trae-plugin/plugin.json) 通过 `hooks` 字段引用 [hooks/hooks.json](hooks/hooks.json)。
2. 若 Trae 未自动加载插件 Hook：把 `hooks/hooks.json` 复制到全局 `hooks.json`，将 `${TRAE_PLUGIN_ROOT}` 替换为仓库绝对路径，然后在「设置 > Hooks」启用并信任。项目级 Hook 还需信任工作区。
3. 在 Trae「自动化」中按 SKILL 里的模板创建本地任务，触发时间用 `scripts/fomor status` 显示的 `schedule`（默认 03:00，可在 `~/.fomor/config/settings.json` 修改）。
4. 让 AI 检查部署：对它说「安装/检查 Fomor」，它会执行 `session-start --verbose`、核对 Hook、给出自动化任务模板并验收。

Hook 只写本地文件、stdout 为空、退出码始终为 0，不会阻断用户提问，也不向 Agent 注入内容。

## 开发

```bash
python3 -m py_compile scripts/fomor
tests/run.sh
```

## 文档

- [产品需求文档（PRD）](docs/PRD.md) — 产品定位、核心机制、功能设计、MVP 范围
- [待确认问题清单](docs/OPEN-QUESTIONS.md) — 未决事项、验证实验与决策顺序
- [Trae 平台能力调研](docs/TRAE-PLATFORM-RESEARCH.md) — Hooks、Skills、插件、MCP、CLI 能力与落地建议
