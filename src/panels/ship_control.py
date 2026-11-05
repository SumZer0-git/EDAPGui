"""Handles ship control, FSD, SC, etc."""

from __future__ import annotations

from time import monotonic, sleep

from core.constants import GuiFocusNoFocus
from core.logger import logger
from game.status import StatusParser

COCKPIT_VIEW_TIMEOUT = 10.0


class EDShipControl:
    """Handles ship control, FSD, SC, etc."""

    def __init__(self, ed_ap, screen, keys, cb):
        self.ocr = ed_ap.ocr
        self.screen = screen
        self.keys = keys
        self.status_parser = StatusParser()
        self.ap_ckb = cb

    def goto_cockpit_view(self, timeout: float | None = None) -> bool:
        """Goto cockpit view.
        @return: True once complete.
        """
        deadline = monotonic() + timeout if timeout is not None else None
        while self.status_parser.get_gui_focus() != GuiFocusNoFocus:
            if deadline is not None and monotonic() >= deadline:
                logger.warning("Unable to return to cockpit view before timeout.")
                self.ap_ckb("log", "Could not return to cockpit view. Waypoint Assist stopped.")
                return False
            self.keys.send("UI_Back")  # make sure back in cockpit view
            if deadline is not None:
                sleep(0.1)

        return True
