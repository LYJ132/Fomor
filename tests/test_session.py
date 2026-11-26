import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401
from fomor import DEFAULT_CONFIG, Home, cmd_session_start, cmd_status
import argparse


def ns(**kwargs):
    return argparse.Namespace(**kwargs)


class SessionStartTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Home(Path(self.tmp.name) / "home")

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_layout_and_config_silently(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cmd_session_start(ns(home=str(self.home.root), verbose=False))
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue(), "")
        for path in (self.home.events_dir, self.home.topics_dir, self.home.discoveries_dir, self.home.reports_dir, self.home.runtime_dir):
            self.assertTrue(path.is_dir())
        self.assertEqual(self.home.config(), DEFAULT_CONFIG)
        self.assertEqual(self.home.root.stat().st_mode & 0o777, 0o700)

    def test_verbose_prints_report(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cmd_session_start(ns(home=str(self.home.root), verbose=True))
        report = json.loads(buffer.getvalue())
        self.assertTrue(report["ok"])
        self.assertFalse(report["existed"])

    def test_never_fails_on_bad_input(self):
        code = cmd_session_start(ns(home="///definitely/not/writable/xyz", verbose=False))
        self.assertEqual(code, 0)


class StatusTest(unittest.TestCase):
    def test_status_prints_counts_and_schedule(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = Home(Path(self.tmp.name) / "home")
        home.ensure()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cmd_status(ns(home=str(home.root)))
        text = buffer.getvalue()
        self.assertIn("events: 0", text)
        self.assertIn("schedule: 03:00", text)
        self.assertIn("last_analyzed_at: never", text)
        self.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
