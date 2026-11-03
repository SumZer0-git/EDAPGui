"""Locates the Elite Dangerous .binds files that are active in the game."""

from __future__ import annotations

import re
from os import environ
from pathlib import Path

GENERAL = "general"
SHIP = "ship"

# Lines of StartPreset.4.start, in the order of the controls menu: general, ship, SRV, on foot.
# Only the first two are used by EDAP.
START_PRESET_CATEGORIES = (GENERAL, SHIP)

_VERSION = re.compile(r"\.(\d+)\.(\d+)\.binds$")


def bindings_dir() -> Path:
    return Path(environ["LOCALAPPDATA"], "Frontier Developments", "Elite Dangerous", "Options", "Bindings")


def read_start_preset(folder: Path | None = None) -> list[str]:
    """Preset names from StartPreset.4.start (one per control category), or an empty list."""
    start_file = (folder or bindings_dir()) / "StartPreset.4.start"
    try:
        lines = start_file.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip()]


def resolve_preset(name: str, folder: Path | None = None) -> Path | None:
    """The .binds file of a preset; the highest version is used if there are several."""
    folder = folder or bindings_dir()
    candidates = []
    for path in folder.glob("*.binds"):
        match = _VERSION.search(path.name)
        if match and path.name[: match.start()] == name:
            candidates.append((int(match.group(1)), int(match.group(2)), path))
    if not candidates:
        return None
    return max(candidates)[2]


def active_binds_files(folder: Path | None = None) -> dict[str, Path]:
    """Maps the control categories used by EDAP to their active .binds file.

    A category is left out if its preset has no file, which is the case for the unmodified presets built into the
    game (for example AdvancedControlPad2)."""
    folder = folder or bindings_dir()
    files = {}
    for category, name in zip(START_PRESET_CATEGORIES, read_start_preset(folder)):
        path = resolve_preset(name, folder)
        if path is not None:
            files[category] = path
    return files


def preset_names(folder: Path | None = None) -> dict[str, str]:
    """Maps the control categories used by EDAP to the name of their active preset."""
    return dict(zip(START_PRESET_CATEGORIES, read_start_preset(folder)))
