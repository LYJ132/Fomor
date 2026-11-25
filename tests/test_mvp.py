from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from fomor import events, memory, pipeline
from fomor.cli import main
from fomor.delivery import render_report


class FomorTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._old_home = os.environ.get("FOMOR_HOME")
        os.environ["FOMOR_HOME"] = str(self.root)

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("FOMOR_HOME", None)
        else:
            os.environ["FOMOR_HOME"] = self._old_home
        self._tmp.cleanup()

    def test_event_dedup(self):
        first = events.record_event("如何管理本地定时任务？", event_id="evt_fixed", root=self.root)
        second = events.record_event("重复写入", event_id="evt_fixed", root=self.root)
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(len(events.all_events(self.root)), 1)

    def test_pipeline_mock_end_to_end(self):
        items = json.loads((Path(__file__).parent.parent / "examples" / "case-data-service.json").read_text("utf-8"))
        events.import_events(items, root=self.root)

        result = pipeline.analyze(self.root)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["discoveries"]), 1)

        discoveries = memory.load_discoveries(self.root)
        self.assertEqual(len(discoveries), 1)
        discovery = discoveries[0]
        self.assertIn("underlying_goal", discovery["problem_understanding"])
        self.assertTrue(discovery["primary_solution"]["name"])
        self.assertGreaterEqual(len(discovery["other_solutions"]), 1)

        report = Path(result["report"])
        self.assertTrue(report.exists())
        self.assertIn("探索结果", report.read_text("utf-8"))

        # events consumed by analysis are marked and no longer pending
        self.assertEqual(events.pending_events(self.root), [])

    def test_feedback_updates_topic(self):
        events.record_event("本地服务如何连接云端数据库？", root=self.root)
        pipeline.analyze(self.root, deliver=False)
        discovery = memory.load_discoveries(self.root)[0]
        result = memory.apply_feedback(discovery["discovery_id"], "already_known", root=self.root)
        self.assertEqual(result["action"], "already_known")
        topic = memory.find_topic(discovery["topic_id"], self.root)
        self.assertTrue(topic["known"])
        self.assertIn(discovery["primary_solution"]["name"], topic["known"])

    def test_cleanup_removes_old_event_files(self):
        old = self.root / "events" / "2020-01-01.json"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text(json.dumps({"date": "2020-01-01", "events": [{"event_id": "x"}]}), encoding="utf-8")
        result = events.cleanup_expired(self.root)
        self.assertEqual(result["removed_days"], 1)
        self.assertFalse(old.exists())

    def test_cli_collect_and_report(self):
        self.assertEqual(main(["--root", str(self.root), "collect", "测试一条问题", "--platform", "test"]), 0)
        self.assertEqual(len(events.all_events(self.root)), 1)
        path = render_report(self.root)
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
