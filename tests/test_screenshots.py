"""Regression tests with real game screenshots.

The screenshots are not part of the repository. Put them in tests/fixtures/screenshots/<height>p/ named
NN_<scene>_<state>[_<language>].png (for example 2160p/12_target-occluded_moon.png); the tests skip when there are
none. The file names tell what is expected:
 - target-occluded / target-visible / aligned-target: the target ring is detected as occluded or not
 - compass / aligned-target: the compass is found
 - jump-align-msg: OCR recognizes the localized FSD alignment prompt in the HUD
 - disengage-msg: the message gate (message-colored area) lets the message region pass; the OCR is not run
 - no-msg: the message gate must not pass (guards against false alarms that trigger slow OCR runs)
 - station-services: OCR recognizes the localized header in each provided color scheme
 - galaxy-map: OCR recognizes the map header in each provided color scheme
 - trade-buy / trade-sell: the modal commodity and transaction direction match; background goods do not
 - nav-panel: the selected system/navigation/transactions/contacts tab is identified in both color schemes
 - internal-panel: the selected right-panel tab, including icon tabs, is identified in both color schemes
Screenshots whose names contain "crop" or "head-turned" are ignored.
"""

import unittest
from unittest import skipUnless
from unittest.mock import Mock, patch

import cv2
import numpy as np

from core import paths
from core.constants import GuiFocusGalaxyMap
from gui.cv_view import CvFrames
from i18n.localization import LocalizationManager
from panels.galaxy_map import EDGalaxyMap
from panels.internal_status import EDInternalStatusPanel
from panels.navigation import EDNavigationPanel
from panels.station_services import EDStationServicesInShip
from tests.helpers import FIXTURES, ScreenshotScreen, load_screenshot
from vision.detection import DetectionMixin
from vision.regions import ScreenRegions
from vision.templates import ImageTemplates

try:
    from vision.ocr import OCR
except ImportError:
    OCR = None

SCREENSHOTS = FIXTURES / "screenshots"
IGNORED = ("crop", "head-turned")
ALIGNMENT_SCREENSHOTS = tuple(sorted(SCREENSHOTS.glob("*p/*jump-align-msg*.png")))
STATION_SCREENSHOTS = tuple(sorted(SCREENSHOTS.glob("*p/*station-services*.png")))
TRADE_SCREENSHOTS = tuple(sorted(SCREENSHOTS.glob("*p/*trade-*.png")))
GALAXY_MAP_SCREENSHOTS = tuple(sorted(SCREENSHOTS.glob("*p/*galaxy-map*.png")))
NAV_PANEL_SCREENSHOTS = tuple(sorted(SCREENSHOTS.glob("*p/*nav-panel*.png")))
INTERNAL_PANEL_SCREENSHOTS = tuple(sorted(SCREENSHOTS.glob("*p/*internal-panel*.png")))


def screenshot_language(path):
    return "en" if "en" in path.stem.split("_") else "de"


def screenshot_ocr(path, engines):
    language = screenshot_language(path)
    if language not in engines:
        locale = LocalizationManager(str(paths.LOCALES_DIR), language)
        engines[language] = OCR(screen=None, language=locale.ocr_language)
    return engines[language]


