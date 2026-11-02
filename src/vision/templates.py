"""Template images used with OpenCV to match in screen regions.

The templates are native screenshots in assets/templates/<height>p/ (for example 2160p). They are used unscaled
when the screen height matches. Otherwise the next larger set is scaled down (INTER_AREA), or, above the largest
set, the largest set is scaled up. The HUD scales with the screen height, so the scale factor is the ratio of
the screen height to the set height.
"""

from pathlib import Path

import cv2
import numpy as np

from core import paths

# Template name -> file name in a template folder
TEMPLATE_FILES = {
    "navpoint": "navpoint.png",
    "navpoint-behind": "navpoint-behind.png",
    "compass": "compass.png",
    "target": "destination.png",
    "target_occluded": "target_occluded.png",
}


def circle_center(image) -> tuple[float, float]:
    """Fit a circle to the white pixels of a template and return its center (x, y) in template pixels.
    The target template is only an arc of the circle, so the circle center is not the center of the image."""
    ys, xs = np.nonzero(image > 64)
    a = np.c_[2 * xs, 2 * ys, np.ones(len(xs))]
    b = xs**2 + ys**2
    cx, cy, _ = np.linalg.lstsq(a, b, rcond=None)[0]
    return float(cx), float(cy)


class ImageTemplates:
    def __init__(self, screen_height: int):
        self.screen_height = screen_height
        self.template = {name: {"image": None, "width": 1, "height": 1} for name in TEMPLATE_FILES}
        self.reload_templates()

    @staticmethod
    def complete_folder(height: int) -> Path | None:
        folder = paths.TEMPLATES_DIR / f"{height}p"
        if all((folder / file_name).is_file() for file_name in TEMPLATE_FILES.values()):
            return folder
        return None

    def source_set(self) -> tuple[Path, float]:
        """Folder of the template set to use and the scale factor for it: the exact set for the screen height,
        else the next larger set, else the largest set."""
        heights = sorted(
            int(folder.name[:-1])
            for folder in paths.TEMPLATES_DIR.glob("*p")
            if folder.name[:-1].isdigit() and self.complete_folder(int(folder.name[:-1])) is not None
        )
        if not heights:
            raise FileNotFoundError(f"No complete template set in {paths.TEMPLATES_DIR}")
        height = next((h for h in heights if h >= self.screen_height), heights[-1])
        return self.complete_folder(height), self.screen_height / height

    def read_template(self, path, scale=1.0):
        """Load a template in grey scale, optionally resize it, and return the image and size info."""
        template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if scale != 1.0:
            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            template = cv2.resize(template, (0, 0), fx=scale, fy=scale, interpolation=interpolation)
        width, height = template.shape[::-1]
        return {"image": template, "width": width, "height": height}

    def reload_templates(self):
        """Load the full set of image templates."""
        folder, scale = self.source_set()
        for name, file_name in TEMPLATE_FILES.items():
            self.template[name] = self.read_template(folder / file_name, scale)

        # Center of the target circle, the point that must be at the center of the screen when aligned
        self.template["target"]["anchor"] = circle_center(self.template["target"]["image"])
