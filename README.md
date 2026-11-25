# Fomor

一个持续理解用户工作与学习过程、主动发现其他解决方案的 AI 探索助手，首个适配平台为 Trae。

## 当前架构

- 采集：Trae `UserPromptSubmit` Hook，事件写入本地
- 调度与分析：Trae 自动化任务，每天 03:00 触发
- 长期记忆：`~/.fomor/` 下的文件结构
- 交付：自动化任务对话流（不做独立网页）
- 反馈：次日 03:00 回看用户提问，有兴趣的移入长期记忆，其余到期删除

## 文档

- [产品需求文档（PRD）](docs/PRD.md) — 产品定位、核心机制、功能设计、MVP 范围
- [待确认问题清单](docs/OPEN-QUESTIONS.md) — 按优先级整理的所有未决事项、验证实验与决策顺序
- [Trae 平台能力调研](docs/TRAE-PLATFORM-RESEARCH.md) — Hooks、Skills、插件、MCP、CLI 能力与落地建议
