# Fomor

一个持续理解用户工作与学习过程、主动发现其他解决方案的 AI 探索助手，首个适配平台为 Trae。

## 当前架构

- 采集：Trae `UserPromptSubmit` Hook，事件写入本地
- 调度与分析：Trae 自动化任务，每天 03:00 触发
- 补跑：`SessionStart` Hook 调用 `catch-up`，补上睡眠期间错过的 03:00
- 长期记忆：`~/.fomor/` 下的文件结构（可用 `FOMOR_HOME` 覆盖）
- 交付：自动化任务对话流 + `~/.fomor/reports/`（不做独立网页）
- 反馈：次日 03:00 回看用户提问，有兴趣的移入长期记忆，其余到期删除

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
├── fomor               唯一可执行入口（无扩展名，Hook 与分析命令调用）
└── lib/fomor/          Python 包
    ├── cli.py          命令行
    ├── pipeline.py     反馈回看 → 聚合 → 理解 → 评分 → 探索 → 报告
    ├── feedback.py     次日隐式反馈归因
    ├── scheduler.py    03:00 截止时间与首次唤醒补跑
    ├── store.py        Event / Topic / Discovery 持久化
    ├── llm.py          mock / traecli / openai
    └── prompts.py      读取 references/ 中的提示词
hooks/
└── hooks.json          UserPromptSubmit 采集 + SessionStart 补跑
references/
├── 00-system.md        分析引擎全局规则
├── 01-aggregate.md … 06-feedback.md
└── 07-data-model.md    ~/.fomor/ 目录与字段
skills/fomor/SKILL.md   完整操作 SOP（安装、分析、查看、排障）
docs/                   维护者文档，不参与运行时
tests/                  标准库 unittest
.trae-plugin/plugin.json
```

约定：

- 可执行逻辑只放 `scripts/` 与 `hooks/`
- `references/` 只放静态、按需读取的参考内容（提示词契约、数据模型）
- 同一个 SOP 只写一个 skill，不按步骤拆分
- `docs/` 是维护者文档，不注入运行时

运行时数据全部在 `~/.fomor/`：`events/`、`topics/`、`discoveries/{pending,promoted}`、`tombstones/`、`reports/`、`runtime/`、`logs/`、`backup/`。仓库内的 `data/` 是早期原型样例，不参与运行。

## 接入 Trae

1. 插件清单 [.trae-plugin/plugin.json](.trae-plugin/plugin.json) 通过 `hooks` 字段引用 [hooks/hooks.json](hooks/hooks.json)。
2. 若 Trae 未自动加载插件 Hook：把 `hooks/hooks.json` 复制到全局 `hooks.json`，将 `${TRAE_PLUGIN_ROOT}` 替换为仓库绝对路径，然后在「设置 > Hooks」启用并信任。项目级 Hook 还需信任工作区。
3. 在 Trae「自动化」中创建每天 03:00 的本地任务，任务内容使用 `fomor` 技能。
4. 完整步骤见 [skills/fomor/SKILL.md](skills/fomor/SKILL.md)。

Hook 只写本地文件、stdout 为空、退出码始终为 0，不会阻断用户提问，也不向 Agent 注入内容。

## 开发

```bash
python3 -m compileall scripts/lib/fomor
tests/run.sh
```

## 文档

- [产品需求文档（PRD）](docs/PRD.md) — 产品定位、核心机制、功能设计、MVP 范围
- [待确认问题清单](docs/OPEN-QUESTIONS.md) — 未决事项、验证实验与决策顺序
- [Trae 平台能力调研](docs/TRAE-PLATFORM-RESEARCH.md) — Hooks、Skills、插件、MCP、CLI 能力与落地建议
