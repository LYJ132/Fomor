# Fomor

一个持续理解用户工作与学习过程、主动发现其他解决方案的 AI 探索助手，首个适配平台为 Trae。

## 当前架构

**分析由 Agent 执行，机械步骤全部代码化。** 不需要用户配置任何模型参数——Trae 自动化任务里的 Agent 就是分析引擎。

```text
UserPromptSubmit Hook ──► events/ 落盘（hook）
SessionStart Hook    ──► 静默创建/校验 ~/.fomor/（session-start）
每天 <schedule> 自动化任务 ──► Agent 按 skills/SKILL.md 的 SOP：
        prepare（一行命令：收集窗口+档案，代码顺带清理过期数据）
        → 反馈回看（learn 写认知档案）
        → 评估 → 洞察 → 挖掘
        → 写报告 + finish（提交 pending，更新 last_analyzed_at）
```

- **不存话题**：用户真感兴趣的话题每天都会再问出来，不需要额外记录
- **长期记忆 = 他已知什么**：`profile.json` 只记 known / dislikes，作用是避免重复推荐、判断认知水位
- **短期判断极短**：上一轮的探索结论只活到本次分析，对照完新提问就处置
- 交付：自动化任务对话流 + `~/.fomor/reports/latest.md`

## 快速开始

```bash
scripts/fomor session-start --verbose   # 创建/校验 ~/.fomor
printf '%s' '{"session_id":"demo","prompt":"如何把本地数据库迁移到云端？"}' | scripts/fomor hook
scripts/fomor status
scripts/fomor prepare                    # 分析材料的唯一入口（含清理）
```

分析不需要跑分析命令：让 Agent 读 `skills/SKILL.md` 的「每日分析 SOP」执行即可。

## 目录结构

```text
scripts/
└── fomor               唯一脚本（~14KB）：hook / session-start / prepare / learn / finish / status
hooks/
└── hooks.json          UserPromptSubmit 采集 + SessionStart 环境校验
skills/
└── SKILL.md            唯一流程文档：部署 SOP + 分析 SOP（评估→洞察→挖掘）
docs/                   维护者文档，不参与运行时
tests/                  标准库 unittest
.trae-plugin/plugin.json
```

复杂度控制：

- Agent 从不手写 JSON：收集、清理、状态提交、认知记录全部走代码命令
- Agent 只写 Markdown 报告；机械步骤（清理过期 events、丢弃过期 pending）在 prepare 里顺带完成
- 数据只有 4 类：events / profile.json / reports / runtime（state.json）

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
