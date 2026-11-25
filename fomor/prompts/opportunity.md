# 任务：探索机会评分

判断「围绕该主题，是否存在值得用户了解的其它解决方案」。评分对象是问题空间，不是单条消息，也不是技术是否热门。

## 输入

主题：{{topic_name}}

问题理解：

{{understanding}}

## 五个维度（1–5 分）

| 维度 | 判断 |
| --- | --- |
| solution_space | 是否存在不同的解决路径，而不是只能继续当前做法 |
| potential_gain | 新路径是否可能明显改善效率、稳定性或成本 |
| cognitive_gain | 是否可能让用户接触到此前没考虑过的思路 |
| applicability | 新路径是否与用户当前场景有实际联系 |
| necessity | 用户当前方案是否已经足够好（越低表示越没必要探索） |

## 硬性规则

- 当前方案已经很好、或问题只是一次性报错：`decision = none`。
- 只能给出模糊的「可以了解一下」：`decision = watch`。
- 只有存在具体替代路径，且与输入证据相关：`decision = explore`。
- 不要为了产出内容而抬高分数。

## 输出 JSON

```json
{
  "dimensions": {
    "solution_space": 1,
    "potential_gain": 1,
    "cognitive_gain": 1,
    "applicability": 1,
    "necessity": 1
  },
  "total": 0.0,
  "decision": "explore | watch | none",
  "rationale": "必须引用问题理解中的证据或不确定性",
  "blocking_questions": ["如果这些没答案就不该推荐"]
}
```
