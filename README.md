# Fomor

一个适配 Agent 平台（首个目标为 Trae）的 **AI 探索助手**：通过分析用户在日常工作中提出的问题，在理解用户当前目标与解决方式的基础上，主动发现其现有路径之外值得尝试的新解决方案。

不是技术资讯日报，也不向 Agent 注入内容或干预会话。

## 文档

- [产品需求文档（PRD）](./docs/PRD.md)
- [待确认问题清单](./docs/open-questions.md)

## 快速开始

无需第三方依赖，Python 3.11+ 即可运行。默认使用离线 Mock 模型，开箱可跑通完整链路。

```bash
python3 -m fomor init
python3 -m fomor import examples/case-data-service.json
python3 -m fomor analyze
open data/report.html
```

`analyze` 会完成：问题聚合 → Problem Understanding → 探索机会评分 → 方案生成 → 生成 Discovery → 输出 HTML。

## 常用命令

| 命令 | 说明 |
|---|---|
| `fomor init` | 初始化数据目录与默认配置 |
| `fomor collect "问题" --session-id s1` | 记录一条用户问题 |
| `fomor import case.json` | 从 JSON 文件导入事件（`-` 读 stdin） |
| `fomor hook` | Hook 入口，从 stdin 读取 JSON 并记录事件 |
| `fomor analyze` | 立即运行一次分析并生成报告 |
| `fomor run` | 启动后台调度器（每天固定时间分析一次） |
| `fomor list [discoveries\|topics\|tasks]` | 列出探索结果 / 话题 / 任务 |
| `fomor show <discovery_id>` | 查看一条探索结果 |
| `fomor feedback <id> --action interested` | 提交反馈 |
| `fomor cleanup` | 清理超过保留期的原始事件 |
| `fomor report` | 用已有数据重新生成 HTML |

反馈动作：`interested` / `continue` / `already_known` / `not_interested` / `irrelevant` / `applied` / `no_feedback`。

## 接入 Agent Hook

Hook 只负责快速记录一条用户问题，不做任何模型调用或分析。任何能执行命令并传入 JSON 的平台都可以接入：

```bash
echo '{"user_message":"如何管理本地定时任务？","session_id":"s1"}' | python3 -m fomor hook --platform trae
```

接受的字段：`user_message`（或 `message` / `prompt`）、`session_id`、`timestamp`、`event_id`、`platform`。

> Trae 的具体 Hook 注册方式尚未验证。若暂不可用，可先用 `fomor import` 或 `fomor collect` 跑通链路。

## 配置

配置位于 `data/config/settings.json`（数据目录可用 `FOMOR_HOME` 或 `--root` 指定）。

```json
{
  "analysis_hour": 3,
  "retention_hours": 48,
  "llm": {
    "mock": true,
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "api_key_env": "FOMOR_LLM_API_KEY"
  },
  "scoring": { "explore_threshold": 3.5, "watch_threshold": 2.0 }
}
```

接入真实模型：

```bash
export FOMOR_LLM_API_KEY=sk-...
# 将 settings.json 中 llm.mock 改为 false
```

任何 OpenAI 兼容的 `/chat/completions` 服务都可用（OpenAI、DeepSeek、通义等），只需修改 `base_url` 与 `model`。

## 目录结构

```
fomor/
  config.py       配置与数据目录
  events.py       短期事件采集 / 去重 / 清理
  llm.py          模型接入（Mock + OpenAI 兼容）
  prompts.py      各分析阶段的提示词
  pipeline.py     聚合 → 理解 → 评分 → 探索 → Discovery
  memory.py       长期 Topic、Discovery、反馈、生命周期
  delivery.py     静态 HTML 交付
  search.py       可插拔搜索 Provider（MVP 为 none）
  scheduler.py    每日定时分析
  cli.py          命令行入口

data/             （gitignore）
  config/ events/ topics/ discoveries/ runtime/ logs/ report.html
```

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 当前范围（MVP）

已实现：事件采集与幂等、问题聚合、Problem Understanding、探索评分与三档判断、候选方案生成、Discovery 结构化输出、Topic 长期记忆与反馈、日志与任务状态、过期清理、静态 HTML 报告。

未实现（见待确认问题清单）：真实搜索 Provider、会话上下文按需读取、多平台适配、IM / APP 交付、自动方案验证与评分细则。
