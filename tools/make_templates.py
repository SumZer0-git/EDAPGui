"""Helper to create native-resolution template images from full-screen game screenshots.

The screenshots contain player information and must never be committed. Only the small, anonymous template crops
written by this tool belong into the repository.

Usage (run from the repository root):

    python tools/make_templates.py locate <screenshot> <template> [--scale-min 0.8 --scale-max 2.4]
    python tools/make_templates.py crop <screenshot> <name> <x> <y> <w> <h> --mode <mode> [--res 2160p]
        [--inpaint-center RADIUS]

`locate` searches for an existing template in a screenshot (using the same filter as the runtime detection)
and prints the best scale, score and rectangle. It also writes a preview image with the rectangle drawn in.
`crop` cuts a rectangle out of the screenshot losslessly, converts it with the given mode and stores it as
8-bit grayscale PNG in assets/templates/<res>/<name>.png.

Modes: orange2, occluded, blue_sco, white, tan (binary HSV filters used by the regions), h, s, v, gray (single channels).
The occluded target ring is white with HDR and beige (tan) without; the template is made from the white (HDR) ring.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "assets" / "templates"
PREVIEW_DIR = ROOT / "user_data" / "debug" / "templates"

# Keep in sync with the color ranges in src/vision/regions.py.
FILTERS = {
    "orange2": (np.array([16, 165, 220]), np.array([98, 255, 255])),
    "occluded": (np.array([16, 31, 85]), np.array([26, 160, 212])),
    "blue_sco": (np.array([10, 0, 0]), np.array([100, 150, 255])),
    "white": (np.array([0, 0, 215]), np.array([180, 40, 255])),
    "tan": (np.array([8, 40, 150]), np.array([30, 140, 255])),
}

# Template name -> (file, search region as fractions of the screen [L, T, R, B], conversion modes to try)
TEMPLATES = {
    "destination": ("destination.png", [0.33, 0.27, 0.66, 0.70], ["orange2"]),
    "target_occluded": ("target_occluded.png", [0.33, 0.27, 0.66, 0.70], ["white"]),
    "compass": ("compass.png", [0.33, 0.65, 0.46, 1.0], ["h", "s", "v"]),
    "navpoint": ("navpoint.png", [0.33, 0.65, 0.46, 1.0], ["h", "s", "v"]),
    "navpoint-behind": ("navpoint-behind.png", [0.33, 0.65, 0.46, 1.0], ["h", "s", "v"]),
}


def load_image(path: str | Path) -> np.ndarray:
    """Load an image as BGR. Reads via numpy so paths with umlauts work on Windows."""
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"Cannot read image: {path}")
    return img


def save_image(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise SystemExit(f"Cannot encode image: {path}")
    buf.tofile(str(path))


def convert(img_bgr: np.ndarray, mode: str) -> np.ndarray:
    """Convert a BGR image to the single-channel image that the runtime matches against."""
    if mode in FILTERS:
        lo, hi = FILTERS[mode]
        return cv2.inRange(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV), lo, hi)
    if mode == "gray":
        return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    if mode in ("h", "s", "v"):
        return cv2.split(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV))["hsv".index(mode)]
    raise SystemExit(f"Unknown mode: {mode}")


def cmd_locate(args) -> None:
    img = load_image(args.screenshot)
    h, w = img.shape[:2]
    file_name, region, modes = TEMPLATES[args.template]
    x0, y0, x1, y1 = int(region[0] * w), int(region[1] * h), int(region[2] * w), int(region[3] * h)
    crop = img[y0:y1, x0:x1]
    tpl = cv2.imdecode(np.fromfile(str(TEMPLATE_DIR / file_name), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)

    best = None
    for mode in modes:
        channel = convert(crop, mode)
        for scale in np.arange(args.scale_min, args.scale_max + 1e-9, args.step):
            scaled = cv2.resize(tpl, (0, 0), fx=float(scale), fy=float(scale), interpolation=cv2.INTER_AREA)
            if scaled.shape[0] > channel.shape[0] or scaled.shape[1] > channel.shape[1]:
                continue
            result = cv2.matchTemplate(channel, scaled, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(result)
            if best is None or score > best[0]:
                best = (float(score), float(scale), mode, loc, scaled.shape[::-1])

    if best is None:
        raise SystemExit("Template does not fit into the search region.")
    score, scale, mode, loc, (tw, th) = best
    rect = (loc[0] + x0, loc[1] + y0, tw, th)
    print(f"template={args.template} mode={mode} score={score:.3f} scale={scale:.2f} rect(x y w h)={rect}")

    preview = img.copy()
    cv2.rectangle(preview, (rect[0], rect[1]), (rect[0] + rect[2], rect[1] + rect[3]), (0, 255, 0), 3)
    pad = 60
    view = preview[max(rect[1] - pad, 0) : rect[1] + rect[3] + pad, max(rect[0] - pad, 0) : rect[0] + rect[2] + pad]
    out = PREVIEW_DIR / f"locate-{args.template}.png"
    save_image(out, view)
    print(f"preview: {out}")


def cmd_crop(args) -> None:
    img = load_image(args.screenshot)
    x, y, w, h = args.x, args.y, args.w, args.h
    if x < 0 or y < 0 or x + w > img.shape[1] or y + h > img.shape[0]:
        raise SystemExit(f"Rectangle outside the image ({img.shape[1]}x{img.shape[0]}).")
    # Convert the whole image first so filters see the same pixels as at runtime, then cut out.
    out_img = convert(img, args.mode)[y : y + h, x : x + w]
    if args.inpaint_center:
        # Remove the nav point from the compass center so the template matches any nav point position.
        mask = np.zeros(out_img.shape, np.uint8)
        cv2.circle(mask, (w // 2, h // 2), args.inpaint_center, 255, -1)
        out_img = cv2.inpaint(out_img, mask, 3, cv2.INPAINT_TELEA)
    if args.ring_mask:
        # Keep only an annulus around the center, so text and noise next to a circle stay out of the template.
        r_in, r_out = args.ring_mask
        yy, xx = np.ogrid[:h, :w]
        dist = np.hypot(xx - w / 2, yy - h / 2)
        out_img[(dist < r_in) | (dist > r_out)] = 0
    out = TEMPLATE_DIR / args.res / f"{args.name}.png"
    save_image(out, out_img)
    print(f"written: {out} ({w}x{h}, mode={args.mode})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    loc = sub.add_parser("locate", help="find an existing template in a screenshot")
    loc.add_argument("screenshot")
    loc.add_argument("template", choices=sorted(TEMPLATES))
    loc.add_argument("--scale-min", type=float, default=0.8)
    loc.add_argument("--scale-max", type=float, default=2.4)
    loc.add_argument("--step", type=float, default=0.02)
    loc.set_defaults(func=cmd_locate)

    crp = sub.add_parser("crop", help="cut a native template out of a screenshot")
    crp.add_argument("screenshot")
    crp.add_argument("name")
    for dim in ("x", "y", "w", "h"):
        crp.add_argument(dim, type=int)
    crp.add_argument("--mode", required=True, choices=sorted([*FILTERS, "h", "s", "v", "gray"]))
    crp.add_argument("--res", default="2160p")
    crp.add_argument("--inpaint-center", type=int, default=0, metavar="RADIUS")
    crp.add_argument("--ring-mask", type=int, nargs=2, metavar=("R_IN", "R_OUT"))
    crp.set_defaults(func=cmd_crop)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
