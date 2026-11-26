---
name: fomor
description: Use when setting up Fomor (hooks, data dir, automation task) or when the daily automation executes the analysis SOP. Contains the full methodology: feedback review, evaluate-first, insight into what the user is missing, then dig.
user-invocable: true
disable-model-invocation: false
---

# Fomor

Fomor 采集用户在 Trae 中提出的问题，每天由自动化任务中的 **Agent（你）** 按本文档执行分析，报告写入 `~/.fomor/reports/`。分析不依赖任何脚本或模型配置——你的智能就是分析引擎。

职责划分：

| 组件 | 触发时机 | 做什么 |
| --- | --- | --- |
| `UserPromptSubmit` Hook（`scripts/fomor hook`） | 用户发消息 | 静默把问题追加到 `~/.fomor/events/`，不阻塞、不注入 |
| `SessionStart` Hook（`scripts/fomor session-start`） | 会话开始 | 静默创建/校验 `~/.fomor/`，不输出 |
| **自动化任务** | 每天定时 | 你按本文档「每日分析 SOP」执行分析与反馈回看 |
| 本技能 | 用户调用 / 自动化任务 | 部署检查（A 部分）；分析执行（B 部分） |

用户调用本技能做部署时执行 A 部分；自动化任务触发时直接执行 B 部分。

---

## A. 部署（用户说「安装/检查 Fomor」时）

### A1. 环境检查

```bash
scripts/fomor session-start --verbose
```

`ok: true` 即就绪（目录与默认配置已静默补齐）；`missing` 含 `python` 则先请用户安装 Python 3.10+ 并终止。

### A2. Hook 核对

读取全局 `~/.trae-cn/hooks.json`（国际版 `~/.trae/hooks.json`）或项目 `.trae/hooks.json`，确认两条命令（`<插件根目录>` 用实际绝对路径替换）：

```text
UserPromptSubmit → <插件根目录>/scripts/fomor hook
SessionStart     → <插件根目录>/scripts/fomor session-start
```

缺失时把仓库 `hooks/hooks.json` 内容合并进去并替换 `${TRAE_PLUGIN_ROOT}`，提醒用户在「设置 > Hooks」启用（涉及安全确认弹窗由用户手动点击）。

### A3. 由你创建自动化任务

不要让用户手动新建。使用 Trae 的对话创建能力，按以下模板创建（`<时间>` 取 `scripts/fomor status` 输出的 `schedule` 值）：

