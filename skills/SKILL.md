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
1. 阅读 fomor 技能中的「每日探索 SOP」，按 Step 0 到 Step 6 完整执行；
2. 若结论是没有值得探索的方向，明确说明并只执行 Step 6 提交，不生成低质量内容；
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

执行顺序：Step 0（取数据）→ Step 1 观察 → Step 2 假设 → Step 3 发现新可能性 → Step 4 研究与评估 → Step 5 输出 → Step 6 提交。

四个分析阶段是自然的推导关系，不是逐条填写的问卷：每个阶段只选适用的核心问题来思考，综合得出结论后再进入下一阶段；如果后面的推理发现前面的理解明显不成立，可以回到前面修正，但不需要额外的证据等级、置信度评分或校验流程。

写任何结论时都要区分「用户明确说过的」和「你推断出来的」：推断要标成推断，不要写成用户已经确认的需求。

### Step 0：Prepare（唯一数据入口）

```bash
scripts/fomor prepare
```

输出 JSON：`events`（所有尚未成功分析的用户消息）、`dislikes`（用户明确拒绝的内容）、`snapshot`（本轮读取边界）。**不要自己删文件、不要改 runtime state、不要读历史报告**——事件文件在 `finish` 之前保持原样。

### Step 1：Observation（观察与发现）

目标：从当天的提问里建立对用户活动的整体理解，找出值得继续关注的现象。**本阶段只描述看到了什么，不解释原因，也不提前提方案。**

1. 他今天主要在推进什么任务？把提问按「同一件事」归组，而不是一条条孤立地看。
2. 哪些现象值得注意——重复提问、反复强调、反复修正、任务卡住、绕远路的操作、临时改主意？
3. 这些现象之间有时间或目标上的联系吗？比如几条看似不同的问题，其实指向同一个还没说出口的目标。
4. 哪些是他明确说出来的，哪些是你从他前后文推断出来的？

看到什么就写什么，不要在这一步判断好坏，也不要急着解释。

### Step 2：Hypothesis（推导假设）

目标：针对观察到的现象，推导可能的原因，理解他真正想解决的事情。

1. 他提这些问题、做这些事，背后真正想达成的是什么？说不准时给出 1–2 个竞争性的解释，不要硬套一个宏大目标。
2. 这些现象可能由什么造成？可以从需求表达、指令组织、Agent 理解、执行能力、协作方式几个方向去想，哪个最贴合就落在哪个。
3. 他当前的知识、方法、工具或工作流，是否可能限制了问题的解决？具体卡在哪个环节？
4. 遇到重复强调或反复修正时：他最初要的是什么，Agent 给出了什么，之后又怎么改的？这个来回说明了什么？

关于重复强调和反复修正：不要直接当成「用户偏好」或「要求高」。先对照他最初的要求、Agent 的回应和后续修正，看是不是表达、理解或协作上出现了偏差——这往往是重要线索。

六个缺口维度（知识 / 方法 / 工具 / 工作流 / 方案 / 视野）只是你判断「他可能缺什么」时的提醒，不必每次逐项检查，也不要变成固定分类写进输出。

### Step 3：Opportunity Discovery（发现新可能性）

目标：从假设和真实目标出发，找出可能改变他解决问题方式的新思路。

1. 他现在的做法具体卡在哪？是某个环节不够好，还是整条路线本身有局限？
2. 有没有他还没进入考虑范围的知识、方法、工具、工作流，或者整体换一种做法？同类问题在其他领域、行业或场景里通常怎么解？
3. 哪个方向最有机会真正改善他的结果，而不只是让现有做法更顺手？
4. 哪些方向其实普通 AI 对话就能给出答案，不值得占用这次探索？

筛选时直接跳过 `dislikes` 里明确拒绝的内容。不要为了显得有新意而硬找差异，也不要停在「换个工具」这一层——目标是能改变解决问题方式的方案。通过筛选的方向通常一两个就够；如果一个都没有，就明确说没有，不凑数。

### Step 4：Research & Evaluation（研究与评估）

目标：只研究通过筛选的方向，判断它是否真实可行、是否值得推荐给他。

1. 这个方向解决的是他的核心需求，还是只处理了表面问题？
2. 有没有真实可用的方案、实践案例或技术实现，能证明它成立？
3. 和他现在的做法比，改善在哪里，成本、限制和风险是什么？
4. 它是否足够新、足够重要，值得他投入注意力？

研究要围绕前面提出的具体假设和方向展开，不要退化成泛泛的资料搜集或工具罗列。通过评估后，把研究结果整理成可理解的解决路径（核心思路、关键组成、与现方案的区别、适用条件与代价），供 Step 5 输出。查不到可靠依据就如实说明，不硬凑。

### Step 5：Output（探索目录 + 详情）

**第一层：探索目录**（直接展示在对话里）

```markdown
# Fomor 探索目录 · YYYY-MM-DD

近期观察到你在 [一句话概括用户目标/活动]。

以下方向值得探索：

## <方向标题>
<一句说明：为什么值得了解>

（数量由质量决定，没有就写「本轮没有值得探索的新方向」）
```

**第二层：探索详情**：为每个方向写入 `~/.fomor/reports/<YYYY-MM-DD>-<slug>.md`。内容随方向调整，不必套同一模板，但必须保留：

- 与用户问题的关联，以及你判断的依据（引用关键原话，并标明哪些是你的推断）；
- 发现这个方向的理由；
- 新方案的具体内容；
- 真实证据和来源；
- 适用条件及限制。

没有通过 Step 4 的方向时，不生成目录和详情文件，在对话里说明「本轮没有值得探索的新方向」即可。

### Step 6：Finish（成功后提交）

**只有完整分析成功完成后**才执行。把 Step 0 的 `snapshot` 原样传回：

```bash
printf '%s' '{"snapshot":{...Step 0 的 snapshot 原文...}}' | scripts/fomor finish
```

`finish` 会只删除本轮已读取的事件（分析期间新增的消息会保留到下一轮）。失败时（`finish` 报错）不要重试删除，如实报告即可——事件会留在磁盘上，下次重新分析。

每日自动化任务在 Step 0→6 全程：**不更新 Disliked、不读取 pending、不做反馈回看、不要求用户确认是否感兴趣**。

---

## C. 用户主动调用（唯一允许更新 Disliked 的入口）

用户主动调用 Fomor Skill 时可以：

- **手动执行一次探索**：按 B 部分 Step 0→6 执行；
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
