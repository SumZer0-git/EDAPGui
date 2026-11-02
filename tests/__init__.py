"""Tests. Adds src/ to the import path so that the application packages can be imported."""

import os
import sys
import tempfile
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Keep the test logs out of user_data/logs, the logger rotates (and deletes) old log files on import
os.environ.setdefault("EDAP_LOG_DIR", tempfile.mkdtemp(prefix="edap-test-logs-"))
