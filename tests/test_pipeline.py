import support  # noqa: F401
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fomor.config import ensure_initialized
from fomor.paths import FomorPaths
from fomor.pipeline import run_analysis
from fomor.store import append_event, list_discoveries, list_topics, normalize_hook_payload

NOW = datetime(2026, 11, 25, 19, 0, tzinfo=timezone.utc)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = FomorPaths(Path(self.tmp.name))
        self.config = ensure_initialized(self.paths)

    def tearDown(self):
        self.tmp.cleanup()

    def _collect(self, prompt, at):
        event = normalize_hook_payload({"session_id": "s1", "prompt": prompt}, now=at)
        append_event(self.paths, self.config, event)
        return event

    def test_first_run_produces_report_and_discovery(self):
        self._collect("如何把本地 Docker 数据库迁移到 Supabase？", NOW - timedelta(hours=2))
        self._collect("本地数据采集服务应该部署在哪里？", NOW - timedelta(hours=1))

        result = run_analysis(self.paths, config=self.config, now=NOW)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["discoveries"]), 1)
        self.assertTrue((self.paths.reports_dir / "latest.md").exists())
        self.assertEqual(len(list_topics(self.paths)), 1)
        self.assertEqual(len(list_discoveries(self.paths, status="observing")), 1)
        report = (self.paths.reports_dir / "latest.md").read_text(encoding="utf-8")
        self.assertIn("反馈回看", report)
        self.assertIn("职责分层", report)
        self.assertNotIn("0 条相关问题", report)

    def test_second_run_promotes_interest(self):
        first_event = self._collect("如何把本地 Docker 数据库迁移到 Supabase？", NOW - timedelta(hours=2))
        first = run_analysis(self.paths, config=self.config, now=NOW)
        self.assertEqual(first["status"], "completed")
        discovery = list_discoveries(self.paths, status="observing")[0]
        topic_name = discovery["topic_name"]
        self.assertTrue(topic_name)

        self._collect(f"{topic_name} 还有更稳的做法吗？", NOW + timedelta(hours=2))
        second = run_analysis(self.paths, config=self.config, now=NOW + timedelta(days=1))

        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["feedback"]["promoted"], [discovery["discovery_id"]])
        self.assertEqual(len(list_discoveries(self.paths, status="promoted")), 1)
        topic = list_topics(self.paths)[0]
        self.assertEqual(len(topic["interests"]), 1)

    def test_scheduled_run_skips_when_not_due(self):
        run_analysis(self.paths, config=self.config, now=NOW)
        result = run_analysis(self.paths, config=self.config, now=NOW + timedelta(hours=1), scheduled=True)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "not_due")


if __name__ == "__main__":
    unittest.main()
