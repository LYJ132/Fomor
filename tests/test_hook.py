import support  # noqa: F401
import json
import tempfile
import unittest
from pathlib import Path

from fomor import Home, append_event, count_events, find_duplicate, normalize_hook_payload


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Home(Path(self.tmp.name) / "home")
        self.home.ensure()

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, prompt, session="s1"):
        return {"session_id": session, "prompt": prompt}

    def test_event_has_exactly_five_fields(self):
        event = normalize_hook_payload(self.payload("如何迁移数据库？"))
        self.assertEqual(
            sorted(event),
            ["event_id", "fingerprint", "session_id", "timestamp", "user_message"],
        )
        self.assertEqual(event["user_message"], "如何迁移数据库？")

    def test_duplicate_within_window_is_skipped(self):
        _, first_dup = append_event(self.home, self.payload("重复的问题"))
        _, second_dup = append_event(self.home, self.payload("重复的问题"))
        self.assertFalse(first_dup)
        self.assertTrue(second_dup)
        self.assertEqual(count_events(self.home), 1)

    def test_same_prompt_in_other_session_is_kept(self):
        append_event(self.home, self.payload("同一句", "a"))
        append_event(self.home, self.payload("同一句", "b"))
        self.assertEqual(count_events(self.home), 2)

    def test_blank_prompt_is_not_stored(self):
        event, dup = append_event(self.home, self.payload("   "))
        self.assertIsNone(event)
        self.assertFalse(dup)
        self.assertEqual(count_events(self.home), 0)

    def test_fingerprint_ignores_whitespace_and_case(self):
        import fomor

        append_event(self.home, self.payload("  如何   迁移数据库？ "))
        stored = json.loads((self.home.events_dir / sorted(p.name for p in self.home.events_dir.glob("*.jsonl"))[0]).read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(stored["fingerprint"], fomor.event_fingerprint("s1", "如何 迁移数据库？"))
        self.assertTrue(find_duplicate(self.home, stored["fingerprint"]))


if __name__ == "__main__":
    unittest.main()
