import support  # noqa: F401
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fomor.config import ensure_initialized
from fomor.paths import FomorPaths
from fomor.scheduler import is_due, latest_cutoff, next_cutoff
from fomor.store import save_state
from fomor.utils import to_iso


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = FomorPaths(Path(self.tmp.name))
        self.config = ensure_initialized(self.paths)

    def tearDown(self):
        self.tmp.cleanup()

    def test_cutoff_is_previous_0300_when_before(self):
        # 2026-11-25 01:00 UTC == 09:00 Asia/Shanghai, already past 03:00.
        now = datetime(2026, 11, 25, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(latest_cutoff(now, self.config), datetime(2026, 11, 24, 19, 0, tzinfo=timezone.utc))

    def test_cutoff_rolls_back_before_0300(self):
        # 2026-11-24 18:00 UTC == 2026-11-25 02:00 Asia/Shanghai.
        now = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)
        self.assertEqual(latest_cutoff(now, self.config), datetime(2026, 11, 23, 19, 0, tzinfo=timezone.utc))

    def test_next_cutoff_is_one_day_later(self):
        now = datetime(2026, 11, 25, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(next_cutoff(now, self.config), datetime(2026, 11, 25, 19, 0, tzinfo=timezone.utc))

    def test_due_when_never_run(self):
        self.assertTrue(is_due(self.paths, self.config, datetime.now(timezone.utc)))

    def test_not_due_after_run_past_cutoff(self):
        now = datetime(2026, 11, 25, 1, 0, tzinfo=timezone.utc)
        save_state(self.paths, {"last_success_at": to_iso(datetime(2026, 11, 24, 20, 0, tzinfo=timezone.utc))})
        self.assertFalse(is_due(self.paths, self.config, now))

    def test_due_when_last_run_before_cutoff(self):
        now = datetime(2026, 11, 25, 1, 0, tzinfo=timezone.utc)
        save_state(self.paths, {"last_success_at": to_iso(datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc))})
        self.assertTrue(is_due(self.paths, self.config, now))


if __name__ == "__main__":
    unittest.main()
