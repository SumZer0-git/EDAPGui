"""Handles the internal (right hand) ship status panel."""

from __future__ import annotations

import logging
from time import sleep

from core.constants import GuiFocusInternalPanel
from core.logger import logger
from game.status import StatusParser
from i18n.localization import normalize_text
from panels.ship_control import COCKPIT_VIEW_TIMEOUT
from panels.tab_navigation import confirm_panel_tab
from vision.diagnostics import save_case
from vision.regions import size_scale_for_station


class EDInternalStatusPanel:
    """The Internal (Right hand) Ship Status Panel."""

    def __init__(self, ed_ap, screen, keys, cb):
        self.ap = ed_ap
        self.ocr = ed_ap.ocr
        self.screen = screen
        self.keys = keys
        self.ap_ckb = cb
        self.locale = self.ap.locale
        self.status_parser = StatusParser()

        # The rect is [L, T, R, B] top left x, y, and bottom right x, y in fraction of screen resolution
        self.reg = {"right_panel": {"rect": [0.30, 0.20, 0.91, 0.28]}}

    def show_right_panel(self):
        """Shows the Internal (Right) Panel.
        Returns True if successful, else False.
        """
        logger.debug("show_right_panel: entered")

        # Is nav panel active?
        active, active_tab_name = self.is_right_panel_active()
        if active:
            return active, active_tab_name
        else:
            logger.debug("show_right_panel: Open Internal Panel")
            if not self.ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT):
                logger.warning("Could not return to the cockpit before opening the internal panel.")
                return False, ""

            self.keys.send("HeadLookReset")
            self.keys.send("UIFocus", state=1)
            try:
                self.keys.send("UI_Right")
            finally:
                self.keys.send("UIFocus", state=0)
            sleep(0.5)

            # Check if it opened
            active, active_tab_name = self.is_right_panel_active()
            if active:
                return active, active_tab_name
            else:
                return False, ""

    def show_inventory_tab(self) -> bool:
        """Open the internal panel and confirm Inventory before returning success."""
        logger.debug("show_inventory_tab: entered")

        if not self.ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT):
            logger.warning("Could not return to the cockpit before opening the internal panel.")
            return False
        self.keys.send("HeadLookReset")
        self.keys.send("UIFocus", state=1)
        try:
            self.keys.send("UI_Right")
        finally:
            self.keys.send("UIFocus", state=0)
        overlay_enabled = self.ap.debug_overlay
        if overlay_enabled:
            rect = self.screen.screen_rect_to_abs(self.reg["right_panel"]["rect"])
            self.ap.overlay.overlay_rect1("right_panel_active", rect, (0, 255, 0), 2)
            self.ap.overlay.overlay_paint()
        try:
            return confirm_panel_tab(
                self.status_parser, self.keys, self._selected_tab, GuiFocusInternalPanel, "inventory", "Internal panel"
            )
        finally:
            if overlay_enabled:
                self.ap.overlay.overlay_remove_rect("right_panel_active")
                self.ap.overlay.overlay_paint()

    def _tab_id(self, words) -> str:
        text = normalize_text(" ".join(words or []))
        for tab in ("modules", "fire_groups", "ship", "inventory", "storage", "status"):
            if text in {normalize_text(value) for value in self.locale.all_values(f"INT_PNL_TAB_{tab.upper()}")}:
                return tab
        return ""

    def _selected_tab(self) -> str:
        image = self.ocr.capture_region_pct(self.reg["right_panel"])
        width, height = size_scale_for_station(35, 30, self.screen.screen_width, self.screen.screen_height)
        items = self.ocr.solid_highlighted_items(image, width, height)
        if not items:
            items = self.ocr.solid_highlighted_items(image, width, height, remove_thin_lines=True)
        if len(items) != 1:
            logger.debug("Internal tab highlight count=%s; no unique selected tab.", len(items))
            self._save_tab_failure(image)
            return ""
        cropped, x, _y, w, h = items[0]
        center = self.reg["right_panel"]["rect"][0] + (x + w / 2) / self.screen.screen_width
        if 0.7 <= w / h <= 1.8:
            if 0.315 <= center <= 0.34:
                return "home"
            if 0.86 <= center <= 0.90:
                return "playlist"
        if cropped.shape[1] < width * 3:
            self._save_tab_failure(image)
            return ""
        words = self.ocr.image_simple_ocr(cropped)
        tab = self._tab_id(words)
        logger.debug("Internal selected-tab OCR: words=%r tab=%r", words, tab)
        if not tab:
            self._save_tab_failure(image)
        return tab

    def _save_tab_failure(self, image):
        if logger.isEnabledFor(logging.DEBUG):
            context = self.ocr.capture_region_pct({"rect": [0.30, 0.20, 1.0, 0.90]})
            save_case("internal-panel", "tab", {"evaluated": image, "later-panel": context})

    def is_right_panel_active(self) -> tuple[bool, str]:
        """Determine if the Nav Panel is open and if so, which tab is active.
        Returns True if active, False if not and also the string of the tab name.
        """
        logger.debug("is_right_panel_active: entered")

        # Check if nav panel is open
        if not self.status_parser.wait_for_gui_focus(GuiFocusInternalPanel, 3):
            logger.debug("is_right_panel_active: right panel not focused")
            return False, ""

        logger.debug("is_right_panel_active: right panel is focused")

        # Draw box around region
        abs_rect = self.screen.screen_rect_to_abs(self.reg["right_panel"]["rect"])
        if self.ap.debug_overlay:
            self.ap.overlay.overlay_rect1("right_panel_active", abs_rect, (0, 255, 0), 2)
            self.ap.overlay.overlay_paint()

        # Try this 'n' times before giving up
        tab_text = ""
        for i in range(10):
            tab_text = self._selected_tab()
            if tab_text:
                break

            # Wait and retry
            sleep(1)

        # Clean up screen
        if self.ap.debug_overlay:
            sleep(2)
            self.ap.overlay.overlay_remove_rect("right_panel_active")
            self.ap.overlay.overlay_remove_floating_text("right_panel_text")
            self.ap.overlay.overlay_paint()

        # Return Tab text or nothing
        if tab_text != "":
            return True, tab_text
        else:
            logger.warning("Internal panel selected tab could not be identified.")
            return False, ""

    def hide_right_panel(self):
        """Hides the Internal Panel if open."""
        # Is internal panel active?
        if self.status_parser.get_gui_focus() == GuiFocusInternalPanel:
            self.ap.ship_control.goto_cockpit_view()

    def transfer_to_fleetcarrier(self, ap):
        """Transfer all goods to Fleet Carrier"""
        self.ap_ckb("log+vce", "Executing transfer to Fleet Carrier.")
        logger.debug("transfer_to_fleetcarrier: entered")
        # Go to the internal (right) panel inventory tab
        if not self.show_inventory_tab():
            self.ap_ckb("log", "Could not confirm the inventory tab. Fleet Carrier transfer stopped.")
            return False

        # Assumes on the INVENTORY tab
        ap.keys.send("UI_Right")
        sleep(0.1)
        ap.keys.send("UI_Up")  # To FILTERS
        sleep(0.1)
        ap.keys.send("UI_Right")  # To TRANSFER >>
        sleep(0.1)
        ap.keys.send("UI_Select")  # Click TRANSFER >>
        sleep(0.1)
        ap.keys.send("UI_Up", hold=3)
        sleep(0.1)
        ap.keys.send("UI_Up")
        sleep(0.1)
        ap.keys.send("UI_Select")

        ap.keys.send("UI_Select")
        sleep(0.1)

        ap.keys.send("UI_Back", repeat=4)
        sleep(0.2)
        ap.keys.send("HeadLookReset")
        logger.debug("End of unload FC")
        return True
        # quit()

    def transfer_from_fleetcarrier(self, ap, buy_commodities):
        """Do not reinterpret commodity IDs as the obsolete unverified row-index transfer."""
        logger.warning("Fleet Carrier withdrawal requires confirmed commodity-to-inventory mapping.")
        self.ap_ckb("log", "ID-based Fleet Carrier withdrawals are not supported. No transfer inputs were sent.")
        return False


def dummy_cb(msg, body=None):
    pass


# Usage Example
if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)  # Default to log all debug when running this file.
    from core.autopilot import EDAutopilot

    ap = EDAutopilot(cb=dummy_cb)
    scr = ap.scr
    mykeys = ap.keys
    mykeys.activate_window = True  # Helps with single steps testing

    from vision.screen import set_focus_elite_window

    set_focus_elite_window()
    nav_pnl = EDInternalStatusPanel(ap, scr, mykeys, dummy_cb)
    nav_pnl.show_inventory_tab()
