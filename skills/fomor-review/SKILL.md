---
name: fomor-review
description: 查看 Fomor 最近的探索结果、长期话题与待回看数量。当用户说「看看最近的探索」「Fomor 有什么发现」「打开昨天的报告」时使用。
user-invocable: true
disable-model-invocation: false
---

# 查看 Fomor 探索结果

只读操作，不触发分析、不改动数据。

## 执行

```bash
bin/fomor status
```

```bash
cat ~/.fomor/reports/latest.md
```

若用户设置了 `FOMOR_HOME`，用该目录替换 `~/.fomor`。

## 展示

1. 先给出概览：事件数、Topic 数、待回看 Discovery 数、已移入长期记忆数、最近成功运行时间。
2. 再展示 `latest.md` 的内容。
3. 如果用户想看某个历史日期，读取 `~/.fomor/reports/<YYYY-MM-DD>.md`。
4. 如果用户想看长期话题，读取 `~/.fomor/topics/*.json`，重点展示 `name`、`user_goal`、`interests`、`introduced_solutions`。

## 边界

- 不触发新的分析；用户需要新结果时应使用 `fomor-analyze`。
- 不删除或修改任何文件。
- 报告不存在时直接说明「今天还没有报告」，不要编造内容。
