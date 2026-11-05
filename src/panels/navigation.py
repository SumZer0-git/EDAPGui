"""Handles the navigation panel."""

from __future__ import annotations

import logging
from time import monotonic, sleep

import cv2
import numpy as np

from core.constants import GuiFocusExternalPanel
from core.logger import logger
from game.status import StatusParser
from i18n.localization import normalize_text
from panels.ship_control import COCKPIT_VIEW_TIMEOUT
from vision.regions import size_scale_for_station


class EDNavigationPanel:
    """The Navigation (Left hand) Ship Status Panel."""

    def __init__(self, ed_ap, screen, keys, cb):
        self.ap = ed_ap
        self.ocr = ed_ap.ocr
        self.screen = screen
        self.keys = keys
        self.ap_ckb = cb
        self.locale = self.ap.locale
        self.status_parser = StatusParser()

        self.navigation_tab_text = self.locale["NAV_PNL_TAB_NAVIGATION"]
        self.transactions_tab_text = self.locale["NAV_PNL_TAB_TRANSACTIONS"]
        self.contacts_tab_text = self.locale["NAV_PNL_TAB_CONTACTS"]
        self.target_tab_text = self.locale["NAV_PNL_TAB_TARGET"]
        self.nav_pnl_coords = None  # [top left, top right, bottom left, bottom right]

        # The rect is [L, T, R, B], top left x, y, and bottom right x, y in fraction of screen resolution
        # Nav Panel region covers the entire navigation panel.
        self.reg = {"nav_panel": {"rect": [0.11, 0.21, 0.70, 0.86]}, "temp_tab_bar": {"rect": [0.0, 0.2, 0.7, 0.35]}}
        self.sub_reg = {"tab_bar": {"rect": [0.0, 0.0, 1.0, 0.08]}, "location_panel": {"rect": [0.2218, 0.3, 0.8, 1.0]}}

        self.nav_pnl_tab_width = 260  # Nav panel tab width in pixels at 1920x1080
        self.nav_pnl_tab_height = 35  # Nav panel tab height in pixels at 1920x1080
        self.nav_pnl_location_width = 500  # Nav panel location width in pixels at 1920x1080
        self.nav_pnl_location_height = 35  # Nav panel location height in pixels at 1920x1080

    def request_docking_ocr(self) -> bool:
        """Try to request docking with OCR."""
        # res = self.show_contacts_tab()
        # if res is None:
        #     return None
        # if not res:
        #     print("Contacts Panel could not be opened")
        #     return False
        #
        # # On the CONTACT TAB, go to top selection, do this 4 seconds to ensure at top
        # # then go right, which will be "REQUEST DOCKING" and select it
        # self.keys.send("UI_Down")  # go down
        # self.keys.send('UI_Up', hold=2)  # got to top row
        # self.keys.send('UI_Right')
        # self.keys.send('UI_Select')
        # sleep(0.3)
        #
        # self.hide_nav_panel()
        # return True
        pass

    def _navigation_tab(self) -> bool:
        if not self.ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT):
            return False
        self.keys.send("HeadLookReset")
        self.keys.send("UIFocus", state=1)
        try:
            self.keys.send("UI_Left")
        finally:
            self.keys.send("UIFocus", state=0)
        for _ in range(5):
            sleep(0.4)
            focus = self.status_parser.get_gui_focus()
            if focus != GuiFocusExternalPanel:
                logger.debug("Navigation tab check: GUI focus=%s, external panel not ready.", focus)
                continue
            selected = self._selected_tab()
            logger.debug("Navigation tab check: selected=%r", selected)
            if selected == "navigation":
                return True
            self.keys.send("CycleNextPanel")
        logger.warning("Navigation tab could not be confirmed.")
        return False

    def _selected_tab(self) -> str | None:
        region = {"rect": [0.11, 0.21, 0.70, 0.30]}
        image = self.ocr.capture_region_pct(region)
        width, height = size_scale_for_station(35, 35, self.screen.screen_width, self.screen.screen_height)
        items = self.ocr.solid_highlighted_items(image, width, height)
        if len(items) != 1:
            logger.debug("Navigation tab highlight count=%s; no unique selected tab.", len(items))
            return None
        cropped, x, _y, w, h = items[0]
        center = region["rect"][0] + (x + w / 2) / self.screen.screen_width
        if 0.115 <= center <= 0.15 and 0.7 <= w / h <= 1.4:
            return "system"
        if cropped.shape[1] < width * 4:
            return None
        text = normalize_text(" ".join(self.ocr.image_simple_ocr(cropped) or []))
        logger.debug("Navigation selected-tab OCR: text=%r", text)
        for tab in ("navigation", "transactions", "contacts", "target"):
            titles = {
                normalize_text(value) for value in self.locale.all_values(f"NAV_PNL_TAB_{tab.upper()}") if value != "?"
            }
            if text in titles:
                return tab
        return None

    def _selected_destination(self) -> str:
        image = self.ocr.capture_region_pct({"rect": [0.11, 0.35, 0.70, 0.86]})
        width, height = size_scale_for_station(350, 25, self.screen.screen_width, self.screen.screen_height)
        items = self.ocr.solid_highlighted_items(image, width, height)
        if len(items) != 1:
            logger.debug("Navigation destination highlight count=%s; row not confirmed.", len(items))
            return ""
        name_image = self._destination_name_image(items[0][0])
        text = normalize_text(" ".join(self.ocr.image_simple_ocr(name_image) or []))
        logger.debug("Navigation destination-name OCR: name=%r", text)
        return text

    @staticmethod
    def _destination_name_image(row):
        """Isolate the name column of an already rectified highlighted destination."""
        height, width = row.shape[:2]
        # The highlight starts at the object icon, after the separate action-icon column.
        image = row[:, int(width * 0.04) : int(width * 0.86)].copy()
        background = np.median(image.reshape(-1, 3), axis=0).astype(np.uint8)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        markers = cv2.inRange(hsv, (35, 80, 40), (140, 255, 255))
        image[markers != 0] = background
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        background_gray = int(cv2.cvtColor(background.reshape(1, 1, 3), cv2.COLOR_BGR2GRAY)[0, 0])
        ink = cv2.inRange(gray, 0, max(0, background_gray - 35))
        count, labels, stats, _ = cv2.connectedComponentsWithStats(ink)
        for label in range(1, count):
            # Map pins and shields extend beyond the text line; do not OCR them as letters.
            if stats[label, cv2.CC_STAT_HEIGHT] > height * 0.65:
                image[labels == label] = background
        return image[int(height * 0.15) : int(height * 0.85)]

    def _next_destination(self, previous: str, deadline: float) -> str | None:
        self.keys.send("UI_Down")
        change_deadline = min(deadline, monotonic() + 2.5)
        stable_reads = 0
        while monotonic() < change_deadline:
            sleep(0.2)
            current = self._selected_destination()
            if current and current != previous:
                return current
            stable_reads = stable_reads + 1 if current == previous else 0
        # Only repeated readable, unchanged rows indicate the list boundary.
        return None if stable_reads >= 3 and change_deadline < deadline else ""

    def _lock_visible_destination(self, name: str, expected: str, deadline: float, attempt: int) -> bool:
        if not self._navigation_tab():
            return False
        self.keys.send("UI_Up", hold=4)
        sleep(0.5)
        current = self._selected_destination()
        seen = set()
        while current and current not in seen and len(seen) < 200 and monotonic() < deadline:
            seen.add(current)
            parsed_name = current
            logger.debug(
                "Station OCR scan: attempt=%s row=%s selected=%r parsed_name=%r expected=%r match=%s",
                attempt + 1,
                len(seen),
                current,
                parsed_name,
                expected,
                parsed_name == expected,
            )
            if parsed_name == expected:
                # Re-read before selection; never rely on a counted row position.
                reread = self._selected_destination()
                if reread != current:
                    logger.debug("Station OCR row changed before selection: previous=%r current=%r", current, reread)
                    return False
                self.keys.send("UI_Select")
                sleep(0.5)
                self.keys.send("UI_Select")
                if self.ap.wait_for_expected_in_system_target(name):
                    logger.debug("Station OCR target confirmed: target=%r attempt=%s", name, attempt + 1)
                    return True
                logger.warning("Station OCR selection did not confirm the requested target: %r", name)
                return False
            current = self._next_destination(current, deadline)
        logger.warning(
            "Station OCR did not find the requested destination: target=%r scan_complete=%s", name, current is None
        )
        logger.debug(
            "Station OCR scan stopped: rows=%s last_selection=%r deadline_reached=%s",
            len(seen),
            current,
            monotonic() >= deadline,
        )
        return False

    def lock_destination(self, name: str) -> bool:
        """Select the first exact name match and verify the selected game target."""
        expected = normalize_text(name)
        if not expected:
            logger.warning("Station OCR rejected an empty destination.")
            self.ap_ckb("log", "Enter a station name before selecting a navigation target.")
            return False
        if self.ap.has_expected_in_system_target(self.ap.status.get_cleaned_data(), name):
            return True
        deadline = monotonic() + 120
        for attempt in range(2):
            if monotonic() >= deadline:
                break
            try:
                confirmed = self._lock_visible_destination(name, expected, deadline, attempt)
            finally:
                cockpit_ready = self.ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT)
                self.keys.send("HeadLookReset")
            if confirmed and cockpit_ready:
                return True
            if not cockpit_ready:
                logger.warning("Station OCR could not return to the cockpit; stopping target selection.")
                break
            if monotonic() >= deadline:
                break
        self.ap_ckb(
            "log",
            f"Could not confirm station '{name}' in the Navigation panel. "
            "Check the name and navigation filters, or configure a station bookmark.",
        )
        return False

    def request_docking(self):
        """Request docking from Nav Panel."""
        self.keys.send("UI_Back", repeat=10)
        self.keys.send("HeadLookReset")
        self.keys.send("UIFocus", state=1)
        self.keys.send("UI_Left")
        self.keys.send("UIFocus", state=0)
        sleep(0.5)

        # Draw box around region
        abs_rect = self.screen.screen_rect_to_abs(self.reg["temp_tab_bar"]["rect"])
        if self.ap.debug_overlay:
            self.ap.overlay.overlay_rect1("nav_panel_active", abs_rect, (0, 255, 0), 2)
            self.ap.overlay.overlay_paint()

        tab_text = ""

        # Take screenshot of the panel
        image = self.ocr.capture_region_pct(self.reg["temp_tab_bar"])

        # Determine the nav panel tab size at this resolution
        scl_row_w, scl_row_h = size_scale_for_station(
            self.nav_pnl_tab_width, self.nav_pnl_tab_height, self.screen.screen_width, self.screen.screen_height
        )

        img_selected, ocr_textlist = self.ocr.get_highlighted_item_data(image, scl_row_w, scl_row_h)
        if img_selected is not None:
            logger.debug("is_nav_panel_active: image selected")
            logger.debug(f"is_nav_panel_active: OCR: {ocr_textlist}")

            # Overlay OCR result
            if self.ap.debug_overlay:
                self.ap.overlay.overlay_floating_text(
                    "nav_panel_text", f"{ocr_textlist}", abs_rect[0], abs_rect[1] - 25, (0, 255, 0)
                )
                self.ap.overlay.overlay_paint()

            # Test OCR string
            if self.navigation_tab_text in str(ocr_textlist):
                tab_text = self.navigation_tab_text
            if self.transactions_tab_text in str(ocr_textlist):
                tab_text = self.transactions_tab_text
            if self.contacts_tab_text in str(ocr_textlist):
                tab_text = self.contacts_tab_text
            if self.target_tab_text in str(ocr_textlist):
                tab_text = self.target_tab_text
        else:
            logger.debug("is_right_panel_active: no image selected")

        if tab_text == "":
            # we start with the Left Panel having "NAVIGATION" highlighted, we then need to right
            # twice to "CONTACTS".  Notice of a FSD run, the LEFT panel is reset to "NAVIGATION"
            # otherwise it is on the last tab you selected. Thus must start AP with "NAVIGATION" selected
            self.keys.send("CycleNextPanel", hold=0.2)
            sleep(0.2)
            self.keys.send("CycleNextPanel", hold=0.2)
        elif tab_text is self.navigation_tab_text:
            self.keys.send("CycleNextPanel", repeat=2)
        elif tab_text is self.transactions_tab_text:
            self.keys.send("CycleNextPanel", repeat=1)
        elif tab_text is self.contacts_tab_text:
            pass
        elif tab_text is self.target_tab_text:
            self.keys.send("CycleNextPanel", repeat=4)

        # On the CONTACT TAB, go to top selection, do this 4 seconds to ensure at top
        # then go right, which will be "REQUEST DOCKING" and select it
        self.keys.send("UI_Up", hold=4)
        self.keys.send("UI_Right")
        self.keys.send("UI_Select")

        sleep(0.5)
        # Go back to NAVIGATION tab
        self.keys.send("CycleNextPanel", hold=0.2)  # STATS tab
        sleep(0.2)
        self.keys.send("CycleNextPanel", hold=0.2)  # NAVIGATION tab

        # Clean up screen
        if self.ap.debug_overlay:
            sleep(2)
            self.ap.overlay.overlay_remove_rect("nav_panel_active")
            self.ap.overlay.overlay_remove_floating_text("nav_panel_text")
            self.ap.overlay.overlay_paint()

        sleep(0.3)
        self.keys.send("UI_Back")
        self.keys.send("HeadLookReset")

    def hide_nav_panel(self):
        """Hides the Nav Panel if open."""
        # Is nav panel active?
        if self.status_parser.get_gui_focus() == GuiFocusExternalPanel:
            self.ap.ship_control.goto_cockpit_view()


def dummy_cb(msg, body=None):
    pass


# Usage Example
if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)  # Default to log all debug when running this file.
    from core.autopilot import EDAutopilot

    ap = EDAutopilot(cb=dummy_cb)
    ap.keys.activate_window = True  # Helps with single steps testing

    from vision.screen import set_focus_elite_window

    set_focus_elite_window()
    nav_pnl = EDNavigationPanel(ap, ap.scr, ap.keys, dummy_cb)
    nav_pnl.request_docking()
