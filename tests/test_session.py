import contextlib
import io
import json
import os
import tempfile
import unittest
import argparse
from pathlib import Path

import support  # noqa: F401
from fomor import DEFAULT_CONFIG, DEFAULT_PROFILE, Home, cmd_session_start, cmd_status


def ns(**kwargs):
    return argparse.Namespace(**kwargs)


class SessionStartTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Home(Path(self.tmp.name) / "home")

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_layout_and_defaults_silently(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cmd_session_start(ns(home=str(self.home.root), verbose=False))
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue(), "")
        for path in (self.home.events_dir, self.home.reports_dir, self.home.runtime_dir):
            self.assertTrue(path.is_dir())
        self.assertEqual(self.home.config(), DEFAULT_CONFIG)
        self.assertEqual(self.home.profile(), DEFAULT_PROFILE)
        if os.name == "posix":  # chmod is a no-op on Windows
            self.assertEqual(self.home.root.stat().st_mode & 0o777, 0o700)

    def test_verbose_prints_report(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cmd_session_start(ns(home=str(self.home.root), verbose=True))
        report = json.loads(buffer.getvalue())
        self.assertTrue(report["ok"])
        self.assertFalse(report["existed"])

    def test_never_fails_on_unwritable_home(self):
        code = cmd_session_start(ns(home="///definitely/not/writable/xyz", verbose=False))
        self.assertEqual(code, 0)


class StatusTest(unittest.TestCase):
    def test_status_shows_new_fields_only(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = Home(Path(self.tmp.name) / "home")
        home.ensure()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cmd_status(ns(home=str(home.root)))
        text = buffer.getvalue()
        self.assertIn("events: 0", text)
        self.assertIn("dislikes: 0", text)
        self.assertIn("last_successful_analysis_at: never", text)
        self.assertIn("schedule: 03:00", text)
        self.assertNotIn("pending", text)
        self.assertNotIn("known", text)
        self.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