@skipUnless(OCR is not None and NAV_PANEL_SCREENSHOTS, "PaddleOCR or local navigation-panel screenshots unavailable")
class NavigationPanelScreenshotTestCase(unittest.TestCase):
    def test_selected_tab_and_station_in_both_color_schemes(self):
        engines = {}
        for path in NAV_PANEL_SCREENSHOTS:
            with self.subTest(screenshot=path.name):
                ocr = screenshot_ocr(path, engines)
                screen = ScreenshotScreen(load_screenshot(path))
                ocr.screen = screen
                locale = LocalizationManager(str(paths.LOCALES_DIR), screenshot_language(path))
                with patch("panels.navigation.StatusParser"):
                    panel = EDNavigationPanel(Mock(ocr=ocr, locale=locale), screen, Mock(), Mock())
                expected = path.stem.split("_")[2]
                self.assertEqual(panel._selected_tab(), expected)
                if expected == "navigation" and "tab-only" not in path.stem.split("_"):
                    destination = "NAV BEACON" if "nav-beacon" in path.stem.split("_") else "OHM CITY"
                    self.assertEqual(panel._selected_destination(), destination)

    def test_long_name_and_numeric_suffix_survive_icons_and_noisy_distance_column(self):
        ocr = OCR(screen=None)
        name = "ORBITAL CONSTRUCTION SITE WINGROVES INHERITANCE ABC123"
        for background in ((255, 255, 255), (0, 255, 255)):
            with self.subTest(background=background):
                row = np.full((80, 1600, 3), background, dtype=np.uint8)
                cv2.putText(row, name, (90, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
                cv2.rectangle(row, (10, 5), (45, 70), (0, 0, 0), 3)
                cv2.rectangle(row, (1100, 5), (1125, 70), (0, 0, 0), 3)
                cv2.putText(row, "1187LS 0", (1400, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
                image = EDNavigationPanel._destination_name_image(row)
                self.assertEqual(" ".join(ocr.image_simple_ocr(image) or []), name)


@skipUnless(OCR is not None and INTERNAL_PANEL_SCREENSHOTS, "PaddleOCR or local internal-panel screenshots unavailable")
class InternalPanelScreenshotTestCase(unittest.TestCase):
    def test_selected_tab_in_both_color_schemes(self):
        engines = {}
        for path in INTERNAL_PANEL_SCREENSHOTS:
            with self.subTest(screenshot=path.name):
                ocr = screenshot_ocr(path, engines)
                screen = ScreenshotScreen(load_screenshot(path))
                ocr.screen = screen
                locale = LocalizationManager(str(paths.LOCALES_DIR), screenshot_language(path))
                with patch("panels.internal_status.StatusParser"):
                    panel = EDInternalStatusPanel(Mock(ocr=ocr, locale=locale), screen, Mock(), Mock())
                self.assertEqual(panel._selected_tab(), path.stem.split("_")[2].replace("-", "_"))


class NoOcr:
    def image_simple_ocr(self, image):
        return None


class Detector(DetectionMixin):
    def __init__(self):
        self.cv_frames = CvFrames()

    ocr = NoOcr()


def screenshots():
    for path in sorted(SCREENSHOTS.glob("*p/*.png")):
        if not any(word in path.name for word in IGNORED):
            yield path


@unittest.skipUnless(any(screenshots()), "no local screenshots in tests/fixtures/screenshots")
class ScreenshotTestCase(unittest.TestCase):
    def test_screenshots(self):
        templates = {}
        for path in screenshots():
            image = load_screenshot(path)
            height = image.shape[0]
            self.assertEqual(f"{height}p", path.parent.name, f"{path.name} is in the wrong folder")
            if height not in templates:
                templates[height] = ImageTemplates(height)
            regions = ScreenRegions(ScreenshotScreen(image), templates[height])
            detector = Detector()
            name = path.name

            with self.subTest(screenshot=f"{path.parent.name}/{name}"):
                self.assertEqual(
                    detector.is_destination_occluded(regions),
                    "target-occluded" in name,
                    "occluded target",
                )
                if "compass" in name or "aligned-target" in name:
                    self.assertTrue(detector.have_destination(regions), "compass")
                if "compass-behind" in name:
                    self.assertEqual(detector.get_nav_offset(regions)["z"], -1.0, "nav point behind")
                if "type9" in name and "compass" in name:
                    _, (_, score, _, _), scale = regions.match_compass_multiscale()
                    self.assertGreater(scale, 1.1, "larger compass sphere of the Type-9")
                    if "compass-behind-on-rim" in name or "aligned-target" in name or "compass-ahead" in name:
                        self.assertGreater(score, 0.75, "compass match")
                if "compass-behind-on-rim" in name:
                    offset = detector.get_nav_offset(regions)
                    self.assertGreater(max(abs(offset["x"]), abs(offset["y"])), 0.5, "nav point at the sphere rim")
                if "compass-ahead" in name:
                    self.assertEqual(detector.get_nav_offset(regions)["z"], 1.0, "nav point ahead")
                if "aligned-target_compass-ahead_type9" in name:
                    self.assertLess(abs(detector.get_nav_offset(regions)["pit"]), 6, "centered nav point")
                if "compass-ahead-off-target" in name:
                    self.assertGreater(detector.get_nav_offset(regions)["pit"], 10, "nav point above the center")
                # The message gate is only a cheap pre-check (bright scenes may pass it, the OCR decides)
                if "disengage-msg" in name:
                    self.assertTrue(regions.message_text_present(), "disengage message")
                if "no-msg" in name:
                    self.assertFalse(regions.message_text_present(), "false message alarm")


@skipUnless(OCR is not None and ALIGNMENT_SCREENSHOTS, "PaddleOCR or local FSD alignment screenshots unavailable")
class FsdAlignmentPromptScreenshotTestCase(unittest.TestCase):
    def test_alignment_prompt_is_read_in_all_local_screenshots(self):
        templates = ImageTemplates(2160)
        detector = Detector()
        engines = {}

        for path in ALIGNMENT_SCREENSHOTS:
            with self.subTest(screenshot=path.name):
                detector.locale = LocalizationManager(str(paths.LOCALES_DIR), screenshot_language(path))
                detector.ocr = screenshot_ocr(path, engines)
                image = load_screenshot(path)
                regions = ScreenRegions(ScreenshotScreen(image), templates)
                self.assertTrue(detector.fsd_alignment_prompt(regions))


@skipUnless(OCR is not None and STATION_SCREENSHOTS, "PaddleOCR or local station-services screenshots unavailable")
class StationServicesScreenshotTestCase(unittest.TestCase):
    def test_station_header_is_recognized_in_all_color_schemes(self):
        engines = {}
        for path in STATION_SCREENSHOTS:
            with self.subTest(screenshot=path.name):
                ocr = screenshot_ocr(path, engines)
                screen = ScreenshotScreen(load_screenshot(path))
                ocr.screen = screen
                services = EDStationServicesInShip.__new__(EDStationServicesInShip)
                services.ap = Mock(debug_overlay=False)
                services.keys = Mock()
                services.ap_ckb = Mock()
                services.screen = screen
                services.ocr = ocr
                services.locale = LocalizationManager(str(paths.LOCALES_DIR), screenshot_language(path))
                services.reg = {"connected_to": {"rect": [0.0, 0.0, 0.25, 0.25]}}
                # One real OCR poll is sufficient for a fully rendered static screenshot.
                wait = ocr.wait_for_text
                with patch.object(
                    ocr, "wait_for_text", side_effect=lambda ap, texts, region: wait(ap, texts, region, timeout=0.01)
                ):
                    self.assertTrue(services.goto_station_services())
                    services.ap_ckb.assert_not_called()


@skipUnless(OCR is not None and GALAXY_MAP_SCREENSHOTS, "PaddleOCR or local galaxy-map screenshots unavailable")
class GalaxyMapScreenshotTestCase(unittest.TestCase):
    def test_map_opening_header_is_recognized_on_first_poll_in_both_colors(self):
        ocr = OCR(screen=None)
        for path in GALAXY_MAP_SCREENSHOTS:
            with self.subTest(screenshot=path.name):
                screen = ScreenshotScreen(load_screenshot(path))
                ocr.screen = screen
                galaxy = EDGalaxyMap.__new__(EDGalaxyMap)
                galaxy.ap = Mock(debug_overlay=False)
                galaxy.ap.ship_control = Mock()
                galaxy.keys = Mock()
                galaxy.screen = screen
                galaxy.ocr = ocr
                galaxy.status_parser = Mock()
                galaxy.status_parser.get_gui_focus.return_value = GuiFocusGalaxyMap - 1
                galaxy.reg = {"cartographics": {"rect": [0.0, 0.0, 0.25, 0.25]}}
                wait = ocr.wait_for_text

                def recognize_once(ap, texts, region):
                    result = wait(ap, texts, region, timeout=0.01)
                    self.assertTrue(result, "map header must be recognized, not just time out")
                    return result

                with (
                    patch.object(
                        ocr,
                        "wait_for_text",
                        side_effect=recognize_once,
                    ) as recognition,
                    patch.object(ocr, "is_text_in_region", wraps=ocr.is_text_in_region) as poll,
                ):
                    galaxy.goto_galaxy_map()
                recognition.assert_called_once()
                poll.assert_called_once()
                self.assertIn("UI_Up", [call.args[0] for call in galaxy.keys.send.call_args_list])


@skipUnless(OCR is not None and TRADE_SCREENSHOTS, "PaddleOCR or local trade-dialog screenshots unavailable")
class TradeDialogScreenshotTestCase(unittest.TestCase):
    def test_selected_commodity_and_direction_in_both_color_schemes(self):
        engines = {}
        for path in TRADE_SCREENSHOTS:
            with self.subTest(screenshot=path.name):
                ocr = screenshot_ocr(path, engines)
                services = EDStationServicesInShip.__new__(EDStationServicesInShip)
                services.locale = LocalizationManager(str(paths.LOCALES_DIR), screenshot_language(path))
                services.screen = ScreenshotScreen(load_screenshot(path))
                services.ocr = ocr
                ocr.screen = services.screen
                selling = "trade-sell" in path.name
                name = "Halbleiter" if "halbleiter" in path.name else "Polymere"
                self.assertTrue(services.trade_dialog_matches(name, selling))
                self.assertFalse(
                    services.trade_dialog_matches("Polymere" if name == "Halbleiter" else "Halbleiter", selling)
                )
                self.assertFalse(services.trade_dialog_matches(name, not selling))

        for path in STATION_SCREENSHOTS:
            with self.subTest(no_trade_dialog=path.name):
                ocr = screenshot_ocr(path, engines)
                services.ocr = ocr
                services.locale = LocalizationManager(str(paths.LOCALES_DIR), screenshot_language(path))
                services.screen = ScreenshotScreen(load_screenshot(path))
                ocr.screen = services.screen
                self.assertFalse(services.trade_dialog_matches("Polymere", False))
                self.assertFalse(services.trade_dialog_matches("Polymere", True))


if __name__ == "__main__":
    unittest.main()
