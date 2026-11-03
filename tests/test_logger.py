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
        with tempfile.TemporaryDirectory() as log_dir:
            env = os.environ.copy()
            env["EDAP_LOG_DIR"] = log_dir
            script = (
                "import logging, sys\n"
                f"sys.path.insert(0, {str(project_root / 'src')!r})\n"
                "logging.getLogger().addHandler(logging.NullHandler())\n"
                "from core.logger import logger\n"
                "logger.setLevel(logging.DEBUG)\n"
                "logger.debug('file logger debug regression marker')\n"
                "logger.warning('file logger warning regression marker')\n"
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

        self.assertIn("file logger debug regression marker", log_contents)
        self.assertIn("file logger warning regression marker", log_contents)


if __name__ == "__main__":
    unittest.main()
