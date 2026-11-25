import support  # noqa: F401
import tempfile
import unittest
from pathlib import Path

from fomor.config import DEFAULT_CONFIG, ensure_initialized
from fomor.paths import FomorPaths
from fomor.scheduler import verify_environment


class EnvironmentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = FomorPaths(Path(self.tmp.name) / "home")

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_home_is_created_silently(self):
        report = verify_environment(self.paths, DEFAULT_CONFIG)
        self.assertFalse(report["ok"] is False)
        self.assertIn("home", report["missing"])
        self.assertIn("workspace", report["missing"])
        self.assertTrue(self.paths.events_dir.is_dir())
        self.assertTrue(self.paths.reports_dir.is_dir())
        self.assertTrue(self.paths.settings_file.exists())
        self.assertEqual(self.paths.root.stat().st_mode & 0o777, 0o700)

    def test_initialized_environment_needs_no_repair(self):
        ensure_initialized(self.paths)
        report = verify_environment(self.paths, DEFAULT_CONFIG)
        self.assertTrue(report["ok"])
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["repaired"], [])
        self.assertEqual(report["dependencies"], [])


if __name__ == "__main__":
    unittest.main()
