---
name: fomor-setup
description: 安装与配置 Fomor：初始化 ~/.fomor、接入 Trae Hook、创建每天 03:00 的自动化任务，并做一次自检。当用户说「安装 Fomor」「配置 Fomor」「接入 Hook」时使用。
user-invocable: true
disable-model-invocation: false
---

# Fomor 安装与配置

Fomor 由三部分组成：Trae Hook 采集问题、Trae 自动化任务每天 03:00 分析、`~/.fomor/` 保存长期记忆。本技能只负责安装与自检，不分析数据。

## 前置检查

1. 确认 Python 可用：`python3 --version`（需要 3.10+）。
2. 确认当前仓库位置，后续命令统一使用 `bin/fomor`（脚本会自动定位仓库根目录）。
3. 提醒用户：`~/.fomor/` 只存本地数据，不写入插件目录，也不上传。

## 步骤一：初始化数据目录

```bash
bin/fomor init
```

预期输出包含 `initialized:` 与 `schedule: every day at 03:00`。如用户设置了 `FOMOR_HOME`，以该目录为准。

## 步骤二：安装采集 Hook

参考 `.trae/hooks.example.json`，把 `/absolute/path/to/fomor` 替换成仓库真实绝对路径。

- 全局 Hook：写入 `~/.trae-cn/hooks.json`（国内版）或 `~/.trae/hooks.json`（国际版）。
- 项目 Hook：写入当前工作区的 `.trae/hooks.json`。

需要注册两个事件：

| 事件 | 命令 | 作用 |
| --- | --- | --- |
| `UserPromptSubmit` | `bin/fomor hook` | 记录用户提问 |
| `SessionStart` | `bin/fomor catch-up` | 首次唤醒时补跑错过的 03:00 分析 |

安装后必须提醒用户：

1. 在「设置 > Hooks」确认已启用，并接受安全提示。
2. 项目 Hook 需要信任当前工作区。
3. Hook 必须快速返回；Fomor 的 Hook 只写本地文件、始终以退出码 0 结束，不会阻断提问。

## 步骤三：创建每天 03:00 的自动化任务

在 Trae 的「自动化」中手动新建任务：

- 名称：`Fomor 每日探索`
- 触发：每天 03:00
- 运行环境：本地（需要读取本机 `~/.fomor/`）
- 任务内容：`使用 fomor-analyze 技能执行今天的分析，并把报告完整展示出来`

注意两点：

- 本地任务要求电脑保持唤醒；睡眠期间不会执行，由 `SessionStart` 的 `catch-up` 在下次唤醒时补跑。
- 任务创建后运行环境与输出位置不可修改。

## 步骤四：自检

```bash
printf '%s' '{"session_id":"setup-check","prompt":"Fomor 安装自检","hook_event_name":"UserPromptSubmit"}' | bin/fomor hook
bin/fomor status
```

通过标准：

- `event` 写入成功（`status` 里 `events` 增加 1）。
- 重复执行同一条自检问题不会重复计数。
- `status` 能显示 `home`、`latest_cutoff` 与报告路径。

自检完成后，建议删除这条自检事件：从 `~/.fomor/events/<当天>.jsonl` 中移除 `session_id` 为 `setup-check` 的记录。

## 失败处理

- Hook 报错：只写 stderr，不影响用户提问；查看 `~/.fomor/logs/catchup.log` 与 Trae 的 Agent Hooks 日志。
- `catch-up` 没有执行：确认当前时间已过最近一次 03:00，且 `state.json` 中没有更新的成功记录。
- 目录权限：`~/.fomor` 应为 `0700`，不要在共享目录中初始化。
