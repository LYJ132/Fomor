# Fomor

一个持续理解用户工作与学习过程、主动发现其他解决方案的 AI 探索助手，首个适配平台为 Trae。

## 当前架构

- 采集：Trae `UserPromptSubmit` Hook，事件写入本地
- 调度与分析：Trae 自动化任务，每天 03:00 触发
- 补跑：`SessionStart` Hook 调用 `fomor catch-up`，补上睡眠期间错过的 03:00
- 长期记忆：`~/.fomor/` 下的文件结构（可用 `FOMOR_HOME` 覆盖）
- 交付：自动化任务对话流 + `~/.fomor/reports/`（不做独立网页）
- 反馈：次日 03:00 回看用户提问，有兴趣的移入长期记忆，其余到期删除

## 快速开始

```bash
bin/fomor init
```

采集一条事件（模拟 Trae Hook 的 stdin）：

```bash
printf '%s' '{"session_id":"demo","prompt":"如何把本地数据库迁移到云端？","hook_event_name":"UserPromptSubmit"}' | bin/fomor hook
```

跑一次分析（默认离线 mock 模型）：

```bash
bin/fomor analyze
bin/fomor status
```

报告写入 `~/.fomor/reports/latest.md`。

## 目录结构

```text
fomor/                 Python 包
├── cli.py             命令行入口
├── pipeline.py        反馈回看 → 聚合 → 理解 → 评分 → 探索 → 报告
├── feedback.py        次日隐式反馈归因与提升
├── scheduler.py       03:00 截止时间与首次唤醒补跑
├── store.py           Event / Topic / Discovery 持久化
├── llm.py             mock / traecli / openai 三种模型后端
├── prompts.py         提示词加载与渲染
└── prompts/           7 个提示词模板
tests/                 标准库 unittest
skills/                Trae Skills：fomor-setup / fomor-analyze / fomor-review
.trae-plugin/          Trae 插件清单
.trae/hooks.example.json  Hook 配置示例
bin/fomor              Hook 调用的稳定启动脚本
```

运行时数据全部在 `~/.fomor/`：`events/`、`topics/`、`discoveries/{pending,promoted}`、`tombstones/`、`reports/`、`runtime/`、`logs/`、`backup/`。仓库内的 `data/` 是早期样例，不参与运行。

## 接入 Trae

1. 参考 `.trae/hooks.example.json`，把 `/absolute/path/to/fomor` 换成真实路径，写入全局或项目 `hooks.json`，并在「设置 > Hooks」启用。
2. 在 Trae「自动化」中创建每天 03:00 的本地任务，任务内容使用 `fomor-analyze` 技能。
3. 安装细节见 `skills/fomor-setup/SKILL.md`。

Hook 只写本地文件、stdout 为空、退出码始终为 0，不会阻断用户提问，也不向 Agent 注入内容。

## 开发

```bash
python3 -m compileall fomor
python3 -m unittest discover -s tests -v
```

## 文档

- [产品需求文档（PRD）](docs/PRD.md) — 产品定位、核心机制、功能设计、MVP 范围
- [待确认问题清单](docs/OPEN-QUESTIONS.md) — 按优先级整理的所有未决事项、验证实验与决策顺序
- [Trae 平台能力调研](docs/TRAE-PLATFORM-RESEARCH.md) — Hooks、Skills、插件、MCP、CLI 能力与落地建议
