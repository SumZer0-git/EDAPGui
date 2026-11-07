"""Debug-only, bounded storage for vision recognition cases."""

import logging
import os
import re
import threading
from datetime import datetime
from uuid import uuid4

import cv2

from core import paths
from core.logger import logger

CASE_LIMIT = 50
_lock = threading.Lock()
_case_file = re.compile(r"^(\d{8}-\d{6}-\d{6}-[0-9a-f]{32})_([A-Za-z0-9-]+)\.png$")


def save_case(category: str, reason: str, images: dict[str, object]) -> None:
    """Save images as one case and rotate only cases created by this recorder."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    if not category.isascii() or not reason.isascii():
        raise ValueError("Invalid vision diagnostic category or reason")
    if not category.replace("-", "").isalnum() or not reason.replace("-", "").isalnum():
        raise ValueError("Invalid vision diagnostic category or reason")
    if not images or any(not name.isascii() or not name.replace("-", "").isalnum() for name in images):
        raise ValueError("Invalid vision diagnostic images")
    root = paths.DEBUG_DIR / category
    case = f"{datetime.now():%Y%m%d-%H%M%S-%f}-{uuid4().hex}"
    with _lock:
        written = []
        try:
            root.mkdir(parents=True, exist_ok=True)
            for name, image in images.items():
                filename = root / f"{case}_{name}.png"
                written.append(filename)
                if not cv2.imwrite(str(filename), image):
                    raise OSError(f"Could not write {filename}")
        except (OSError, cv2.error) as error:
            logger.warning("Could not save vision diagnostic case %s: %s", root / case, error)
            for filename in written:
                try:
                    filename.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    logger.warning("Could not remove incomplete diagnostic image %s: %s", filename, cleanup_error)
            return
        try:
            prefix = os.path.relpath(root / case, paths.ROOT)
        except ValueError:
            # A debug-directory override on another drive has no program-root-relative path.
            prefix = os.path.relpath(root / case, paths.DEBUG_DIR)
        logger.debug(
            "Vision diagnostic case: category=%s reason=%s prefix=%s", category, reason, prefix.replace("\\", "/")
        )
        try:
            cases = {}
            for filename in root.iterdir():
                match = _case_file.fullmatch(filename.name)
                if match and filename.is_file():
                    cases.setdefault(match.group(1), []).append(filename)
            for old in sorted(cases)[:-CASE_LIMIT]:
                for filename in cases[old]:
                    filename.unlink()
        except OSError as error:
            logger.warning("Could not rotate vision diagnostic cases in %s: %s", root, error)
