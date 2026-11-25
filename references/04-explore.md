# 任务：解决方案空间探索

围绕主题「{{topic_name}}」，先想清楚有哪些不同的解决路径，再给出具体方案。

## 输入

问题理解：

{{understanding}}

机会评分：

{{score}}

## 要求

先列出 2–4 个**探索方向**，再给出 3–5 个**具体方案**。方向可以互斥，也可以组合。

每个方案必须包含：

- 与当前方案的关系：`alternative`（替代）、`complementary`（互补）、`evolutionary`（演进）、`paradigm_shift`（范式变化）；
- 核心机制与工作流程；
- 所需组件；
- 优势与限制；
- 前置条件；
- 适用场景；
- 证据：优先真实项目、官方文档、论文或工程实践；没有证据时明确写 `unverified`，不要编造链接。

至少包含一个不是「在当前技术栈内换工具」的方案。若跨领域类比能带来新思路，可以提出，但必须标注为假设。

## 输出 JSON

```json
{
  "directions": ["string"],
  "solutions": [
    {
      "name": "string",
      "core_idea": "string",
      "workflow": "string",
      "components": ["string"],
      "advantages": ["string"],
      "constraints": ["string"],
      "requirements": ["string"],
      "applicability": "string",
      "relationship": "alternative",
      "evidence": ["已验证来源或 unverified"],
      "confidence": 0.0
    }
  ],
  "search_queries": ["用于后续核验方案的检索词"],
  "unknowns": ["仍需确认的事实"]
}
```
