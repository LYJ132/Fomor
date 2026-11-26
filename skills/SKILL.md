---
name: fomor
description: Use when setting up Fomor (hooks, data dir, automation task), when the daily automation executes the exploration SOP, or when the user wants to review results or explicitly refuse content. Contains the full methodology: understand, find gaps, hypothesize, evaluate before searching, research, and deliver an exploration directory.
user-invocable: true
disable-model-invocation: false
---

# Fomor

Fomor 采集用户在 Trae 中提出的问题，每天由自动化任务中的 **Agent（你）** 按本文档执行一次深度探索，产出「探索目录 + 探索详情」。所有机械步骤（收集、清理、状态提交）都由 `scripts/fomor` 完成，你只负责理解、思考、搜索与写作。

职责划分：

| 组件 | 触发时机 | 做什么 |
| --- | --- | --- |
| `UserPromptSubmit` Hook（`scripts/fomor hook`） | 用户发消息 | 静默把问题追加到 `~/.fomor/events/`，不阻塞、不注入、不分析 |
| `SessionStart` Hook（`scripts/fomor session-start`） | 会话开始 | 静默创建/校验 `~/.fomor/`，不输出 |
| `scripts/fomor prepare / finish` | 每日探索前后 | 代码完成：读取事件与快照；成功后清理本轮已读事件 |
| `scripts/fomor dislike` | **仅用户主动调用 Skill 时** | 记录用户明确拒绝的内容 |
| **自动化任务** | 每天定时 | 你按本文档「每日探索 SOP」执行 |
| 本技能 | 用户调用 / 自动化任务 | 部署与管理（A）；每日探索 SOP（B）；主动调用（C） |

三条硬性边界，任何时候都不违反：

1. **事件无处理标记**：不添加 processed/analyzed 字段；事件文件只在分析成功后由 `finish` 按快照清理。
2. **分析失败不清理**：中断、搜索失败、结果生成失败都不调用 `finish`，原始事件完整保留，下次重新分析。
3. **Disliked 只进不出、只在主动调用时更新**：每日自动化任务只读不写；用户沉默、没追问、没点击都不是拒绝，不得推断。

---

## A. 部署与管理（用户说「安装/检查 Fomor」时）

### A1. 环境检查

```bash
scripts/fomor session-start --verbose
```

`ok: true` 即就绪；`missing` 含 `python` 则先请用户安装 Python 3.10+ 并终止。

### A2. Hook 核对

读取全局 `~/.trae-cn/hooks.json`（国际版 `~/.trae/hooks.json`）或项目 `.trae/hooks.json`，确认两条命令（`<插件根目录>` 用实际绝对路径替换）：

```text
UserPromptSubmit → <插件根目录>/scripts/fomor hook
SessionStart     → <插件根目录>/scripts/fomor session-start
```

缺失时把仓库 `hooks/hooks.json` 内容合并进去并替换 `${TRAE_PLUGIN_ROOT}`，提醒用户在「设置 > Hooks」启用（安全确认弹窗由用户手动点击）。即使 SessionStart 缺失，首次 hook 也会自动创建数据目录，不会丢消息。

### A3. 由你创建自动化任务

不要让用户手动新建。使用 Trae 的对话创建能力，按以下模板创建（`<时间>` 取 `scripts/fomor status` 输出的 `schedule` 值）：

```text
任务名称：Fomor 每日探索
触发：每天 <时间>
任务内容：
使用 fomor 技能执行今日探索：
1. 阅读 fomor 技能中的「每日探索 SOP」，按 Step 0 到 Step 9 完整执行；
2. 若结论是没有值得探索的方向，明确说明并只执行 Step 9 提交，不生成低质量内容；
3. 否则把探索目录完整展示给我，并告诉我详情保存在哪里；
4. 遇到报错或数据不足时如实说明，不要编造。
```

创建后告知用户：任务创建后运行环境不可修改；本地任务睡眠期不执行，错过的探索会在下次运行时补上（未分析的事件会一直保留）。

### A4. 自检

```bash
printf '%s' '{"session_id":"setup-check","prompt":"Fomor 安装自检","hook_event_name":"UserPromptSubmit"}' | scripts/fomor hook
scripts/fomor status
```

`events` 增加 1、重复执行不再增加即采集正常。从 `~/.fomor/events/<当天>.jsonl` 删除 `session_id` 为 `setup-check` 的自检记录。最后确认：自动化任务已创建、Hook 已启用。

---

## B. 每日探索 SOP（自动化任务 / 用户主动要求分析时执行）

按 Step 0→9 顺序执行，不要跳步。所有判断都要有用户原话作证据；宁可保留不确定，也不编造洞察。

### Step 0：Prepare（唯一数据入口）

```bash
scripts/fomor prepare
```

输出 JSON：`events`（所有尚未成功分析的用户消息）、`dislikes`（用户明确拒绝的内容）、`snapshot`（本轮读取边界）。**不要自己删文件、不要改 runtime state、不要读历史报告**——事件文件在 `finish` 之前保持原样。

### Step 1：Problem Understanding（理解用户在做什么）

分析单位是**一组相关问题**，不是单条消息；不要为了分类而分类。回答：

1. 用户正在完成什么任务？
2. 他真正想实现的目标是什么？
3. 当前使用什么方法、工具或工作流？
4. 当前遇到什么问题？
5. 这些问题之间是否存在因果关系？
6. 用户有哪些明确提出的约束？
7. 哪些地方仍然存在不确定性？

不确定的地方如实标注，不要强行补全。

### Step 2：Gap Discovery（识别缺口）

