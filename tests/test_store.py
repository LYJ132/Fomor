import support  # noqa: F401
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fomor.config import ensure_initialized
from fomor.paths import FomorPaths
from fomor.store import (
    append_event,
    cleanup_events,
    iter_events,
    list_topics,
    mark_events_analyzed,
    normalize_hook_payload,
    save_topic,
)
from fomor.utils import utcnow


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = FomorPaths(Path(self.tmp.name))
        self.config = ensure_initialized(self.paths)

    def tearDown(self):
        self.tmp.cleanup()

    def _payload(self, prompt: str, session: str = "s1") -> dict:
        return {"session_id": session, "prompt": prompt, "hook_event_name": "UserPromptSubmit"}

    def test_hook_payload_is_normalized(self):
        event = normalize_hook_payload(self._payload("如何迁移数据库？"))
        self.assertEqual(event["user_message"], "如何迁移数据库？")
        self.assertIsNone(event["analyzed_at"])
        self.assertTrue(event["fingerprint"])
        self.assertEqual(
            sorted(event),
            ["analyzed_at", "event_id", "fingerprint", "session_id", "timestamp", "user_message"],
        )

    def test_duplicate_prompt_is_skipped(self):
        event = normalize_hook_payload(self._payload("重复的问题"))
        _, first = append_event(self.paths, self.config, event)
        again = normalize_hook_payload(self._payload("重复的问题"))
        _, second = append_event(self.paths, self.config, again)
        self.assertFalse(first)
        self.assertTrue(second)
        self.assertEqual(len(list(iter_events(self.paths))), 1)

    def test_same_prompt_in_other_session_is_kept(self):
        append_event(self.paths, self.config, normalize_hook_payload(self._payload("同一句", "a")))
        append_event(self.paths, self.config, normalize_hook_payload(self._payload("同一句", "b")))
        self.assertEqual(len(list(iter_events(self.paths))), 2)

    def test_mark_analyzed_updates_only_targets(self):
        one = normalize_hook_payload(self._payload("问题一"))
        two = normalize_hook_payload(self._payload("问题二"))
        append_event(self.paths, self.config, one)
        append_event(self.paths, self.config, two)
        mark_events_analyzed(self.paths, [one], utcnow())
        by_id = {event["event_id"]: event for event in iter_events(self.paths)}
        self.assertIsNotNone(by_id[one["event_id"]]["analyzed_at"])
        self.assertIsNone(by_id[two["event_id"]]["analyzed_at"])

    def test_cleanup_removes_old_day_files(self):
        old = utcnow() - timedelta(days=self.config["retention"]["event_days"] + 2)
        append_event(self.paths, self.config, normalize_hook_payload(self._payload("旧问题"), now=old))
        append_event(self.paths, self.config, normalize_hook_payload(self._payload("新问题")))
        removed = cleanup_events(self.paths, self.config)
        self.assertEqual(removed, 1)
        messages = [event["user_message"] for event in iter_events(self.paths)]
        self.assertEqual(messages, ["新问题"])

    def test_created_directories_are_private(self):
        self.assertEqual(self.paths.root.stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
