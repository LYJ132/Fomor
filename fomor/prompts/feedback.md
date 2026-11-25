# 任务：隐式反馈归因

判断用户在观察窗内的新提问，是否对某条已交付的 Discovery 表现出兴趣。不要读心，只根据文本证据。

## 输入

Discovery：

{{discovery}}

观察窗内的事件（均发生在交付之后）：

{{feedback_events}}

## 判定

- `strong`：再次提到同一方案/话题/链接，明确追问细节、要求继续、表示要尝试；
- `weak`：询问同一主题下的相邻问题，但没有直接指向该 Discovery；
- `negative`：明确表示已了解、不感兴趣、不相关；
- `none`：没有相关提问。

## 规则

- 用户只是继续做日常工作，不等于对推荐感兴趣；
- 同一句话可能同时涉及多个 Discovery，只选择证据最强的一个，并说明；
- 无法判断时输出 `none`，不要过度归因；
- 沉默不是负向信号。

## 输出 JSON

```json
{
  "signal": "strong | weak | negative | none",
  "confidence": 0.0,
  "matched_event_ids": ["evt_..."],
  "reason": "引用具体表述，说明为什么",
  "topic_update": {
    "interest": "string or null",
    "known": "string or null",
    "dislike": "string or null"
  }
}
```
