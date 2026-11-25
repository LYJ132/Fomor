import unittest

from fomor.prompts import build_prompt, describe_tasks, load_system
from fomor.utils import extract_json


EVENTS = [
    {"event_id": "evt_1", "user_message": "如何迁移数据库？", "timestamp": "2026-11-25T00:00:00+00:00"},
]

SAMPLES = {
    "aggregate": {"date": "2026-11-25", "events": EVENTS},
    "understand": {"topic_name": "数据服务架构", "events": EVENTS},
    "opportunity": {"topic_name": "数据服务架构", "understanding": {"goal": "构建稳定服务"}},
    "explore": {
        "topic_name": "数据服务架构",
        "understanding": {"goal": "构建稳定服务"},
        "score": {"total": 3.8, "decision": "explore"},
    },
    "discovery": {
        "topic_name": "数据服务架构",
        "events": EVENTS,
        "understanding": {"goal": "构建稳定服务"},
        "score": {"total": 3.8, "decision": "explore"},
        "exploration": {"solutions": [{"name": "职责分层"}]},
    },
    "feedback": {
        "discovery": {"topic_name": "数据服务架构", "title": "分层"},
        "feedback_events": EVENTS,
    },
}


class PromptTest(unittest.TestCase):
    def test_every_task_has_a_prompt_file(self):
        self.assertEqual(describe_tasks(), sorted(SAMPLES))

    def test_all_placeholders_are_rendered(self):
        for task, variables in SAMPLES.items():
            rendered = build_prompt(task, variables)
            self.assertNotIn("{{", rendered, f"unrendered placeholder in {task}.md")
            self.assertIn("Fomor 分析引擎", rendered)

    def test_events_are_embedded_as_json(self):
        rendered = build_prompt("aggregate", SAMPLES["aggregate"])
        self.assertIn("evt_1", rendered)
        self.assertIn("如何迁移数据库？", rendered)

    def test_output_contracts_are_parseable_json_examples(self):
        for task in SAMPLES:
            text = build_prompt(task, SAMPLES[task])
            block = text.split("```json")[-1].split("```")[0]
            payload = extract_json(block)
            self.assertIsInstance(payload, dict)

    def test_system_prompt_forbids_injection(self):
        system = load_system()
        self.assertIn("输出严格 JSON", system)
        self.assertIn("不为推荐而制造问题", system)


if __name__ == "__main__":
    unittest.main()
