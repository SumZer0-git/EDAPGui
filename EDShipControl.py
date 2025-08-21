from __future__ import annotations

from time import sleep
from EDAP_data import *
from OCR import OCR
from StatusParser import StatusParser


class EDShipControl:
    """ Handles ship control, FSD, SC, etc. """
    def __init__(self, ed_ap, screen, keys, cb):
        self.ap = ed_ap
        self.ocr = ed_ap.ocr
        self.screen = screen
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
        for _ in range(10):
            if self.status_parser.get_gui_focus() == GuiFocusNoFocus:
                break
            self.keys.send("UI_Back")
            sleep(0.3)

        if self.status_parser.get_gui_focus() != GuiFocusNoFocus:
            self.ap.internal_panel.show_home_tab()
            self.keys.send("UI_Select")
            sleep(0.3)
            self.keys.send("UI_Back")
            sleep(0.3)
            self.keys.send("UI_Back")
            sleep(0.3)
            self.keys.send("UI_Back")
            sleep(0.3)

        return self.status_parser.get_gui_focus() == GuiFocusNoFocus