用以下六个**内部分析维度**思考（可以同时成立；它们不是对外的栏目，不出现在最终输出里）：

1. **Knowledge Gap**：不了解某领域的存在或原理；
2. **Method Gap**：知道目标但不知道方法；
3. **Tool Gap**：方法已知但缺少合适工具；
4. **Workflow Gap**：流程本身有问题（单点都对、串起来不合理）；
5. **Solution Gap**：当前方案路线本身有局限，需要换路线；
6. **Perspective Gap**：问题框架本身可以重构（他在优化 A，其实该考虑 B）。

典型信号：同一事物被反复用不同措辞描述（词汇/参考资源缺口）；连续多天追问同一环节（他在搭系统，缺的是整体方法而非单点答案）。对每个洞察区分：**用户原话/实际行为 → 基于证据的观察 → 推测的缺口 → 置信度**。不要把推测当成事实。

### Step 3：Exploration Hypothesis（形成探索假设）

把洞察转换为具体假设，每个回答：

- 用户当前的问题是什么？
- 当前方案可能有什么局限？
- 如果采用不同方案，可能带来什么改善？
- 为什么用户可能不知道这种解决路径？
- 需要搜索和验证什么？

目标是形成**新的解决方案**，不是找一个关键词对应的工具。

### Step 4：Pre-search Evaluation（搜索前评估与过滤）

在搜索之前评估每个假设：与用户目标的相关性、潜在改善价值、新颖程度、可行性、行为证据强度。过滤掉：

- 与用户当前目标关联弱的；
- 命中 `dislikes` 的；
- 重复的探索方向；
- 过于常规、AI 正常对话就会给的答案；
- 缺乏实际改善价值的。

没有通过评估的假设就明确说明「没有值得探索的方向」——**不为凑数而生成假设**。若全部被过滤，直接跳到 Step 9（提交空确认）。

### Step 5：Research & Validation（搜索与验证）

只针对通过评估的假设搜索。重点：新方法、新技术、新工具、工具组合、工作流、开源项目、社区实践、实际案例、跨领域方案。**不要搜索用户普通 AI 对话就能获得的官方文档和基础教程。**

对每个候选方案验证：是否真实存在？有实际使用案例吗？解决什么问题？与当前方案相比改善在哪？适用条件？成本、风险、迁移限制？符合用户约束吗？搜不到可靠内容就如实说明，不硬凑。

### Step 6：Solution Synthesis（方案综合）

把验证过的结果转化为**可理解的解决路径**——工具、技术栈、方法、工作流都是方案的组成部分，不要按类型拆栏目。每个方案说明：核心思路、关键组成、如何解决用户的问题、与当前方案的区别、适用场景、成本和限制。

### Step 7：Exploration Directory（第一层：探索目录）

```markdown
# Fomor 探索目录 · YYYY-MM-DD

近期观察到你在 [一句话概括用户目标/活动]。

以下方向值得探索：

## <方向标题>
<一句说明：为什么值得了解>

（数量由质量决定，没有就写「本轮没有值得探索的新方向」）
```

### Step 8：Exploration Detail（第二层：探索详情）

为每个目录方向生成详情，写入 `~/.fomor/reports/<YYYY-MM-DD>-<slug>.md`。内容随方向调整，不必套同一模板，但必须保留：

- 与用户问题的关联；
- 发现这个方向的理由（含证据原话与置信度）；
- 新方案的具体内容；
- 真实证据和来源；
- 适用条件及限制。

### Step 9：Finish（成功后提交）

**只有完整分析成功完成后**才执行。把 Step 0 的 `snapshot` 原样传回：

```bash
printf '%s' '{"snapshot":{...Step 0 的 snapshot 原文...}}' | scripts/fomor finish
```

`finish` 会只删除本轮已读取的事件（分析期间新增的消息会保留到下一轮）。失败时（`finish` 报错）不要重试删除，如实报告即可——事件会留在磁盘上，下次重新分析。

每日自动化任务在 Step 0→9 中：**不更新 Disliked、不读取 pending、不做反馈回看、不要求用户确认是否感兴趣**。

---

## C. 用户主动调用（唯一允许更新 Disliked 的入口）

用户主动调用 Fomor Skill 时可以：

- **手动执行一次探索**：按 B 部分 Step 0→9 执行；
- **查看/讨论结果**：读 `~/.fomor/reports/` 下的目录与详情，展开讨论；
- **更新 Disliked**：仅当用户**明确表达拒绝**时执行：

```bash
scripts/fomor dislike --name "<内容名称>" [--category content_preference]
```

Disliked 更新规则：

1. 只记录用户明确说「不想再看到这类内容」的条目；
2. 用户只是调用了 Skill 但没表达拒绝 → **不更新**；
3. 用户沉默、没点击、没追问、没用某个方案 → **不推断为拒绝**；
4. 重复条目自动去重，不需要反馈状态或时间线。

---

## 数据与配置速查

```text
~/.fomor/
├── config.json               {"timezone": "Asia/Shanghai", "schedule": "03:00"}
├── events/YYYY-MM-DD.jsonl   用户问题，无处理标记；finish 按快照清理已分析的
├── profile.json              {"version": 1, "dislikes": [...]} 只记明确拒绝
├── reports/                  探索目录与详情（留存，可随时删除，不参与每日分析）
└── runtime/state.json        {"last_successful_analysis_at"}
```

Event 只有 5 个字段：`event_id`、`session_id`、`timestamp`、`user_message`、`fingerprint`。

常用命令：`scripts/fomor status`（概览）、`cat ~/.fomor/reports/*.md`（查看结果）。
