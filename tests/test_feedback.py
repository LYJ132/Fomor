import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fomor.config import ensure_initialized
from fomor.feedback import classify, evaluate_feedback
from fomor.paths import FomorPaths
from fomor.store import list_discoveries, load_topic, save_discovery
from fomor.utils import to_iso

NOW = datetime(2026, 11, 25, 19, 0, tzinfo=timezone.utc)


def make_discovery(created=NOW - timedelta(hours=6), expires=NOW + timedelta(days=3)):
    return {
        "discovery_id": "discovery_test",
        "topic_id": "topic_test",
        "topic_name": "数据服务架构",
        "created_at": to_iso(created),
        "expires_at": to_iso(expires),
        "status": "observing",
        "title": "把本地采集与云端数据库重新分层",
        "problem_understanding": {"goal": "构建稳定的数据服务"},
        "primary_solution": {"name": "职责分层", "core_idea": "解耦本地采集与云端存储"},
        "other_solutions": [{"name": "工作流引擎", "core_idea": "让任务可恢复"}],
        "feedback_event_ids": [],
        "feedback": {"signal": "none"},
    }


def make_event(text, at=NOW - timedelta(hours=1)):
    return {
        "event_id": f"evt_{abs(hash(text)) % 100000}",
        "user_message": text,
        "timestamp": to_iso(at),
        "analyzed_at": None,
    }


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = FomorPaths(Path(self.tmp.name))
        self.config = ensure_initialized(self.paths)

    def tearDown(self):
        self.tmp.cleanup()

    def test_topic_mention_is_strong(self):
        result = classify(make_discovery(), [make_event("数据服务架构还有别的方案吗？")], self.config)
        self.assertEqual(result["signal"], "strong")

    def test_explicit_marker_is_strong(self):
        result = classify(make_discovery(), [make_event("想试试 数据服务架构 的职责分层")], self.config)
        self.assertEqual(result["signal"], "strong")

    def test_negative_marker_is_dismissed(self):
        result = classify(make_discovery(), [make_event("数据服务架构我已经了解，不感兴趣")], self.config)
        self.assertEqual(result["signal"], "negative")

    def test_unrelated_question_is_neutral(self):
        result = classify(make_discovery(), [make_event("今天天气怎么样")], self.config)
        self.assertEqual(result["signal"], "none")


class EvaluateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = FomorPaths(Path(self.tmp.name))
        self.config = ensure_initialized(self.paths)

    def tearDown(self):
        self.tmp.cleanup()

    def test_interest_promotes_and_updates_topic(self):
        discovery = make_discovery()
        save_discovery(self.paths, discovery)
        events = [make_event("数据服务架构还有更稳的做法吗？")]
        summary = evaluate_feedback(self.paths, self.config, events, "run_1", NOW)
        self.assertEqual(summary["promoted"], [discovery["discovery_id"]])
        self.assertEqual(list_discoveries(self.paths, status="observing"), [])
        promoted = list_discoveries(self.paths, status="promoted")
        self.assertEqual(len(promoted), 1)
        topic = load_topic(self.paths, "topic_test")
        self.assertEqual(len(topic["interests"]), 1)

    def test_no_interest_expires_after_window(self):
        discovery = make_discovery(
            created=NOW - timedelta(days=10),
            expires=NOW - timedelta(days=3),
        )
        save_discovery(self.paths, discovery)
        summary = evaluate_feedback(self.paths, self.config, [], "run_1", NOW)
        self.assertEqual(summary["expired"], [discovery["discovery_id"]])
        self.assertEqual(list_discoveries(self.paths, status="observing"), [])
        tombstones = list(self.paths.tombstones_dir.glob("*.json"))
        self.assertEqual(len(tombstones), 1)

    def test_unexpired_neutral_discovery_is_kept(self):
        discovery = make_discovery()
        save_discovery(self.paths, discovery)
        summary = evaluate_feedback(self.paths, self.config, [], "run_1", NOW)
        self.assertEqual(summary["expired"], [])
        self.assertEqual(len(list_discoveries(self.paths, status="observing")), 1)
        kept = list_discoveries(self.paths, status="observing")[0]
        self.assertEqual(kept["last_evaluated_run_id"], "run_1")


if __name__ == "__main__":
    unittest.main()
