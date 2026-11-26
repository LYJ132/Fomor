# Fomor

一个持续理解用户工作与学习过程、主动发现其他解决方案的 AI 探索助手，首个适配平台为 Trae。

## 当前架构

**分析由 Agent 执行，脚本只做采集。** 不需要用户配置任何模型参数——Trae 自动化任务里的 Agent 就是分析引擎。

```text
UserPromptSubmit Hook ──► events/ 落盘（唯一脚本职责）
SessionStart Hook    ──► 静默创建/校验 ~/.fomor/
每天 <schedule> 自动化任务 ──► Agent 按 skills/SKILL.md 的 SOP 执行：
        反馈回看 → 评估 → 洞察 → 挖掘 → 报告 + 长期记忆
```

- 长期记忆：`~/.fomor/` 下的文件（topics / discoveries / reports）
- 反馈：每次分析先回看——被追问的探索提升进 topics，无人问津的到期删除
- 交付：自动化任务对话流 + `~/.fomor/reports/latest.md`

## 快速开始

```bash
scripts/fomor session-start --verbose   # 创建/校验 ~/.fomor
printf '%s' '{"session_id":"demo","prompt":"如何把本地数据库迁移到云端？"}' | scripts/fomor hook
scripts/fomor status
```

分析不需要跑命令：让 Agent 读 `skills/SKILL.md` 的「每日分析 SOP」执行即可（或由自动化任务每天自动执行）。

## 目录结构

```text
scripts/
└── fomor               唯一脚本（~10KB）：hook 采集 / session-start / status
hooks/
└── hooks.json          UserPromptSubmit 采集 + SessionStart 环境校验
skills/
└── SKILL.md            唯一流程文档：部署 SOP + 分析 SOP（评估→洞察→挖掘）
docs/                   维护者文档，不参与运行时
tests/                  标准库 unittest
.trae-plugin/plugin.json
```

复杂度控制：

- 脚本只做三件事：采集、环境校验、状态概览；没有分析管线、模型后端、调度器、备份
- 模型文件为零：分析方法是 SOP 里的推理链（Agent 读取并执行）
- 数据只有 5 类：events / topics / discoveries / reports / runtime（含一个 state.json）

## 接入 Trae

1. 把 [hooks/hooks.json](hooks/hooks.json) 内容合并到全局 `hooks.json`（`${TRAE_PLUGIN_ROOT}` 替换为仓库绝对路径），在「设置 > Hooks」启用。
2. 对 Agent 说「安装/检查 Fomor」：它执行 `session-start --verbose`、核对 Hook、**代用户创建**每天 `<schedule>` 的自动化任务（任务内容见 SKILL 的 A3 模板）并验收。
3. 之后无需人工干预；日常查看 `cat ~/.fomor/reports/latest.md`。

## 开发

```bash
python3 -m py_compile scripts/fomor
tests/run.sh
```

## 文档

- [产品需求文档（PRD）](docs/PRD.md) — 产品定位、核心机制、功能设计、MVP 范围
- [待确认问题清单](docs/OPEN-QUESTIONS.md) — 未决事项、验证实验与决策顺序
- [Trae 平台能力调研](docs/TRAE-PLATFORM-RESEARCH.md) — Hooks、Skills、插件、MCP、CLI 能力与落地建议
