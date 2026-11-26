import io
import json
import tempfile
import unittest
import argparse
import contextlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import support  # noqa: F401
from fomor import EVENT_RETENTION_DAYS, PENDING_MAX_AGE_DAYS, Home, cmd_finish, cmd_learn, prepare
from fomor import to_iso

NOW = datetime(2026, 11, 26, 3, 0, tzinfo=timezone.utc)


def ns(**kwargs):
    return argparse.Namespace(**kwargs)


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Home(Path(self.tmp.name) / "home")
        self.home.ensure()

    def tearDown(self):
        self.tmp.cleanup()

    def collect(self, prompt, at, session="s1"):
        day = at.strftime("%Y-%m-%d")
        path = self.home.events_dir / f"{day}.jsonl"
        record = {
            "event_id": f"evt_{day}_{abs(hash(prompt)) % 99999}",
            "session_id": session,
            "timestamp": to_iso(at),
            "user_message": prompt,
            "fingerprint": f"fp_{abs(hash(prompt)) % 99999}",
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def test_window_filters_since_last_analyzed(self):
        old = self.collect("旧问题", NOW - timedelta(days=3))
        recent = self.collect("新问题", NOW - timedelta(hours=2))
        cmd_finish_ok(self.home, [{"id": "p1", "title": "t", "topic": "tt", "created_at": to_iso(NOW - timedelta(days=1))}])
        self.home.state_file.write_text(
            json.dumps({"last_analyzed_at": to_iso(NOW - timedelta(days=1)), "pending": []}),
            encoding="utf-8",
        )
        report = prepare(self.home, NOW)
        self.assertEqual([event["event_id"] for event in report["events"]], [recent["event_id"]])
        self.assertNotIn(old["event_id"], [event["event_id"] for event in report["events"]])

    def test_old_day_files_are_removed(self):
        self.collect("很久以前", NOW - timedelta(days=EVENT_RETENTION_DAYS + 2))
        self.collect("最近", NOW - timedelta(hours=1))
        report = prepare(self.home, NOW)
        removed = [name for name in report["event_files_removed"]]
        self.assertEqual(len(removed), 1)
        remaining = sorted(path.name for path in self.home.events_dir.glob("*.jsonl"))
        self.assertEqual(len(remaining), 1)

    def test_stale_pending_is_dropped(self):
        stale = {"id": "old", "title": "t", "topic": "tt", "created_at": to_iso(NOW - timedelta(days=PENDING_MAX_AGE_DAYS + 1))}
        fresh = {"id": "new", "title": "t", "topic": "tt", "created_at": to_iso(NOW - timedelta(hours=1))}
        cmd_finish_ok(self.home, [stale, fresh])
        report = prepare(self.home, NOW)
        self.assertEqual([item["id"] for item in report["pending"]], ["new"])
        self.assertEqual(report["pending_dropped"], 1)

    def test_profile_is_included(self):
        cmd_learn_ok(self.home, ["--known", "Docker", "--note", "已在用"])
        report = prepare(self.home, NOW)
        self.assertEqual(report["known"][0]["name"], "Docker")
        self.assertEqual(report["dislikes"], [])


def cmd_finish_ok(home, pending):
    import sys

    original = sys.stdin
    sys.stdin = io.StringIO(json.dumps({"pending": pending}))
    try:
        code = cmd_finish(ns(home=str(home.root)))
    finally:
        sys.stdin = original
    assert code == 0, "finish failed"


def cmd_learn_ok(home, flags):
    with contextlib.redirect_stdout(io.StringIO()):
        code = cmd_learn(ns(home=str(home.root), **dict(_learn_args(flags))))
    assert code == 0, f"learn failed: {flags}"


def _learn_args(flags):
    kwargs = {"note": ""}
    i = 0
    while i < len(flags):
        if flags[i] == "--known":
            kwargs["known"] = flags[i + 1]
            kwargs["dislike"] = None
            i += 2
        elif flags[i] == "--dislike":
            kwargs["dislike"] = flags[i + 1]
            kwargs["known"] = None
            i += 2
        elif flags[i] == "--note":
            kwargs["note"] = flags[i + 1]
            i += 2
        else:
            i += 1
    if "known" not in kwargs:
        kwargs["known"] = None
    if "dislike" not in kwargs:
        kwargs["dislike"] = None
    return kwargs


if __name__ == "__main__":
    unittest.main()
