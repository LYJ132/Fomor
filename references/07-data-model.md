# 数据模型（`~/.fomor/`）

运行时数据全部在用户主目录，插件目录只放代码。默认根目录 `~/.fomor`，可用 `FOMOR_HOME` 覆盖；权限 `0700`。

## 目录

```text
~/.fomor/
├── config/
│   └── settings.json           # 合并后的配置（首次 init 写入默认值）
├── events/
│   └── YYYY-MM-DD.jsonl        # 每天一个文件，按采集时间归档
├── topics/
│   └── topic_*.json            # 长期话题
├── discoveries/
│   ├── pending/                # 观察期内的探索结果
│   └── promoted/               # 已因后续提问移入长期记忆
├── tombstones/
│   └── discovery_*.json        # 过期指纹，仅用于去重
├── reports/
│   ├── YYYY-MM-DD.md
│   └── latest.md               # 最近一次报告
├── runtime/
│   ├── state.json              # last_success_at / last_run_id / last_event_count
│   ├── runs.json               # 最近 200 次运行记录
│   └── analyze.lock            # 分析互斥锁
├── logs/
│   └── catchup.log             # 补跑日志
└── backup/
    └── fomor-YYYYmmddHHMMSS/   # 最近 7 份 config/topics/discoveries/tombstones
```

## `config/settings.json`

| 键 | 默认值 | 说明 |
| --- | --- | --- |
| `timezone` | `Asia/Shanghai` | 本地日与每日分析截止时间的时区 |
| `schedule.hour` / `schedule.minute` | `3` / `0` | 每日分析截止时间 |
| `retention.event_days` | `8` | Event 保留天数（7 天反馈窗 + 1 天缓冲） |
| `retention.feedback_days` | `7` | Discovery 观察期 |
| `retention.tombstone_days` | `90` | 过期指纹保留天数 |
| `retention.dedupe_days` | `2` | 同一 fingerprint 的去重窗口 |
| `llm.mode` | `mock` | `mock` / `traecli` / `openai` |
| `analysis.max_events_per_run` | `200` | 单次分析事件上限 |
| `analysis.max_topics_per_run` | `3` | 单次分析主题上限 |
| `scoring.explore_threshold` | `3.5` | `explore` 的最低总分 |
| `scoring.watch_threshold` | `2.0` | `watch` 的最低总分 |
| `feedback.strong_similarity` | `0.18` | 强兴趣相似度阈值 |
| `feedback.weak_similarity` | `0.06` | 弱兴趣相似度阈值 |

## Event

`events/YYYY-MM-DD.jsonl`，一行一个 JSON 对象。只保留有读取方的字段——每加一个字段都必须回答「谁在什么时机读它」。

| 字段 | 谁读 | 作用 |
| --- | --- | --- |
| `event_id` | 聚合输出、`discovery.source_event_ids`、反馈的 `evidence_event_ids` | 主键；把原始问题与主题、探索结果、反馈证据关联起来 |
| `session_id` | `fingerprint` 计算；未来按会话补上下文 | 会话定位符；与问题内容一起构成去重键 |
| `timestamp` | `iter_events` 窗口过滤、按天归档、反馈归因边界 | 所有时间窗口（分析窗口、反馈观察窗）的依据 |
| `user_message` | 聚合/理解提示词、报告「观察到的问题」 | 唯一的内容载体 |
| `fingerprint` | `find_event_by_fingerprint`（追加前去重） | `trae + session_id + 规范化问题` 的 SHA-256；Trae 多 Hook 配置会合并执行，去重防污染 |
| `analyzed_at` | `run_analysis` 过滤未分析事件 | 区分「已参与分析/未分析」，避免同一条问题被重复聚合 |

被裁剪的字段及理由：`platform`（当前只有 Trae，硬编码进指纹）、`collection_status`（恒为 `collected`，无其他状态）、`related_topic_id`（与 `discovery.source_event_ids` 重复）、`metadata`（`cwd`/`workspace_roots`/`hook_event_name` 无读取方，还扩大隐私面）。

## Topic

`topics/topic_*.json`。长期记忆的主体，原始 Event 过期后仍保留。

| 字段 | 说明 |
| --- | --- |
| `topic_id` / `name` | 标识与主题名 |
| `background` / `user_goal` | 背景与目标 |
| `progress` | 推进记录数组（`at`、`note`） |
| `introduced_solutions` | 已介绍过的方案名，用于避免重复推荐 |
| `interests` | 反馈提升记录（`discovery_id`、`signal`、`confidence`、`evidence_event_ids`、`at`） |
| `dislikes` | 明确不感兴趣记录（`discovery_id`、`reason`、`at`） |
| `known` / `practices` / `corrections` | 认知状态与实践记录（后续扩展） |
| `evidence` | 支撑该话题的 Event ID |
| `discovery_ids` | 关联的 Discovery |
| `status` | `active` 等 |
| `created_at` / `last_activity_at` | 时间戳 |

## Discovery

`discoveries/pending/*.json` 与 `discoveries/promoted/*.json`。一次探索结果。

| 字段 | 说明 |
| --- | --- |
| `discovery_id` / `topic_id` / `topic_name` | 标识与所属主题 |
| `created_at` | 生成时间，反馈窗口起点 |
| `status` | `observing` / `promoted` / `dismissed` |
| `feedback_due_at` | 下一次反馈回看时间（次日分析时间） |
| `expires_at` | 观察期结束时间 |
| `title` / `observed` | 标题与观察到的现象 |
| `problem_understanding` | 六层理解结果 |
| `score` | 五维评分与决策 |
| `directions` / `primary_solution` / `other_solutions` | 探索方向与方案 |
| `comparison` / `closing_question` | 与当前方式的比较、留给用户的判断问题 |
| `evidence` / `confidence_notes` | 证据与不确定性说明 |
| `search_queries` | 后续核验用检索词 |
| `feedback` | 最近一次归因结果（`signal`、`confidence`、`reason`、`event_id`） |
| `feedback_event_ids` | 已参与归因的 Event |
| `source_event_ids` | 来源 Event |
| `last_evaluated_run_id` / `last_evaluated_at` | 最近一次回看记录 |

## 运行状态

`runtime/state.json`：

| 字段 | 说明 |
| --- | --- |
| `last_attempt_at` | 最近一次分析开始时间 |
| `last_success_at` | 最近一次成功时间，决定每日分析是否到期 |
| `last_run_id` | 最近一次运行 ID |
| `last_event_count` | 最近一次参与分析的事件数 |

`runtime/runs.json` 保存最近 200 次运行记录：`run_id`、`run_type`（`scheduled` / `manual`）、`status`、窗口、反馈汇总、`discovery_ids`、`error`。

## 时间与清理规则

1. 以实际运行时刻计算窗口；`latest_cutoff` 是最近一个已过的本地分析时间（默认 03:00，由 `schedule.hour` / `schedule.minute` 决定）。
2. 次日运行先回看：只检查 Discovery 生成之后、当前时刻之前的提问。
3. Discovery 到期且无兴趣 → 删除并写入 tombstone。
4. Event 按天整文件删除，不拆分单日文件。
