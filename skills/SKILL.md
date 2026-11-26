---
name: fomor
description: Use when setting up Fomor (hooks, data dir, automation task) or when the daily automation executes the analysis SOP. Contains the full methodology: feedback review, evaluate-first, insight into what the user is missing, then dig.
user-invocable: true
disable-model-invocation: false
---

# Fomor

Fomor 采集用户在 Trae 中提出的问题，每天由自动化任务中的 **Agent（你）** 按本文档执行分析，报告写入 `~/.fomor/reports/`。所有机械步骤（收集、清理、状态记录）都由 `scripts/fomor` 完成，你只负责思考与写报告。

职责划分：

| 组件 | 触发时机 | 做什么 |
| --- | --- | --- |
| `UserPromptSubmit` Hook（`scripts/fomor hook`） | 用户发消息 | 静默把问题追加到 `~/.fomor/events/`，不阻塞、不注入 |
| `SessionStart` Hook（`scripts/fomor session-start`） | 会话开始 | 静默创建/校验 `~/.fomor/`，不输出 |
| `scripts/fomor prepare / learn / finish` | 分析前后 | 代码完成：收集窗口与档案、清理过期数据、记录认知、提交本轮 |
| **自动化任务** | 每天定时 | 你按本文档「每日分析 SOP」执行分析 |
| 本技能 | 用户调用 / 自动化任务 | 部署检查（A 部分）；分析执行（B 部分） |

核心记忆观：

- **不存话题**。用户真感兴趣的话题每天都会再问出来，不需要额外记录；
- **长期记忆 = 他已经知道什么**（`profile.json` 的 `known` / `dislikes`），作用只有一个：避免向他推已知道的内容，并据此判断他的认知水位；
- **短期判断极短**：上一轮的探索结论（`pending`）只活到本次分析，对照完新提问就处置掉。

---

## A. 部署（用户说「安装/检查 Fomor」时）

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

缺失时把仓库 `hooks/hooks.json` 内容合并进去并替换 `${TRAE_PLUGIN_ROOT}`，提醒用户在「设置 > Hooks」启用（安全确认弹窗由用户手动点击）。

### A3. 由你创建自动化任务

不要让用户手动新建。使用 Trae 的对话创建能力，按以下模板创建（`<时间>` 取 `scripts/fomor status` 输出的 `schedule` 值）：

```text
任务名称：Fomor 每日探索
触发：每天 <时间>
任务内容：
使用 fomor 技能执行今日分析：
1. 阅读 fomor 技能中的「每日分析 SOP」，逐步执行：prepare → 反馈回看 → 评估 → 洞察 → 挖掘 → 产出与 finish；
2. 若结论是今天没有值得探索的方向，只回复这一句，不生成报告；
3. 否则把生成的报告（~/.fomor/reports/latest.md）完整展示给我；
4. 遇到报错或数据不足时如实说明，不要编造。
```

创建后告知用户：任务创建后运行环境不可修改；本地任务睡眠期不执行，错过的分析会在下次运行时自动扩大时间窗补上。

### A4. 验收

```bash
printf '%s' '{"session_id":"setup-check","prompt":"Fomor 安装自检","hook_event_name":"UserPromptSubmit"}' | scripts/fomor hook
scripts/fomor status
```

`events` 增加 1、重复执行不再增加即采集正常。从 `~/.fomor/events/<当天>.jsonl` 删除 `session_id` 为 `setup-check` 的自检记录。最后确认：自动化任务已创建、Hook 已启用。

---

## B. 每日分析 SOP（自动化任务 / 用户说「分析一下」时执行）

按顺序执行 0→5，不要跳步。所有判断都要有用户原话作证据，宁可保留不确定，也不编造洞察。

### 第 0 步：取材料（一行命令，代码已完成清理）

```bash
scripts/fomor prepare
```

输出 JSON 包含：`events`（上次分析以来的全部提问）、`pending`（上一轮的探索结论）、`known` / `dislikes`（他已知什么、明确不要什么）、`event_files_removed`（本轮清理掉的过期文件）。不要自己去翻目录、删文件、改 state.json——这些代码都做完了。

### 第 1 步：反馈回看（处置 pending）

对照 `pending` 与 `events` 里的新提问：

- **有兴趣**（追问细节、要求尝试、围绕同一目标展开）→ 执行 `scripts/fomor learn --known "<结论/方案名>" --note "<一句话依据+event_id>"`。他的提问证明他现在知道了它，进入长期档案；
- **明确拒绝**（表示已了解/不感兴趣）→ `scripts/fomor learn --dislike "<名称>" --note "<原话依据>"`；
- **无相关提问** → 不做任何操作，`finish` 会自动丢弃本轮 pending（短期判断只活一轮）。

