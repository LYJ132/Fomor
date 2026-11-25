# 任务：问题理解（六层模型）

围绕主题「{{topic_name}}」，从事件中还原用户正在做什么、想实现什么、当前怎么做、卡在哪里。

## 输入事件

{{events}}

## 六层要求

1. **Observed Questions**：用户实际问的问题，保留原文。
2. **User Activity / Context**：用户正在推进什么工作。不要做过度精细的意图分类。
3. **Underlying Goal**：用户最终想实现什么。
4. **Current Approach**：当前使用的工具、流程、职责划分、已做出的技术选择。
5. **Friction / Constraints**：当前方式的阻碍与约束。
6. **Root Problem Hypotheses**：值得解决的问题假设。每个假设必须有证据事件 ID 和置信度。

## 约束

- 不要求每一层都有确定答案；缺失就写 `unknown` 或空数组。
- 多个竞争性假设要同时保留，不要强行选一个「最深刻」的。
- 不要把「用户问了很多问题」本身当成根本问题。
- 如果现有方案看起来已经足够好，在 `assessment` 中明确写出。

## 输出 JSON

```json
{
  "observed_questions": ["原文"],
  "activity": "string",
  "goal": "string",
  "current_approach": "string",
  "frictions": ["string"],
  "root_problem_hypotheses": [
    {
      "hypothesis": "string",
      "confidence": 0.0,
      "evidence_event_ids": ["evt_..."],
      "counter_evidence": "string or null"
    }
  ],
  "open_questions": ["string"],
  "assessment": "evidence_sufficient | weak | current_approach_is_fine",
  "notes": "string"
}
```
