"""Helpers shared by the offline tests."""

import json
import os
import time
from pathlib import Path

import cv2

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture_image(folder: str):
    """Load the (single) screenshot from tests/fixtures/<folder> as a BGR image."""
    path = next((FIXTURES / folder).glob("*.png"))
    return cv2.imread(str(path))


class FakeScreen:
    """Stands in for vision.screen.Screen: every region grab returns the given image."""

    def __init__(self, image, width=3440, height=1440):
        self.image = image
        self.screen_width = width
        self.screen_height = height

    def get_screen_region(self, rect, rgb=True):
        return self.image


def write_json(path: Path, data) -> Path:
    """Write data as JSON, always giving the file a newer modification time than before."""
    previous = os.path.getmtime(path) if path.exists() else None
    path.write_text(json.dumps(data), encoding="utf-8")
    if previous is not None:
        newer = max(previous + 5, time.time())
        os.utime(path, (newer, newer))
    return path
