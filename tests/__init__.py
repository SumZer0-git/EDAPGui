"""Tests. Adds src/ to the import path so that the application packages can be imported."""

import os
import sys
import tempfile
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Keep test logs and diagnostics away from real user data and rotation.
os.environ.setdefault("EDAP_LOG_DIR", tempfile.mkdtemp(prefix="edap-test-logs-"))
os.environ.setdefault("EDAP_DEBUG_DIR", tempfile.mkdtemp(prefix="edap-test-debug-"))
