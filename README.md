# Fomor

一个长期在后台运行的探索系统：观察你在 Agent 中提出的问题，理解你正在做什么、真正想实现什么，然后主动寻找你可能还没意识到的解决路径。

## Fomor 是什么

你每天向 AI 提出大量问题。这些问题通常只解决眼前的局部，但它们连起来指向更大的目标；而你的提问方式，也会暴露你的认知和方案缺口。Fomor 把这些信号收集起来，每天由 Agent 做一次深度探索，产出**值得你看一眼的新方向**——不是新闻聚合，不是工具清单，不是普通搜索，而是「面对你现在的问题，还有没有另一种值得尝试的解决方式」。

## 它解决什么问题

- AI 只会沿你当前的技术栈和思路找答案，茧房就是这么形成的；
- 单次对话只解决局部，没人帮你把一天的问题连起来理解；
- 常规答案你自己就能问到，Fomor 只交付「你没想到的方向」，没有高价值方向时明确说明。

## 用户旅程

**安装**：安装插件 → Agent 读 Fomor Skill → 检查环境、初始化 `~/.fomor/` → 配置 UserPromptSubmit Hook → 创建每日自动化任务 → 自检。

**日常使用**：你正常使用 Trae。每次发消息 Hook 静默落盘，不注入、不分析、不影响对话。

**每日探索**：Trae 自动化任务启动 Agent，按 SOP 执行：prepare 读取事件 → 理解问题序列 → 识别缺口 → 形成探索假设 → 搜索前评估 → 搜索验证 → 方案综合 → 产出探索目录 + 详情 → finish 清理本轮已读事件。失败则保留原始事件，下次重跑。

**主动调用**：随时让 Agent「看看 Fomor 的探索」「手动分析一次」「这类内容以后别推了」（只有这条路径能写入 Disliked）。

## 当前架构

Agent Hook 负责采集，Python CLI 负责确定性操作，Agent Skill 负责分析与探索，Trae Automation 负责每日调度。

```text
UserPromptSubmit Hook ──► events/YYYY-MM-DD.jsonl（追加，无处理标记）
SessionStart Hook    ──► 静默初始化/校验 ~/.fomor/
每天 <schedule> 自动化任务 ──► Agent 按 skills/SKILL.md：
        prepare（读事件+dislikes+快照，不删除）
        → 观察 → 假设 → 发现新可能性 → 研究与评估
        → 探索目录 + 详情 → finish（只删本轮已读，新增消息保留）
```

## 数据收集与隐私

- 只采集用户主动发送的消息 + 最少元数据（session_id / timestamp / fingerprint），不采集 Agent 回复和完整会话；
- 数据全部在本地 `~/.fomor/`（权限 0700），不上传任何服务；
- 不向会话注入内容，Hook 永不阻塞提问；
- 事件文件没有任何处理标记；只有分析成功后，本轮读取的部分才会被删除，期间新增的消息自动保留。

## 每日分析流程

1. `prepare`：读取所有未清理的事件 + Disliked + 读取边界快照；
2. **观察**：今天在推进什么任务、有哪些值得注意的现象（重复提问、反复修正、任务卡住等），以及现象之间的联系；
3. **假设**：这些现象背后的真实目标与可能原因；重复强调、反复修正先当作交互线索，而不是用户偏好；
4. **发现新可能性**：当前做法的局限在哪，有没有他没考虑过的知识、方法、工具、工作流或整体思路；
5. **研究与评估**：只研究通过筛选的方向——是否解决核心需求、有无真实案例、改善与代价、是否值得投入注意力；
6. **产出**：探索目录（第一层）+ 每方向详情（第二层）；
7. `finish`：按快照清理本轮已读事件。

## 探索结果如何呈现

**探索目录**（第一层）：近期观察的一句话理解 + 值得探索的方向列表（标题 + 一句为什么）。**探索详情**（第二层）：为什么发现、与你的关联、新方案内容、真实证据与来源、适用条件与限制。数量由质量决定，没有高价值方向就明说，不凑数。

## 安装与使用

```bash
scripts/fomor session-start --verbose   # 创建/校验 ~/.fomor
printf '%s' '{"session_id":"demo","prompt":"如何把本地数据库迁移到云端？"}' | scripts/fomor hook
scripts/fomor status
```

对 Agent 说「安装/检查 Fomor」即可完成全部部署（含代创建自动化任务）。hooks.json 在 [hooks/hooks.json](hooks/hooks.json)，由 [.trae-plugin/plugin.json](.trae-plugin/plugin.json) 引用。

## 项目结构

```text
scripts/
└── fomor               唯一脚本：hook / session-start / prepare / dislike / finish / status
hooks/
└── hooks.json          UserPromptSubmit 采集 + SessionStart 环境校验
skills/
└── SKILL.md            唯一流程文档：部署与管理 / 每日探索 SOP / 主动调用
docs/                   PRD、待确认问题、平台调研
tests/                  标准库 unittest
.trae-plugin/plugin.json
```

## 开发和测试

```bash
python3 -m py_compile scripts/fomor
tests/run.sh
```

## 文档

- [产品需求文档（PRD）](docs/PRD.md) — 当前产品决策与历史设计转折
- [待确认问题清单](docs/OPEN-QUESTIONS.md) — 未决事项与验证实验
- [Trae 平台能力调研](docs/TRAE-PLATFORM-RESEARCH.md) — Hooks、Skills、Automation 能力与落地建议