```text
任务名称：Fomor 每日探索
触发：每天 <时间>
任务内容：
使用 fomor 技能执行今日分析：
1. 阅读 fomor 技能中的「每日分析 SOP」，逐步执行：反馈回看 → 评估 → 洞察 → 挖掘 → 产出；
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

### 第 0 步：收集材料与清理

1. 读 `~/.fomor/runtime/state.json` 的 `last_analyzed_at`（没有则视为首次，读全部 events）；
2. 读取 `~/.fomor/events/*.jsonl` 中 `timestamp` 晚于 `last_analyzed_at` 的事件，按时间排序；
3. 读 `~/.fomor/discoveries/` 中所有 `status: observing` 的探索结果；
4. 顺手清理：删除 8 天前的 `events/YYYY-MM-DD.jsonl` 文件（按文件名日期判断）。

### 第 1 步：反馈回看（先于新分析）

对照每个 observing 状态的探索结果与这批新提问：

- **有兴趣**：新提问与该探索的主题相关——追问细节、要求尝试、围绕同一目标展开 → 把该文件 `status` 改为 `promoted`，并在对应 topic 的 `interests` 追加一条（含证据 event_id）；
- **明确拒绝**：用户表示已了解/不感兴趣 → `status` 改为 `expired` 并删除文件；
- **无相关提问**：保持 observing。若 `created_at` 距今超过 7 天仍无兴趣 → 视为过期，`status` 改 `expired` 并删除文件。

### 第 2 步：评估（先评估，再挖掘）

对窗口内的提问做主题归并，然后对每个候选主题回答三个问题：

1. 这些提问**最终指向什么目标**？用户正在完成什么任务？
2. 这个主题是否**反复出现**（跨天追问、同天多次）？
3. 用户当前的解决方式有没有**明显局限或未言明的缺口**？

三问之后做出决定：值得挖掘 / 暂时观察 / 不值得。**没有值得挖掘的主题就到此为止**：回复用户「今天没有值得探索的新方向」，更新 `last_analyzed_at`，不生成报告，不硬凑内容。

### 第 3 步：洞察（对决定挖掘的主题）

这是分析的核心。对每个主题完成下面的推理链，写进洞察结论：

**3.1 用户到底缺什么？** 逐项判断，并引用原话作证据：

- 缺**知识**：不了解某个领域的存在或原理；
- 缺**词汇/风格体系**：反复描述同一事物却用词各异——典型信号：同一天用多种不同说法描述同一个东西（例：用户反复用不同措辞描述「前端动效/过渡效果」却从不使用行业术语）→ 推断他不熟悉该领域的名词与风格体系 → 他正在做这类工作 → 他需要系统地知道这些风格与名称 → 挖掘方向就是提供风格清单、术语对照、可参考的案例；
- 缺**方法论/工作流**：问题反复出现在流程的同一环节（例：连续几天都在问数据库怎么迁、怎么连、服务放哪）→ 追问：他为什么一直问数据库？他想达成什么目的（稳定？省成本？可维护？）？他有没有提到过约束（数据量、实时性、团队规模）？他是否需要一个整体的工作流或架构方法，而不是单点答案；
- 缺**判断依据**：知道选项但不会比较取舍。

**3.2 区分目标与阻碍**：他想实现什么（Underlying Goal）≠ 当前什么在阻碍他（Root Problem）。证据不足时列出多个假设并标注置信度，不要强行给一个漂亮结论。

**3.3 用户自己给过线索吗**：他有没有提过「想用 XX」「听说 YY」「试过 ZZ 但不行」？这些是挖掘的锚点。

### 第 4 步：挖掘（使用你的搜索/网页工具）

针对第 3 步识别的缺口去找：方法、工作流、工具、参考资料、案例。要求：

- 每个方案说明：解决什么、核心思路、与他当前做法的差异、适用条件/代价；
- 优先给「不同的解决路径」，而不是同类工具的罗列；
- 附来源链接；搜不到可靠内容就如实说明，不硬凑；
- 每个主题 2–3 个方案即可，宁缺毋滥。

### 第 5 步：产出

1. **报告** `~/.fomor/reports/YYYY-MM-DD.md` 并同步写 `latest.md`，结构：
   - 反馈回看摘要（哪些探索被你追问了、哪些过期了）；
   - 今日主题：洞察结论（目标 / 缺口 / 证据原话）；
   - 方案与参考（含来源）；
   - 留给用户的问题（帮助下一轮归因，例如「你更关心成本还是稳定？」）；
2. **Topic** `~/.fomor/topics/<slug>.json`：新主题则创建 `{name, goal, evidence: [event_id], interests: [], created_at, updated_at}`；已有主题则追加 evidence 与 updated_at；
3. **Discovery** `~/.fomor/discoveries/<slug>.json`：`{id, topic, title, goal, insight, solutions, questions, created_at, status: "observing"}`；
4. **状态**：更新 `~/.fomor/runtime/state.json` 的 `last_analyzed_at` 为本次执行时刻（ISO 格式）。

---

## 数据与配置速查

```text
~/.fomor/
├── config.json               {"timezone": "Asia/Shanghai", "schedule": "03:00"}
├── events/YYYY-MM-DD.jsonl   用户问题，按天归档；8 天前的文件由你在第 0 步删除
├── topics/<slug>.json        长期话题（兴趣沉淀于此）
├── discoveries/<slug>.json   observing（观察中）/ promoted（有兴趣）/ expired
├── reports/latest.md         最近一次报告
└── runtime/state.json        {"last_analyzed_at": "..."}，时间窗的依据
```

Event 只有 5 个字段：`event_id`（关联主键）、`session_id`（会话定位）、`timestamp`（窗口与归因边界）、`user_message`（唯一内容）、`fingerprint`（防多 Hook 重复采集）。

常用命令：`scripts/fomor status`（概览）、`cat ~/.fomor/reports/latest.md`（日常看报告）。
