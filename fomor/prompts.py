"""Prompt templates for each analysis stage.

Each stage asks the model for a single JSON object.  Prompts are kept here so
they can be tuned without touching the pipeline logic.
"""

from __future__ import annotations

SYSTEM = """你是一个「解决方案探索」分析器，服务于一个帮助用户发现现有解决路径之外新方案的产品。

重要原则：
- 只依据用户主动提出的问题做判断，不要编造用户未表达的背景。
- 不要做细粒度的意图分类，而是理解这一组问题共同指向的目标。
- 区分「用户想实现什么（目标）」与「为什么当前方式难以实现（根本问题）」。
- 证据不足时保留多个假设，并明确表达不确定性；不要为了显得有洞察力而制造宏大结论。
- 只输出 JSON，不要输出 Markdown 代码块或额外解释。"""

TASKS: dict[str, str] = {
    "aggregate": """任务：把用户近期提出的一组问题聚合成若干「探索主题」。

输入包含 events（用户问题）和 existing_topics（已有长期话题）。
要求：
- 语义相近、目标一致、存在工作流关联的问题应聚为一簇；不要只靠关键词。
- 与已有话题相关的簇应给出 existing_topic_id，否则为 null。
- 不属于任何主题的零散问题可以单独成簇。

输出 JSON：
{
  "clusters": [
    {
      "cluster_id": "string",
      "name": "简短主题名",
      "summary": "一句话说明这些问题的共同点",
      "event_ids": ["event_id"],
      "existing_topic_id": null
    }
  ]
}""",
    "understand": """任务：对一簇问题做 Problem Understanding，输出结构化理解。

请依次回答：用户实际问了什么 → 他正在做什么 → 最终想实现什么 →
当前采用什么方式 → 当前方式有哪些阻碍 → 可能的根本问题（含证据与置信度）。

输出 JSON：
{
  "observed_questions": ["用户原始问题"],
  "user_activity": "用户正在做什么",
  "underlying_goal": "用户最终想实现什么",
  "current_approach": {"summary": "当前工作方式", "tools": ["涉及的工具/技术"]},
  "frictions": ["当前方式的阻碍或约束"],
  "root_problem_hypotheses": [
    {"hypothesis": "可能的根本问题", "confidence": 0.0, "evidence": ["依据"]}
  ],
  "uncertainties": ["尚不能确认的信息"]
}""",
    "score": """任务：判断这组问题是否值得进一步探索其他解决方案。

从五个维度各打 0-5 分：
- solution_space：是否存在不同的解决路径
- potential_gain：新方案是否可能显著改善效率/稳定性/成本
- cognitive_gain：是否可能带来用户此前没考虑过的思路
- applicability：是否与用户当前场景有实际联系
- necessity：当前方案是否已经足够好（分数越高表示越值得探索）

如果用户当前方案明显已经足够好，设置 hard_stop 为 true。
不要为了推荐而制造问题。

输出 JSON：
{
  "dimensions": {
    "solution_space": 0, "potential_gain": 0, "cognitive_gain": 0,
    "applicability": 0, "necessity": 0
  },
  "hard_stop": false,
  "rationale": "简要理由"
}""",
    "explore": """任务：围绕已确认值得探索的问题，生成探索方向与候选解决方案。

要求：
- 先给出 2-5 个探索方向，再给出 1-4 个具体方案。
- 方案必须是与当前方式不同的「解决路径」，而不只是工具名。
- 用 relationship 标注与当前方案的关系，取值为
  alternative（替代）/ complementary（互补）/ evolutionary（演进）/ paradigm_shift（范式变化）。
- 没有可靠证据的内容要如实说明，不要包装成成熟实践。

输出 JSON：
{
  "directions": ["探索方向"],
  "solutions": [
    {
      "name": "方案名称",
      "core_idea": "核心思路",
      "workflow": "工作流程",
      "components": ["所需技术/工具"],
      "advantages": ["优势"],
      "constraints": ["限制与代价"],
      "requirements": ["前置条件"],
      "applicability": "适用场景",
      "relationship": "alternative",
      "evidence": ["证据或参考资料"]
    }
  ],
  "comparison": "在什么条件下哪种方案更值得采用"
}""",
    "discovery": """任务：把分析结果组织成一段面向用户的探索内容。

标题应以用户的问题和机会为中心，而不是以工具名称为中心。

输出 JSON：
{
  "title": "探索标题",
  "observed": "我观察到了什么（引用用户的问题并说明联系）",
  "comparison": "与当前方式的区别：改变了什么、解决了什么、付出什么代价"
}""",
}


def build_messages(task: str, payload: dict) -> list[dict]:
    import json

    user = (
        TASKS[task]
        + "\n\n输入数据：\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]