### 第 2 步：评估（先评估，再挖掘）

把 `events` 按主题归并，对每个候选主题回答三个问题：

1. 这些提问**最终指向什么目标**？用户正在完成什么任务？
2. 这个主题是否**反复出现**（跨天追问、同天多次）？
3. 用户当前的解决方式有没有**明显局限或未言明的缺口**？

三问之后决定：值得挖掘 / 暂时观察 / 不值得。**没有值得挖掘的主题就到此为止**：回复「今天没有值得探索的新方向」，然后执行第 5 步的 `finish`（提交空 pending），不生成报告，不硬凑内容。

### 第 3 步：洞察（对决定挖掘的主题）

这是分析的核心。对每个主题完成下面的推理链：

**3.1 用户到底缺什么？** 逐项判断，并引用原话作证据：

- 缺**知识**：不了解某个领域的存在或原理；
- 缺**词汇/风格体系**：反复描述同一事物却用词各异——典型信号：同一天用多种不同说法描述同一个东西（例：用户反复用不同措辞描述「前端动效/过渡效果」却从不使用行业术语）→ 推断他不熟悉该领域的名词与风格体系 → 他正在做这类工作 → 他需要系统地知道这些风格与名称 → 挖掘方向就是提供风格清单、术语对照、可参考的案例；
- 缺**方法论/工作流**：问题反复出现在流程的同一环节（例：连续几天都在问数据库怎么迁、怎么连、服务放哪）→ 追问：他为什么一直问数据库？他想达成什么目的（稳定？省成本？可维护？）？他有没有提到过约束（数据量、实时性、团队规模）？他是否需要一个整体的工作流或架构方法，而不是单点答案；
- 缺**判断依据**：知道选项但不会比较取舍。

**3.2 区分目标与阻碍**：他想实现什么 ≠ 当前什么在阻碍他。证据不足时列出多个假设并标注置信度，不要强行给一个漂亮结论。

**3.3 对照认知水位**：`known` 里已有的不要当新发现；`known` 能反映他的知识边界——洞察要落在边界之外一步的位置，而不是远超边界。

**3.4 用户自己给过线索吗**：他有没有提过「想用 XX」「听说 YY」「试过 ZZ 但不行」？这些是挖掘的锚点。

### 第 4 步：挖掘（使用你的搜索/网页工具）

针对第 3 步识别的缺口去找：方法、工作流、工具、参考资料、案例。要求：

- **先对照 `known` 与 `dislikes`**：他已知的跳过，他明确不要的不再推；
- 每个方案说明：解决什么、核心思路、与他当前做法的差异、适用条件/代价；
- 优先给「不同的解决路径」，而不是同类工具的罗列；
- 附来源链接；搜不到可靠内容就如实说明，不硬凑；
- 每个主题 2–3 个方案即可，宁缺毋滥。

### 第 5 步：产出与提交

1. **报告** `~/.fomor/reports/YYYY-MM-DD.md` 并同步写 `latest.md`，结构：
   - 反馈回看摘要（哪些结论被追问了、已进档案）；
   - 今日主题：洞察结论（目标 / 缺口 / 证据原话）；
   - 方案与参考（含来源）；
   - 留给用户的问题（帮助下一轮归因）；
2. **认知档案**：本轮中用户明确表达「我已经知道/在用 XX」的，执行 `learn --known`；
3. **提交**：把本轮探索结论整理为 pending 索引（每条含 `id`、`title`、`topic`、`created_at`），用 stdin 提交给代码：

   ```bash
   printf '%s' '{"pending":[{"id":"db-architecture","title":"...","topic":"...","created_at":"..."}]}' | scripts/fomor finish
   ```

   `finish` 会记录 `last_analyzed_at` 并用新 pending 覆盖旧的。空 pending 也要提交（`{"pending":[]}`）。

---

## 数据与配置速查

```text
~/.fomor/
├── config.json               {"timezone": "Asia/Shanghai", "schedule": "03:00"}
├── events/YYYY-MM-DD.jsonl   用户问题，按天归档；8 天前的文件由 prepare 自动删除
├── profile.json              长期记忆：{"known": [...], "dislikes": [...]}——他知道什么、不要什么
├── reports/latest.md         最近一次报告
└── runtime/state.json        {"last_analyzed_at", "pending"}；pending 只活到下次分析
```

Event 只有 5 个字段：`event_id`、`session_id`、`timestamp`、`user_message`、`fingerprint`。

常用命令：`scripts/fomor status`（概览）、`cat ~/.fomor/reports/latest.md`（日常看报告）。
