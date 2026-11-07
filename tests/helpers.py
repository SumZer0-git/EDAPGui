"""Helpers shared by the offline tests."""

import json
import os
import time
from pathlib import Path

import cv2
import numpy as np

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture_image(folder: str):
    """Load the (single) screenshot from tests/fixtures/<folder> as a BGR image."""
    path = next((FIXTURES / folder).glob("*.png"))
    return cv2.imread(str(path))


def pad_to_region(image, size=700):
    """The fixtures are tight crops; put them on a black canvas, so they are larger than every template."""
    height, width = image.shape[:2]
    return cv2.copyMakeBorder(
        image, 0, max(size - height, 0), 0, max(size - width, 0), cv2.BORDER_CONSTANT, value=(0, 0, 0)
    )


def load_screenshot(path):
    """Load a screenshot as a BGR image; also works for file names with umlauts."""
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


class FakeScreen:
    """Stands in for vision.screen.Screen: every region grab returns the given image."""

    def __init__(self, image, width=3440, height=1440):
        self.image = image
        self.screen_width = width
        self.screen_height = height

    def get_screen_region(self, rect, rgb=True):
        return self.image

    def get_screen_region_with_context(self, rect, rgb=True, scale=2.0):
        return self.image, self.image


class ScreenshotScreen:
    """Stands in for vision.screen.Screen with a full screenshot: region grabs return the cropped region the way
    mss does (BGRA), including the channel swap of the default rgb=True."""

    def __init__(self, image):
        self.image = image
        self.screen_height, self.screen_width = image.shape[:2]

    def get_screen_region(self, rect, rgb=True):
        left, top, right, bottom = (int(value) for value in rect)
        region = cv2.cvtColor(self.image[top:bottom, left:right], cv2.COLOR_BGR2BGRA)
        if rgb:
            region = cv2.cvtColor(region, cv2.COLOR_RGB2BGR)
        return region

    def get_screen_region_with_context(self, rect, rgb=True, scale=2.0):
        from vision.screen import Screen

        return Screen.get_screen_region_with_context(self, rect, rgb, scale)

    def get_screen(self, left, top, right, bottom, rgb=True):
        return self.get_screen_region((left, top, right, bottom), rgb)

    def screen_rect_to_abs(self, rect):
        return [
            int(rect[0] * self.screen_width),
            int(rect[1] * self.screen_height),
            int(rect[2] * self.screen_width),
            int(rect[3] * self.screen_height),
        ]

    def get_screen_rect_pct(self, rect):
        left, top, right, bottom = self.screen_rect_to_abs(rect)
        return self.image[top:bottom, left:right]


def write_json(path: Path, data) -> Path:
    """Write data as JSON, always giving the file a newer modification time than before."""
    previous = os.path.getmtime(path) if path.exists() else None
    path.write_text(json.dumps(data), encoding="utf-8")
    if previous is not None:
        newer = max(previous + 5, time.time())
        os.utime(path, (newer, newer))
    return path
