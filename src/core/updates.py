"""Check GitHub for a newer release of the application."""

import re

import requests

from core.logger import logger
from core.version import __version__

LATEST_RELEASE_API = "https://api.github.com/repos/DopeEx/EDAPGui/releases/latest"
LATEST_RELEASE_PAGE = "https://github.com/DopeEx/EDAPGui/releases/latest"


def parse_version(text: str) -> tuple[int, int, int] | None:
    """Parse 'v1.2.3', 'V1.2.3' or '1.2.3' into (1, 2, 3). Returns None if it is not a plain version."""
    match = re.fullmatch(r"[vV]?(\d+)\.(\d+)\.(\d+)", text.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_newer(latest: str, current: str = __version__) -> bool:
    """True if the version 'latest' is higher than 'current'. Unparsable versions are never newer."""
    latest_parts = parse_version(latest)
    current_parts = parse_version(current)
    if latest_parts is None or current_parts is None:
        return False
    return latest_parts > current_parts


def get_latest_release(timeout: float = 5.0) -> str | None:
    """Return the tag of the latest GitHub release, or None if there is none or it cannot be reached."""
    try:
        response = requests.get(LATEST_RELEASE_API, timeout=timeout, headers={"Accept": "application/vnd.github+json"})
        if response.status_code == 404:
            logger.debug("Update check: no release published yet.")
            return None
        response.raise_for_status()
        return response.json().get("tag_name")
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"Update check failed: {e}")
        return None
