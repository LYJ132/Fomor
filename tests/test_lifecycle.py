import io
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

import support  # noqa: F401
from fomor import Home, finish, prepare

NOW = datetime(2026, 11, 26, 3, 0, tzinfo=timezone.utc)


def write_events(home: Home, day: str, prompts, session="s1"):
    path = home.events_dir / f"{day}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for index, prompt in enumerate(prompts):
        record = {
            "event_id": f"evt_{day}_{index}",
            "session_id": session,
            "timestamp": f"{day}T0{index % 10}:00:00+00:00",
            "user_message": prompt,
            "fingerprint": f"fp_{day}_{index}",
        }
        records.append(record)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return records


class LifecycleTest(unittest.TestCase):
    """Event lifecycle: no processed markers; snapshot handover only."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Home(Path(self.tmp.name) / "home")
        self.home.ensure()

    def tearDown(self):
        self.tmp.cleanup()

    def test_prepare_reads_without_deleting_or_marking(self):
        write_events(self.home, "2026-11-26", ["问题一", "问题二"])
        report = prepare(self.home, NOW)
        self.assertEqual(report["event_count"], 2)
        self.assertEqual(report["snapshot"]["files"], {"2026-11-26.jsonl": 2})
        self.assertTrue((self.home.events_dir / "2026-11-26.jsonl").exists())
        raw = (self.home.events_dir / "2026-11-26.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("processed", raw)
        self.assertNotIn("analyzed", raw)

    def test_failed_analysis_keeps_events(self):
        write_events(self.home, "2026-11-26", ["问题一"])
        prepare(self.home, NOW)
        # Analysis failed: finish never called.
        self.assertEqual(len(list(self.home.events_dir.glob("*.jsonl"))), 1)
        report = prepare(self.home, NOW)  # next run still reads them
        self.assertEqual(report["event_count"], 1)

    def test_finish_deletes_fully_covered_files(self):
        write_events(self.home, "2026-11-25", ["昨天的问题"])
        write_events(self.home, "2026-11-26", ["今天的问题", "今天的问题二"])
        report = prepare(self.home, NOW)
        result = finish(self.home, report["snapshot"], NOW)
        self.assertEqual(result["deleted"], ["2026-11-25.jsonl", "2026-11-26.jsonl"])
        self.assertEqual(result["truncated"], [])
        self.assertEqual(list(self.home.events_dir.glob("*.jsonl")), [])
        state = self.home.state()
        self.assertEqual(state["last_successful_analysis_at"], NOW.isoformat())
        self.assertNotIn("pending", state)

    def test_finish_keeps_messages_added_during_analysis(self):
        write_events(self.home, "2026-11-26", ["已分析的消息"])
        report = prepare(self.home, NOW)
        # Hook appends while the agent is analyzing.
        write_events(self.home, "2026-11-26", ["分析期间新增"], session="s2")
        result = finish(self.home, report["snapshot"], NOW)
        self.assertEqual(result["truncated"], ["2026-11-26.jsonl"])
        remaining = list(self.home.events_dir.glob("*.jsonl"))
        self.assertEqual(len(remaining), 1)
        content = remaining[0].read_text(encoding="utf-8")
        self.assertNotIn("已分析的消息", content)
        self.assertIn("分析期间新增", content)
        next_report = prepare(self.home, NOW)
        self.assertEqual(next_report["event_count"], 1)

    def test_finish_refuses_mismatched_snapshot(self):
        write_events(self.home, "2026-11-26", ["问题一", "问题二"])
        report = prepare(self.home, NOW)
        path = self.home.events_dir / "2026-11-26.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")  # a line vanished
        with self.assertRaises(ValueError):
            finish(self.home, report["snapshot"], NOW)
        # Nothing was deleted.
        self.assertTrue(path.exists())

    def test_finish_refuses_missing_file_and_invalid_snapshot(self):
        write_events(self.home, "2026-11-26", ["问题一"])
        report = prepare(self.home, NOW)
        (self.home.events_dir / "2026-11-26.jsonl").unlink()
        with self.assertRaises(ValueError):
            finish(self.home, report["snapshot"], NOW)
        with self.assertRaises(ValueError):
            finish(self.home, {"version": 99, "cutoff": NOW.isoformat(), "files": {}}, NOW)
        with self.assertRaises(ValueError):
            finish(self.home, None, NOW)

    def test_finish_refuses_stale_snapshot(self):
        from datetime import timedelta

        write_events(self.home, "2026-11-20", ["旧问题"])
        report = prepare(self.home, NOW)
        with self.assertRaises(ValueError):
            finish(self.home, report["snapshot"], NOW + timedelta(hours=25))

    def test_repeated_finish_is_refused(self):
        write_events(self.home, "2026-11-26", ["问题一"])
        report = prepare(self.home, NOW)
        finish(self.home, report["snapshot"], NOW)
        with self.assertRaises(ValueError):
            finish(self.home, report["snapshot"], NOW)

    def test_missed_days_are_all_read(self):
        write_events(self.home, "2026-11-24", ["三天前"])
        write_events(self.home, "2026-11-25", ["两天前"])
        write_events(self.home, "2026-11-26", ["今天"])
        report = prepare(self.home, NOW)
        self.assertEqual(report["event_count"], 3)

    def test_old_pending_state_does_not_break_new_flow(self):
        self.home.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.home.state_file.write_text(
            json.dumps({"last_analyzed_at": "2026-11-25T03:00:00+00:00", "pending": [{"id": "x"}]}),
            encoding="utf-8",
        )
        write_events(self.home, "2026-11-26", ["新流程下的问题"])
        report = prepare(self.home, NOW)
        self.assertEqual(report["event_count"], 1)  # old pending ignored, all events read
        finish(self.home, report["snapshot"], NOW)
        self.assertNotIn("pending", self.home.state())

    def test_concurrent_prepare_and_hook(self):
        write_events(self.home, "2026-11-26", ["初始消息"])
        errors = []

        def hook_during_prepare():
            try:
                for index in range(5):
                    write_events(self.home, "2026-11-26", [f"并发新增{index}"], session=f"c{index}")
            except Exception as error:  # pragma: no cover
                errors.append(error)

        thread = threading.Thread(target=hook_during_prepare)
        thread.start()
        report = prepare(self.home, NOW)
        thread.join()
        self.assertEqual(errors, [])
        self.assertGreaterEqual(report["event_count"], 1)
        # Invariant: everything prepare read is gone after finish; everything
        # it did not read survives for the next run.
        read_ids = {event["event_id"] for event in report["events"]}
        finish(self.home, report["snapshot"], NOW)
        survivors = []
        for path in self.home.events_dir.glob("*.jsonl"):
            survivors.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        for event in survivors:
            self.assertNotIn(event["event_id"], read_ids)
        self.assertLessEqual(len(survivors), 5)


if __name__ == "__main__":
    unittest.main()
