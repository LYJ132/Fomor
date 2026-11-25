---
name: fomor
description: Use when setting up Fomor, running the daily 03:00 analysis, or reviewing what Fomor explored. One SOP covers install, hook verification, analysis, report review, feedback and retention. Do not split this flow into separate skills.
user-invocable: true
disable-model-invocation: false
---

# Fomor

Fomor 是一个本地探索助手：采集你在 Trae 中提出的问题，每天 03:00 分析一次，尝试给出**另一条解决路径**，并把你的后续提问当作反馈。数据只存在本机 `~/.fomor/`，不向 Agent 会话注入内容。

本文件是唯一操作入口。安装、分析、查看、排障属于同一条 SOP，不要拆成多个技能。

## 工作方式

```text
UserPromptSubmit Hook            SessionStart Hook
        │                              │
        ▼                              ▼
  events/ 追加问题            ① 并行校验环境（Python、目录、settings）
                              ② 缺失项静默补齐，无第三方依赖则不下载
                              ③ catch-up：补跑错过的 03:00
        │                              │
        └──────────► 03:00 分析 ◄──────┘
                        │
          ① 回看昨日 Discovery 的反馈
          ② 聚合 → 六层理解 → 机会评分 → 方案探索
                        │
                        ▼
        reports/latest.md + discoveries/pending/
                        │
             次日提问 → 有兴趣则提升为 Topic
                      → 无兴趣则到期删除
```

## 仓库约定

| 目录 | 放什么 | 运行时是否读取 |
| --- | --- | --- |
| `scripts/fomor` | 唯一可执行入口（单文件，无扩展名） | Hook 与分析命令调用 |
| `hooks/hooks.json` | Hook 事件绑定：采集 + SessionStart 环境校验 | 平台加载 |
| `references/` | 静态参考：提示词契约、数据模型 | 代码与 Agent 按需读取 |
| `skills/` | Agent 操作流程（本文件） | 平台加载 |
| `docs/` | 维护者文档（PRD、调研、问题清单） | 否 |
| `tests/` | 标准库单元测试 | 开发时运行 |

原则：

- 可执行逻辑只放 `scripts/` 与 `hooks/`；
- `references/` 只放「读」的内容，不放可执行代码；
- 同一个 SOP 只写一个 skill，不按步骤拆分。

## 安装（一次性）

1. 确认 Python：`python3 --version`，需要 3.10+。
2. 数据目录不需要手动创建：`SessionStart` 的 `session-start` 会在首次会话时静默校验并补齐 `~/.fomor/`、`config/settings.json` 与各子目录；默认根目录为 `~/.fomor`，可用 `FOMOR_HOME` 覆盖，权限 `0700`。需要提前初始化或排查时可手动执行：

   ```bash
   scripts/fomor init
   scripts/fomor session-start --verbose   # 查看环境校验报告
   ```

3. 接入 Hook。插件安装时会加载 `hooks/hooks.json`；若 Trae 未自动加载，把该文件内容复制到全局 `hooks.json`，将 `${TRAE_PLUGIN_ROOT}` 替换为仓库绝对路径，然后在「设置 > Hooks」启用并接受安全提示。项目级 Hook 还需要信任当前工作区。
   - `UserPromptSubmit` → `scripts/fomor hook`
   - `SessionStart` → `scripts/fomor session-start`

4. 在 Trae「自动化」中创建任务：名称 `Fomor 每日探索`，每天 03:00，**本地运行**，任务内容为「使用 fomor 技能执行今日分析并展示报告」。

   本地任务要求电脑保持唤醒。睡眠期间不会执行，由 `SessionStart` 的 `session-start` 在下次唤醒时补跑。

5. 自检：

   ```bash
   printf '%s' '{"session_id":"setup-check","prompt":"Fomor 安装自检","hook_event_name":"UserPromptSubmit"}' | scripts/fomor hook
   scripts/fomor status
   ```

   `events` 增加 1 即通过。之后从 `~/.fomor/events/<当天>.jsonl` 删除这条自检记录。

## 每日分析

由 03:00 自动化任务执行：

```bash
scripts/fomor analyze --scheduled
```

- 若输出 `还没到下一次 03:00，且已有成功运行记录。`，说明本次无需执行，直接告知用户，不要重复跑。
- 否则输出完整 Markdown 报告：完整展示给用户，可在末尾补一句「继续追问某个方向，它会在下次分析时被移入长期记忆；没有追问的内容会在 7 天后删除」。
- 出现 `分析失败：…` 时原样转述，并检查 `~/.fomor/config/settings.json` 的模型配置。

用户要求立即分析时去掉 `--scheduled`：

```bash
scripts/fomor analyze
```

默认 `llm.mode = mock`，离线可跑通。真实分析改为 `traecli` 或 `openai`，并确认对应环境变量。

## 查看结果

```bash
scripts/fomor status
```

然后读取 `~/.fomor/reports/latest.md`。历史报告在 `~/.fomor/reports/<YYYY-MM-DD>.md`，长期话题在 `~/.fomor/topics/*.json`（重点看 `name`、`user_goal`、`interests`、`introduced_solutions`）。字段含义见 `references/07-data-model.md`。

## 反馈与保留

- 分析开始前先回看：对仍在观察期的 Discovery，检查生成之后用户又提了哪些问题。
- 强/弱兴趣 → 移入长期记忆（`discoveries/promoted/`，并写入 Topic 的 `interests`）。
- 明确表示已了解/不感兴趣 → 记入 `dislikes` 并移除。
- 7 天无相关提问 → 到期删除，只保留 90 天指纹用于去重。
- Event 保留 8 天（7 天窗口 + 1 天缓冲）；沉默不是负向信号。

## 边界

- 不修改用户项目文件，不向 Agent 会话注入内容。
- 不虚构证据：报告里没有的链接、工具与结论不要补充。
- 不触发与用户请求无关的分析。

## Reference Index

| 文件 | 何时读 |
| --- | --- |
| [00-system.md](../references/00-system.md) | 分析引擎的全局规则与输出约束 |
| [01-aggregate.md](../references/01-aggregate.md) | 问题如何聚合成主题 |
| [02-understand.md](../references/02-understand.md) | 六层问题理解 |
| [03-opportunity.md](../references/03-opportunity.md) | 五维评分与 explore/watch/none 判定 |
| [04-explore.md](../references/04-explore.md) | 方案空间与方案字段 |
| [05-discovery.md](../references/05-discovery.md) | 报告正文的生成契约 |
| [06-feedback.md](../references/06-feedback.md) | 隐式反馈归因规则 |
| [07-data-model.md](../references/07-data-model.md) | `~/.fomor/` 目录与字段 |

## 排障

- Hook 报错只写入 stderr，不影响用户提问；查看 Trae 的 Agent Hooks 日志与 `~/.fomor/logs/catchup.log`。
- `catch-up` 未执行：确认已过最近一次 03:00，且 `runtime/state.json` 中没有更新的成功记录。
- 数据目录权限异常：不要在共享目录初始化；重新执行 `scripts/fomor init` 会把根目录权限修正为 `0700`。
