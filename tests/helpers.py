"""Helpers shared by the offline tests."""

import json
import os
import time
from pathlib import Path


def write_json(path: Path, data) -> Path:
    """ Write data as JSON, always giving the file a newer modification time than before. """
    previous = os.path.getmtime(path) if path.exists() else None
    path.write_text(json.dumps(data), encoding='utf-8')
    if previous is not None:
        newer = max(previous + 5, time.time())
        os.utime(path, (newer, newer))
    return path
