"""All file and folder locations used by the application.

Paths are resolved relative to the project folder, so the working directory does not matter.
Files written at runtime live in USER_DATA, versioned reference files live in DATA."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# Versioned reference files (examples and defaults), copied to USER_DATA when missing
DATA = ROOT / 'data'
DATA_CONFIGS = DATA / 'configs'
WAYPOINT_EXAMPLES_DIR = DATA / 'waypoints'

# Read-only resources
LOCALES_DIR = ROOT / 'assets' / 'locales'
TEMPLATES_DIR = ROOT / 'assets' / 'templates'

# Runtime files, not versioned
USER_DATA = ROOT / 'user_data'
CONFIG_DIR = USER_DATA / 'configs'
AP_CONFIG = CONFIG_DIR / 'AP.json'
SHIP_CONFIGS = CONFIG_DIR / 'ship_configs.json'
RESOLUTION_CONFIG = CONFIG_DIR / 'resolution.json'
WAYPOINTS_DIR = USER_DATA / 'waypoints'
LOG_DIR = USER_DATA / 'logs'
LOG_FILE = LOG_DIR / 'autopilot.log'
DEBUG_DIR = USER_DATA / 'debug'


def _copy_missing(source_dir: Path, target_dir: Path) -> None:
    """ Copy files from source_dir to target_dir, never overwriting existing files. """
    if not source_dir.is_dir():
        return
    for source in source_dir.glob('*.json'):
        target = target_dir / source.name
        if not target.exists():
            shutil.copy2(source, target)


def ensure_user_data() -> None:
    """ Create the user data folders and seed them with the reference files if missing. """
    for folder in (CONFIG_DIR, WAYPOINTS_DIR, LOG_DIR, DEBUG_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    _copy_missing(DATA_CONFIGS, CONFIG_DIR)
    _copy_missing(WAYPOINT_EXAMPLES_DIR, WAYPOINTS_DIR)


def debug_path(*parts: str) -> str:
    """ Return a path below DEBUG_DIR for debug output, creating the parent folders. """
    target = DEBUG_DIR.joinpath(*parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    return str(target)


ensure_user_data()
