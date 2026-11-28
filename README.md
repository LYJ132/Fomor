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

**每日探索**：Trae 自动化任务启动 Agent，按 SOP 执行四步：Step 0 采集（prepare 读取事件 + 按线索读 Trae memory 会话摘要）→ Step 1 分析（项目归组、Agent 已提供内容、Pack 假设匹配）→ Step 2 专项探索（按匹配 Pack 的规则挖掘知识缺口）→ Step 3 输出（发现 + 锚点目录 + 专项内容 + Pack 匹配情况 + 未覆盖领域建议）→ finish 清理本轮已读事件。失败则保留原始事件，下次重跑。

**Pack**：领域专属的探索方法文件（`skills/fomor/packs/*.md`），定义观察方向、判断规则、探索方法与筛选标准；放入 Markdown 文件即完成安装，无需改配置。没有匹配 Pack 时降级为通用分析，并在报告中建议可建立的 Pack。

**主动调用**：随时让 Agent「看看 Fomor 的探索」「手动分析一次」「这类内容以后别推了」（只有这条路径能写入 Disliked）。

## 当前架构

Agent Hook 负责采集，Python CLI 负责确定性操作，Agent Skill 负责分析与探索，Trae Automation 负责每日调度。

```text
UserPromptSubmit Hook ──► events/YYYY-MM-DD.jsonl（追加，无处理标记）
SessionStart Hook    ──► 静默初始化/校验 ~/.fomor/
每天 <schedule> 自动化任务 ──► Agent 按 skills/fomor/SKILL.md：
        prepare（读事件+dislikes+快照，不删除）
        → 采集 → 分析 → Pack 专项探索 → 输出
        → finish（只删本轮已读，新增消息保留）
```

## 数据收集与隐私

- 只采集用户主动发送的消息 + 最少元数据（session_id / timestamp / fingerprint），不采集 Agent 回复和完整会话；
- 数据全部在本地 `~/.fomor/`（权限 0700），不上传任何服务；
- 不向会话注入内容，Hook 永不阻塞提问；
- 事件文件没有任何处理标记；只有分析成功后，本轮读取的部分才会被删除，期间新增的消息自动保留。

## 每日分析流程

1. `prepare`：读取所有未清理的事件 + Disliked + 读取边界快照；
2. **采集上下文**：通读提问，找出表达模糊、反复描述、概念不熟、决策原因不明等线索；有线索时按 SKILL 写定的方法读取 Trae memory（按 session_id 的消息级摘要，失败则降级，标注「基于有限信息」）；
3. **分析**：按项目归组、整理 Agent 已提供的内容（判重基线）、逐个 Pack 假设匹配（假设适用 → 核对 → 否定或确认）；
4. **专项探索**：按匹配 Pack 定义的规则挖掘知识缺口；没有匹配 Pack 时做通用分析并记录未覆盖领域；
5. **产出**：开头发现 + 锚点目录 + 专项探索内容 + Pack 安装与匹配情况 + 未覆盖领域与 Pack 建议；
6. `finish`：按快照清理本轮已读事件。

## 探索结果如何呈现

**开头**直接呈现本次最值得关注的发现；**锚点目录**可点击跳转；**专项探索内容**按匹配 Pack 的规则组织，每个发现说明「发现了什么、为什么值得关注、从哪些提问发现、可以进一步了解什么」；**Pack 安装与匹配情况**每次必写（装了什么、匹配了什么、为什么不适用）；**未覆盖领域与 Pack 建议**告知可以为什么领域建 Pack、怎么装（放入 `skills/fomor/packs/` 即可）。

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
└── fomor/
    ├── SKILL.md        唯一流程文档：部署与管理 / 每日探索 SOP / 主动调用
    └── packs/          领域 Pack（*.md，放入即安装，定义探索方法与筛选标准）
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
