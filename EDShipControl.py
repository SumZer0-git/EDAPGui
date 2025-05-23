from __future__ import annotations

from EDAP_data import *
from OCR import OCR
from StatusParser import StatusParser


class EDShipControl:
    """ Handles ship control, FSD, SC, etc. """
    def __init__(self, screen, keys, cb):
        self.screen = screen
        self.ocr = OCR(screen)
        self.keys = keys
        self.status_parser = StatusParser()
        self.ap_ckb = cb

    def goto_cockpit_view(self) -> bool:
        """ Goto cockpit view.
        @return: True once complete.
        """
        if self.status_parser.get_gui_focus() == GuiFocusNoFocus:
            return True

        # Go down to cockpit view
        while not self.status_parser.get_gui_focus() == GuiFocusNoFocus:
            self.keys.send("UI_Back")  # make sure back in cockpit view

        return True
