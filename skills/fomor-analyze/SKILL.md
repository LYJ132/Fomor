---
name: fomor-analyze
description: 执行 Fomor 每日分析：先回看昨日 Discovery 的隐式反馈，再聚合并理解新问题、评估探索价值、生成 Discovery 报告。由每天 03:00 的 Trae 自动化任务调用，也可手动触发。
user-invocable: true
disable-model-invocation: false
---

# Fomor 每日分析

本技能执行一次完整分析并把结果交给用户。分析逻辑全部在本地 CLI 中，Skill 只负责调用与展示，不要自行编造探索内容。

## 执行

```bash
bin/fomor analyze --scheduled
```

- 由 03:00 自动化任务调用时必须带 `--scheduled`：只有在越过最近一次 03:00 且没有更新成功记录时才执行。
- 用户手动要求立即分析时可省略 `--scheduled`。
- 模型模式默认 `mock`，离线可跑通。需要真实分析时，在 `~/.fomor/config/settings.json` 中把 `llm.mode` 改为 `traecli` 或 `openai`，并确认对应环境变量。

## 输出处理

1. 命令输出的第一种情况是 `还没到下一次 03:00，且已有成功运行记录。`
   - 直接告诉用户本次跳过，不要重复执行。
2. 其他情况输出的是完整 Markdown 报告。
   - 把报告内容完整呈现给用户。
   - 可以在末尾补充一句：继续追问某个方向，它会在下次分析时被移入长期记忆；没有追问的内容会在 7 天后删除。
3. 如果报告里出现「分析失败：…」，原样转述错误，并提示检查 `~/.fomor/config/settings.json` 的模型配置与网络。

## 边界

- 不修改用户项目文件。
- 不向用户正在进行的 Agent 会话注入内容。
- 不虚构证据：报告里没有的链接、工具与结论不要补充。
- 报告同时保存在 `~/.fomor/reports/<日期>.md` 与 `latest.md`。

## 反馈规则（说明用）

- 分析前先回看：对仍在观察期的 Discovery，检查其生成之后用户又提了哪些问题。
- 强/弱兴趣 → 移入长期记忆（`discoveries/promoted/` 与 Topic 的 `interests`）。
- 明确表示已了解或不感兴趣 → 记入 `dislikes` 并移除。
- 7 天无相关提问 → 到期删除，仅保留 90 天指纹用于去重。
