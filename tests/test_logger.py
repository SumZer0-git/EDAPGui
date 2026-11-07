"""Tests for application logging setup."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class LoggerTestCase(unittest.TestCase):
    def test_file_logging_works_with_existing_root_handlers(self):
        project_root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as log_dir, tempfile.TemporaryDirectory() as debug_dir:
            env = os.environ.copy()
            env["EDAP_LOG_DIR"] = log_dir
            env["EDAP_DEBUG_DIR"] = debug_dir
            (Path(log_dir) / "autopilot.log").write_text("previous normal", encoding="utf-8")
            (Path(debug_dir) / "debug.log").write_text("previous debug", encoding="utf-8")
            script = (
                "import logging, sys\n"
                f"sys.path.insert(0, {str(project_root / 'src')!r})\n"
                "logging.getLogger().addHandler(logging.NullHandler())\n"
                "from core.logger import logger, set_log_level\n"
                "set_log_level(logging.DEBUG)\n"
                "logger.debug('file logger debug regression marker')\n"
                "logger.warning('file logger warning regression marker')\n"
                "set_log_level(logging.INFO)\n"
                "logger.info('after debug marker')\n"
                "for handler in logging.getLogger().handlers + logger.handlers:\n"
                "    handler.flush()\n"
            )
            subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                cwd=project_root,
                env=env,
                capture_output=True,
                text=True,
            )

            log_contents = (Path(log_dir) / "autopilot.log").read_text(encoding="utf-8")
            debug_contents = (Path(debug_dir) / "debug.log").read_text(encoding="utf-8")
            self.assertEqual(len(list(Path(log_dir).glob("autopilot *.log"))), 1)
            self.assertEqual(len(list(Path(debug_dir).glob("debug *.log"))), 1)
            self.assertFalse(list(Path(log_dir).glob("debug*.log")))

        self.assertNotIn("file logger debug regression marker", log_contents)
        self.assertIn("file logger warning regression marker", log_contents)
        self.assertIn("file logger debug regression marker", debug_contents)
        self.assertIn("file logger warning regression marker", debug_contents)
        self.assertNotIn("after debug marker", debug_contents)
        self.assertIn("after debug marker", log_contents)

    def test_debug_file_is_not_created_until_debug_is_enabled(self):
        project_root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as log_dir, tempfile.TemporaryDirectory() as debug_dir:
            env = os.environ.copy()
            env["EDAP_LOG_DIR"] = log_dir
            env["EDAP_DEBUG_DIR"] = debug_dir
            script = (
                "import logging, sys\n"
                f"sys.path.insert(0, {str(project_root / 'src')!r})\n"
                "from core.logger import logger, set_log_level\n"
                "set_log_level(logging.INFO, 'at startup')\n"
                "logger.info('normal marker')\n"
            )
            subprocess.run([sys.executable, "-c", script], check=True, cwd=project_root, env=env)
            self.assertFalse((Path(debug_dir) / "debug.log").exists())


if __name__ == "__main__":
    unittest.main()
