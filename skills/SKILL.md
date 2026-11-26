---
name: fomor
description: Use when the user asks to set up, check, or repair Fomor (hook collection, daily automation, data directory). Verifies the local deployment and provides the automation-task template.
user-invocable: true
disable-model-invocation: false
---

# Fomor

Fomor 采集用户在 Trae 中提出的问题（`UserPromptSubmit` Hook），由 Trae 自动化任务每天在配置时间（默认 03:00）分析一次，报告写入 `~/.fomor/reports/`。它不向会话注入内容。

职责划分（先读懂再动手）：

| 组件 | 触发时机 | 做什么 | 绝不做什么 |
| --- | --- | --- | --- |
| `SessionStart` Hook（`scripts/fomor session-start`） | 每次会话开始 | 静默校验/补齐环境，补跑错过的分析 | 不创建自动化任务，不输出任何内容 |
| `UserPromptSubmit` Hook（`scripts/fomor hook`） | 用户发消息 | 追加事件到本地文件 | 不阻塞提问，不注入上下文 |
| **自动化任务** | 每天定时 | 调用 `scripts/fomor analyze --scheduled` 并展示报告 | — |
| **本技能** | 用户主动调用 | 检查部署、指导创建自动化任务 | 不代替用户创建任务 |

用户调用本技能时，按下面三步执行，每步把结果同步给用户。

## 第一步：环境与依赖检查

```bash
scripts/fomor session-start --verbose
```

判定：

- `ok: true` → Python 版本、`~/.fomor/` 目录、默认配置全部就绪；
- `repaired` 非空 → 缺失项已被静默补齐，告知用户即可；
- `missing` 含 `python` → 先请用户安装 Python 3.10+，流程终止。

再检查 Hook 注册情况：读取全局 `~/.trae-cn/hooks.json`（国际版为 `~/.trae/hooks.json`）或项目 `.trae/hooks.json`，确认存在两条命令（`<插件根目录>` 用实际绝对路径替换）：

```text
UserPromptSubmit → <插件根目录>/scripts/fomor hook
SessionStart     → <插件根目录>/scripts/fomor session-start
```

缺失时把仓库 `hooks/hooks.json` 的内容合并进去并替换 `${TRAE_PLUGIN_ROOT}`，然后提醒用户在「设置 > Hooks」启用并接受安全提示（项目级 Hook 还需信任工作区）。注意：`session-start` 只做环境初始化与补跑，**创建自动化任务不在这条链路里**，由下一步完成。

## 第二步：提供自动化任务模板（本技能的核心交付）

每天的分析由 Trae「自动化」任务驱动，需要用户手动创建。请用户在 Trae 的「自动化」中新建任务，按以下模板填写（`<时间>` 取 `scripts/fomor status` 输出的 `schedule` 值）：

```text
任务名称：Fomor 每日探索
触发：每天 <时间>
运行环境：本地
任务内容：
使用 fomor 技能完成今天的分析：
1. 在插件目录运行 scripts/fomor analyze --scheduled；
2. 如果输出是「还没到下一次分析，且已有成功运行记录。」，直接结束，不要重复执行，也不要展示任何内容；
3. 否则把输出的 Markdown 报告完整展示给我，并在末尾补充说明：继续追问的方向会移入长期记忆，没有追问的内容 7 天后自动删除；
4. 如果输出「分析失败：…」，原样转述错误，并提示检查 ~/.fomor/config/settings.json 的模型配置。
```

同时告知用户：

- 本地任务在电脑睡眠时不执行；错过的分析由 `SessionStart` Hook 在下次唤醒时自动补跑，无需为此额外配置系统唤醒；
- 运行环境与输出位置在任务创建后不可修改，选错需删除重建；
- 修改分析时间：改 `~/.fomor/config/settings.json` 的 `schedule.hour` / `schedule.minute`，并同步修改自动化任务的触发时间。

## 第三步：验收

```bash
printf '%s' '{"session_id":"setup-check","prompt":"Fomor 安装自检","hook_event_name":"UserPromptSubmit"}' | scripts/fomor hook
scripts/fomor status
```

- `events` 增加 1，且重复执行同一问题出现 `duplicate event skipped` → 采集链路正常；
- 从 `~/.fomor/events/<当天>.jsonl` 删除 `session_id` 为 `setup-check` 的自检记录；
- 最后向用户列出剩余动作清单（通常是：创建自动化任务、在设置中启用 Hook）。

## 其他材料（不属于本技能流程）

- `references/00-system.md` ~ `06-feedback.md`：分析引擎的提示词契约，由 `scripts/fomor` 在分析时自动加载，无需阅读；
- `references/07-data-model.md`：`~/.fomor/` 目录与字段说明，排查数据问题时查阅；
- 日常看报告不走本技能：`cat ~/.fomor/reports/latest.md`。
