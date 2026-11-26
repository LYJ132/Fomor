import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

import support  # noqa: F401
from fomor import Home, append_event, count_events, event_fingerprint, find_duplicate, normalize_hook_payload

NOW = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Home(Path(self.tmp.name) / "home")

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, prompt, session="s1"):
        return {"session_id": session, "prompt": prompt}

    def test_event_has_exactly_five_fields_no_processing_markers(self):
        event = normalize_hook_payload(self.payload("如何迁移数据库？"), NOW)
        self.assertEqual(
            sorted(event),
            ["event_id", "fingerprint", "session_id", "timestamp", "user_message"],
        )

    def test_creates_data_dir_on_first_hook(self):
        self.assertFalse(self.home.events_dir.exists())
        event, dup = append_event(self.home, self.payload("第一条消息"), NOW)
        self.assertIsNotNone(event)
        self.assertFalse(dup)
        self.assertTrue(self.home.events_dir.is_dir())
        self.assertTrue(self.home.config_file.exists())
        self.assertTrue(self.home.profile_file.exists())

    def test_blank_message_is_not_stored(self):
        event, dup = append_event(self.home, self.payload("   "), NOW)
        self.assertIsNone(event)
        self.assertFalse(dup)
        self.assertEqual(count_events(self.home), 0)

    def test_duplicate_within_same_session_is_skipped(self):
        _, first = append_event(self.home, self.payload("重复的问题"), NOW)
        _, second = append_event(self.home, self.payload("重复的问题"), NOW)
        self.assertFalse(first)
        self.assertTrue(second)
        self.assertEqual(count_events(self.home), 1)

    def test_same_prompt_in_other_session_is_kept(self):
        append_event(self.home, self.payload("同一句", "a"), NOW)
        append_event(self.home, self.payload("同一句", "b"), NOW)
        self.assertEqual(count_events(self.home), 2)

    def test_concurrent_hooks_do_not_lose_lines(self):
        threads = []
        for index in range(16):
            threads.append(
                threading.Thread(
                    target=append_event,
                    args=(self.home, self.payload(f"并发消息 {index}", f"s{index}"), NOW),
                )
            )
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(count_events(self.home), 16)
        for path in self.home.events_dir.glob("*.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                self.assertIsInstance(json.loads(line), dict)

    def test_invalid_json_line_is_ignored_not_fatal(self):
        path = self.home.events_dir / "2026-11-26.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("{broken json\n", encoding="utf-8")
        append_event(self.home, self.payload("正常消息"), NOW)
        self.assertEqual(count_events(self.home), 1)
        self.assertTrue(find_duplicate(self.home, event_fingerprint("s1", "正常消息")))


if __name__ == "__main__":
    unittest.main()
