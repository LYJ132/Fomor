import argparse
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import support  # noqa: F401
from fomor import Home, cmd_dislike, finish, prepare

NOW = datetime(2026, 11, 26, 3, 0, tzinfo=timezone.utc)


def ns(**kwargs):
    base = {"name": None, "category": "content_preference"}
    base.update(kwargs)
    return argparse.Namespace(**base)


class DislikeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Home(Path(self.tmp.name) / "home")
        self.home.ensure()

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_and_dedupe(self):
        self.assertEqual(cmd_dislike(ns(home=str(self.home.root), name="官方文档式推荐")), 0)
        self.assertEqual(cmd_dislike(ns(home=str(self.home.root), name="官方文档式推荐")), 0)
        profile = self.home.profile()
        self.assertEqual(len(profile["dislikes"]), 1)
        self.assertEqual(profile["dislikes"][0]["name"], "官方文档式推荐")
        self.assertEqual(profile["version"], 1)

    def test_requires_name(self):
        self.assertEqual(cmd_dislike(ns(home=str(self.home.root), name=None)), 1)

    def test_prepare_reads_dislikes(self):
        cmd_dislike(ns(home=str(self.home.root), name="工具清单式推送"))
        report = prepare(self.home, NOW)
        self.assertEqual(report["dislikes"][0]["name"], "工具清单式推送")

    def test_finish_does_not_touch_dislikes(self):
        cmd_dislike(ns(home=str(self.home.root), name="A"))
        path = self.home.events_dir / "2026-11-26.jsonl"
        path.write_text('{"event_id":"e1","user_message":"x"}\n', encoding="utf-8")
        report = prepare(self.home, NOW)
        finish(self.home, report["snapshot"], NOW)
        self.assertEqual(len(self.home.profile()["dislikes"]), 1)

    def test_old_known_data_is_dropped_on_migration(self):
        self.home.profile_file.write_text(
            json.dumps({"known": [{"name": "Docker", "at": "2026-01-01"}], "dislikes": [{"name": "新闻推送"}]}),
            encoding="utf-8",
        )
        profile = self.home.profile()
        self.assertEqual(profile["version"], 1)
        self.assertNotIn("known", profile)
        self.assertEqual([item["name"] for item in profile["dislikes"]], ["新闻推送"])
        on_disk = json.loads(self.home.profile_file.read_text(encoding="utf-8"))
        self.assertNotIn("known", on_disk)
        report = prepare(self.home, NOW)
        self.assertEqual(report["dislikes"], on_disk["dislikes"])


if __name__ == "__main__":
    unittest.main()
