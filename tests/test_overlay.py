"""Tests for rendering overlay contents without creating a Win32 window."""

import sys
import unittest
from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from PIL import ImageColor

from core.types import EdapInterruptError
from gui.fields import DEFAULT_OVERLAY_LINE_ORDER
from gui.overlay import _WM_DPICHANGED, Overlay, _load_font, _render_image
from gui.theme import BLUE, MUTED, ORANGE, PANEL, TEXT

# The slim CI has no PaddleOCR; these tests never run OCR, so a temporary stub lets core.autopilot import.
try:
    from vision.ocr import OCR  # noqa: F401

    _PADDLEOCR_STUBBED = False
except ImportError:
    sys.modules["paddleocr"] = SimpleNamespace(PaddleOCR=None)
    _PADDLEOCR_STUBBED = True

from core.autopilot import (  # noqa: E402
    EDAutopilot,
    _overlay_fuel_segments,
    _overlay_next_star_segments,
    _overlay_ship_status,
    _overlay_status_role,
    _set_overlay_config_defaults,
)

if _PADDLEOCR_STUBBED:
    # Other test modules must still see the missing PaddleOCR and skip their OCR tests.
    del sys.modules["paddleocr"]
    sys.modules.pop("vision.ocr", None)


def _make_route_overlay(route_data, ship_state):
    autopilot = EDAutopilot.__new__(EDAutopilot)
    autopilot.config = {
        "OverlayTextEnable": True,
        "OverlayShowMode": False,
        "OverlayShowStatus": False,
        "OverlayShowShip": False,
        "OverlayShowSystem": False,
        "OverlayShowJumps": True,
        "OverlayShowDistance": True,
    }
    autopilot.travel_assist_enabled = False
    autopilot.waypoint_assist_enabled = False
    autopilot.afk_combat_assist_enabled = False
    autopilot.dss_assist_enabled = False
    autopilot.ap_state = "Idle"
    autopilot.jn = SimpleNamespace(ship_state=lambda: ship_state)
    autopilot.nav_route = SimpleNamespace(get_nav_route_data=lambda: route_data)
    autopilot._overlay_route_active = False
    autopilot._overlay_route_signature = ()
    autopilot._overlay_route_systems = []
    autopilot._overlay_route_completed_at = None
    autopilot.overlay = Mock()
    return autopilot


class OverlayRenderingTests(unittest.TestCase):
    def test_overlay_defaults_match_current_settings(self):
        config = {"OverlayPositionUnit": "Percent"}

        _set_overlay_config_defaults(config)

        self.assertEqual(
            config,
            {
                "OverlayTextEnable": True,
                "OverlayTextXOffset": 1,
                "OverlayTextYOffset": 15,
                "OverlayTextFont": "Rajdhani",
                "OverlayTextFontSize": 14,
                "OverlayTextFontWeight": "Medium",
                "OverlayPositionAnchor": "Top left",
                "OverlayPositionUnit": "Percent",
                "OverlayPanelOpacity": 50,
                "OverlayShowMode": True,
                "OverlayShowStatus": True,
                "OverlayShowShip": True,
                "OverlayShowSystem": True,
                "OverlayShowJumps": True,
                "OverlayShowJumpsBar": True,
                "OverlayShowDistance": True,
                "OverlayShowDistanceBar": True,
                "OverlayShowDestination": True,
                "OverlayShowNextStar": True,
                "OverlayShowFuel": True,
                "OverlayLineOrder": list(DEFAULT_OVERLAY_LINE_ORDER),
            },
        )

    def test_legacy_overlay_config_without_unit_keeps_pixel_coordinates(self):
        config = {"OverlayTextXOffset": 50, "OverlayTextYOffset": 400}

        _set_overlay_config_defaults(config)

        self.assertEqual(config["OverlayPositionUnit"], "Pixels")
        self.assertEqual(config["OverlayTextXOffset"], 50)
        self.assertEqual(config["OverlayTextYOffset"], 400)

    def test_live_render_updates_the_window_with_and_without_jump_progress(self):
        for dpi in (96, 144):
            for progress in (None, 0.0, 0.5, 1.0):
                with self.subTest(dpi=dpi, progress=progress):
                    overlay = Overlay.__new__(Overlay)
                    overlay._lock = RLock()
                    overlay.hWindow = 1
                    overlay._lines = {}
                    overlay._text = {"jumps": [[("JUMPS: ", "label"), ("1 of 2", "value")], 0, 0]}
                    overlay._floating_text = {}
                    overlay._font_name = "Rajdhani"
                    overlay._font_size = 14
                    overlay._font_weight = "Medium"
                    overlay._pos = (10, 10)
                    overlay._anchor = "Top left"
                    overlay._position_unit = "Pixels"
                    overlay._panel_opacity = 78
                    overlay._bars = {} if progress is None else {"jumps_bar": (progress, 1)}
                    overlay._target_position = (100, 200)
                    overlay._target_size = (1920, 1080)
                    overlay._move_overlay_window = Mock()
                    overlay._update_layered_window = Mock()

                    with (
                        patch("gui.overlay._user32.GetDpiForWindow", return_value=dpi),
                        patch("gui.overlay._render_image", wraps=_render_image) as render_image,
                    ):
                        overlay._render()

                    render_image.assert_called_once()
                    self.assertEqual(render_image.call_args.kwargs["bars"], overlay._bars)
                    overlay._move_overlay_window.assert_called_once_with()
                    overlay._update_layered_window.assert_called_once()
                    hwnd, image, x, y = overlay._update_layered_window.call_args.args
                    self.assertEqual(hwnd, 1)
                    self.assertEqual(image.mode, "RGBA")
                    self.assertEqual(image.size, overlay._size)
                    self.assertGreater(image.width, 1)
                    self.assertGreater(image.height, 1)
                    self.assertEqual(
                        (x, y),
                        (100 + overlay._surface_origin[0], 200 + overlay._surface_origin[1]),
                    )

    def test_statuses_use_only_known_semantic_color_roles(self):
        self.assertEqual(_overlay_status_role("Idle"), "muted")
        self.assertEqual(_overlay_status_role("Avoiding star"), "warning")
        self.assertEqual(_overlay_status_role("Docking Complete"), "success")
        self.assertEqual(_overlay_status_role("SC to Station: Jameson Memorial"), "active")
        self.assertEqual(_overlay_status_role("Unclassified state"), "value")

    def test_ship_status_keys_are_shown_as_readable_text(self):
        self.assertEqual(_overlay_ship_status("in_supercruise"), ("Supercruise", "value"))
        self.assertEqual(_overlay_ship_status("in_space"), ("Normal space", "value"))
        self.assertEqual(_overlay_ship_status("starting_hyperspace"), ("Hyperspace jump", "value"))
        self.assertEqual(_overlay_ship_status("in_station"), ("Docked", "success"))
        self.assertEqual(_overlay_ship_status("dockingdenied"), ("Docking denied", "warning"))
        self.assertEqual(_overlay_ship_status(None), ("Unknown", "muted"))
        self.assertEqual(_overlay_ship_status("starting_carrier_jump"), ("Starting carrier jump", "value"))

    def test_update_overlay_shows_readable_ship_status(self):
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.config = {
            "OverlayTextEnable": True,
            "OverlayShowMode": False,
            "OverlayShowStatus": False,
            "OverlayShowShip": True,
            "OverlayShowSystem": False,
            "OverlayShowJumps": False,
        }
        autopilot.travel_assist_enabled = False
        autopilot.waypoint_assist_enabled = False
        autopilot.afk_combat_assist_enabled = False
        autopilot.dss_assist_enabled = False
        autopilot.ap_state = "Idle"
        autopilot.jn = SimpleNamespace(
            ship_state=lambda: {"status": "in_supercruise", "star_class": "G", "location": "Sol"}
        )
        autopilot.overlay = Mock()

        autopilot.update_overlay()

        rendered = [call.args[1] for call in autopilot.overlay.overlay_text_segments.call_args_list]
        self.assertEqual(rendered, [[("SHIP STATUS: ", "label"), ("Supercruise", "value")]])

    def test_completed_route_progress_expires_after_one_minute(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "A", "SystemAddress": 1},
                {"StarSystem": "B", "SystemAddress": 2},
                {"StarSystem": "C", "SystemAddress": 3},
            ],
        }
        cleared = {"event": "NavRouteClear", "Route": []}
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.nav_route = SimpleNamespace(get_nav_route_data=Mock(side_effect=[route, cleared, cleared, cleared]))
        autopilot._overlay_route_active = False
        autopilot._overlay_route_signature = ()
        autopilot._overlay_route_systems = []
        autopilot._overlay_route_completed_at = None
        ship_state = {"location": "C", "system_address": 3}

        with patch("core.autopilot.monotonic", side_effect=(100.0, 110.0, 159.9, 160.0)):
            self.assertEqual(autopilot._get_overlay_route_progress(ship_state), ("complete", 2, 2))
            self.assertEqual(autopilot._get_overlay_route_progress(ship_state), ("complete", 2, 2))
            self.assertEqual(autopilot._get_overlay_route_progress(ship_state), ("complete", 2, 2))
            self.assertIsNone(autopilot._get_overlay_route_progress(ship_state))

    def test_route_progress_uses_system_address_and_supports_rejoining_elsewhere(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "A", "SystemAddress": 1},
                {"StarSystem": "B", "SystemAddress": 2},
                {"StarSystem": "C", "SystemAddress": 3},
                {"StarSystem": "D", "SystemAddress": 4},
            ],
        }
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.nav_route = SimpleNamespace(get_nav_route_data=Mock(return_value=route))
        autopilot._overlay_route_active = False
        autopilot._overlay_route_signature = ()
        autopilot._overlay_route_systems = []
        autopilot._overlay_route_completed_at = None

        self.assertEqual(
            autopilot._get_overlay_route_progress({"location": "C", "system_address": 3}),
            ("on_route", 2, 3),
        )
        self.assertEqual(
            autopilot._get_overlay_route_progress({"location": "B", "system_address": 2}),
            ("on_route", 1, 3),
        )
        self.assertEqual(
            autopilot._get_overlay_route_progress({"location": "D", "system_address": 99}),
            ("off_route", None, 3),
        )

    def test_route_distance_uses_coordinates_along_the_planned_route(self):
        route = [
            {"StarSystem": "A", "StarPos": [0, 0, 0]},
            {"StarSystem": "B", "StarPos": [3, 4, 0]},
            {"StarSystem": "C", "StarPos": [3, 4, 12]},
        ]

        self.assertEqual(EDAutopilot._get_overlay_route_distance(route, 0), (17.0, 17.0))
        self.assertEqual(EDAutopilot._get_overlay_route_distance(route, 1), (12.0, 17.0))
        self.assertEqual(EDAutopilot._get_overlay_route_distance(route, 2), (0, 17.0))
        self.assertIsNone(EDAutopilot._get_overlay_route_distance([route[0], {}], 0))

    def test_route_distance_overlay_is_independent_of_jump_count(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "A", "SystemAddress": 1, "StarPos": [0, 0, 0]},
                {"StarSystem": "B", "SystemAddress": 2, "StarPos": [3, 4, 0]},
                {"StarSystem": "C", "SystemAddress": 3, "StarPos": [3, 4, 12]},
            ],
        }
        autopilot = _make_route_overlay(
            route,
            {"status": "in_supercruise", "star_class": "G", "location": "B", "system_address": 2},
        )
        autopilot.config["OverlayShowJumps"] = False

        autopilot.update_overlay()

        autopilot.overlay.overlay_text_segments.assert_called_once_with(
            "distance",
            [("DISTANCE: ", "label"), ("5.0 of 17.0 ly", "value"), (" (12.0 left)", "muted")],
            0,
            0,
        )
        autopilot.overlay.overlay_remove_text.assert_any_call("jumps")
        autopilot.overlay.overlay_progress_bar.assert_not_called()

    def test_route_distance_is_preserved_when_game_clears_route_before_final_jump(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "A", "SystemAddress": 1, "StarPos": [0, 0, 0]},
                {"StarSystem": "B", "SystemAddress": 2, "StarPos": [3, 4, 0]},
                {"StarSystem": "C", "SystemAddress": 3, "StarPos": [3, 4, 12]},
            ],
        }
        autopilot = _make_route_overlay(
            route,
            {"status": "in_supercruise", "star_class": "G", "location": "B", "system_address": 2},
        )
        autopilot.nav_route.get_nav_route_data = Mock(side_effect=(route, {"event": "NavRouteClear", "Route": []}))

        autopilot.update_overlay()
        autopilot.update_overlay()

        autopilot.overlay.overlay_text_segments.assert_any_call(
            "distance",
            [("DISTANCE: ", "label"), ("5.0 of 17.0 ly", "value"), (" (12.0 left)", "muted")],
            1,
            0,
        )
        self.assertEqual(
            sum(call.args[0] == "distance" for call in autopilot.overlay.overlay_text_segments.call_args_list),
            1,
        )

    def test_destination_and_next_star_follow_the_route(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "A", "SystemAddress": 1, "StarClass": "G"},
                {"StarSystem": "B", "SystemAddress": 2, "StarClass": "K"},
                {"StarSystem": "C", "SystemAddress": 3, "StarClass": "D"},
            ],
        }
        autopilot = _make_route_overlay(
            route,
            {"status": "in_supercruise", "star_class": "G", "location": "A", "system_address": 1},
        )
        autopilot.config.update(
            OverlayShowJumps=False, OverlayShowDistance=False, OverlayShowDestination=True, OverlayShowNextStar=True
        )

        autopilot.update_overlay()

        self.assertEqual(
            [call.args[:3] for call in autopilot.overlay.overlay_text_segments.call_args_list],
            [
                ("destination", [("DESTINATION: ", "label"), ("C", "value")], 0),
                ("next_star", [("NEXT STAR: ", "label"), ("K", "value"), (" (scoopable)", "muted")], 1),
            ],
        )

    def test_next_star_warns_when_not_scoopable_after_final_jump_route_clear(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "A", "SystemAddress": 1, "StarClass": "G"},
                {"StarSystem": "B", "SystemAddress": 2, "StarClass": "K"},
                {"StarSystem": "C", "SystemAddress": 3, "StarClass": "D"},
            ],
        }
        autopilot = _make_route_overlay(
            route,
            {"status": "in_supercruise", "star_class": "K", "location": "B", "system_address": 2},
        )
        autopilot.config.update(OverlayShowJumps=False, OverlayShowDistance=False, OverlayShowNextStar=True)
        autopilot.nav_route.get_nav_route_data = Mock(side_effect=(route, {"event": "NavRouteClear", "Route": []}))

        autopilot.update_overlay()
        autopilot.update_overlay()

        autopilot.overlay.overlay_text_segments.assert_called_once_with(
            "next_star",
            [("NEXT STAR: ", "label"), ("D", "value"), (" (not scoopable)", "warning")],
            0,
            0,
        )

    def test_completed_route_shows_green_destination_without_next_star(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "A", "SystemAddress": 1, "StarClass": "G"},
                {"StarSystem": "B", "SystemAddress": 2},
            ],
        }
        autopilot = _make_route_overlay(
            route,
            {"status": "in_supercruise", "star_class": "G", "location": "B", "system_address": 2},
        )
        autopilot.config.update(
            OverlayShowJumps=False, OverlayShowDistance=False, OverlayShowDestination=True, OverlayShowNextStar=True
        )

        autopilot.update_overlay()

        autopilot.overlay.overlay_text_segments.assert_called_once_with(
            "destination", [("DESTINATION: ", "label"), ("B", "success")], 0, 0
        )
        autopilot.overlay.overlay_remove_text.assert_any_call("next_star")

    def test_next_star_without_star_class_is_unknown(self):
        self.assertEqual(_overlay_next_star_segments(None), [("NEXT STAR: ", "label"), ("Unknown", "muted")])

    def test_fuel_line_is_colored_against_refuel_and_abort_thresholds(self):
        cases = (
            (32, 32, False, [("FUEL: ", "label"), ("100 %", "value")]),
            (16, 32, False, [("FUEL: ", "label"), ("50 %", "warning")]),
            (16, 32, True, [("FUEL: ", "label"), ("50 %", "warning"), (" (scooping)", "active")]),
            (2, 32, False, [("FUEL: ", "label"), ("6 %", "error")]),
            (None, 32, False, [("FUEL: ", "label"), ("Unknown", "muted")]),
            (10, None, False, [("FUEL: ", "label"), ("Unknown", "muted")]),
        )
        for level, capacity, scooping, expected in cases:
            with self.subTest(level=level, capacity=capacity, scooping=scooping):
                self.assertEqual(_overlay_fuel_segments(level, capacity, scooping, 65, 10), expected)

    def test_fuel_line_prefers_live_status_and_falls_back_to_journal(self):
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.config = {"RefuelThreshold": 65, "FuelThreasholdAbortAP": 10}
        ship_state = {"fuel_level": 8, "fuel_capacity": 32, "is_scooping": False}
        autopilot._overlay_status = SimpleNamespace(get_cleaned_data=lambda: {"FuelMain": 24, "Flags": 1 << 11})

        self.assertEqual(
            autopilot._overlay_fuel_line(ship_state),
            [("FUEL: ", "label"), ("75 %", "value"), (" (scooping)", "active")],
        )

        autopilot._overlay_status = SimpleNamespace(get_cleaned_data=Mock(side_effect=OSError("missing")))
        self.assertEqual(autopilot._overlay_fuel_line(ship_state), [("FUEL: ", "label"), ("25 %", "warning")])

    def test_progress_bars_sit_below_their_lines_in_the_default_order(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "A", "SystemAddress": 1, "StarPos": [0, 0, 0]},
                {"StarSystem": "B", "SystemAddress": 2, "StarPos": [3, 4, 0]},
                {"StarSystem": "C", "SystemAddress": 3, "StarPos": [3, 4, 12]},
            ],
        }
        autopilot = _make_route_overlay(
            route,
            {"status": "in_supercruise", "star_class": "G", "location": "B", "system_address": 2},
        )
        autopilot.config.update(OverlayShowJumpsBar=True, OverlayShowDistanceBar=True)

        autopilot.update_overlay()

        texts = [call.args[::2] for call in autopilot.overlay.overlay_text_segments.call_args_list]
        self.assertEqual(texts, [("jumps", 0), ("distance", 2)])
        self.assertEqual(
            autopilot.overlay.overlay_progress_bar.call_args_list,
            [call("jumps_bar", 0.5, 1), call("distance_bar", 5 / 17, 3)],
        )

    def test_custom_line_order_moves_lines_and_bars(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "A", "SystemAddress": 1, "StarPos": [0, 0, 0]},
                {"StarSystem": "B", "SystemAddress": 2, "StarPos": [3, 4, 0]},
                {"StarSystem": "C", "SystemAddress": 3, "StarPos": [3, 4, 12]},
            ],
        }
        autopilot = _make_route_overlay(
            route,
            {"status": "in_supercruise", "star_class": "G", "location": "B", "system_address": 2},
        )
        autopilot.config.update(
            OverlayShowMode=True,
            OverlayShowDistanceBar=True,
            OverlayLineOrder=["distance_bar", "distance", "unknown", "mode"],
        )

        autopilot.update_overlay()

        autopilot.overlay.overlay_progress_bar.assert_called_once_with("distance_bar", 5 / 17, 0)
        self.assertEqual(
            [call.args[::2] for call in autopilot.overlay.overlay_text_segments.call_args_list],
            [("distance", 1), ("mode", 2), ("jumps", 3)],
        )

    def test_cleared_route_is_not_reported_complete_when_not_at_destination(self):
        route = {"event": "NavRoute", "Route": [{"StarSystem": "A"}, {"StarSystem": "B"}, {"StarSystem": "C"}]}
        cleared = {"event": "NavRouteClear", "Route": []}
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.nav_route = SimpleNamespace(get_nav_route_data=Mock(side_effect=[route, cleared]))
        autopilot._overlay_route_active = False
        autopilot._overlay_route_signature = ()
        autopilot._overlay_route_systems = []
        autopilot._overlay_route_completed_at = None

        self.assertEqual(
            autopilot._get_overlay_route_progress({"location": "A", "system_address": None}),
            ("on_route", 0, 2),
        )
        self.assertIsNone(autopilot._get_overlay_route_progress({"location": "A", "system_address": None}))

    def test_new_route_resets_completion_and_starts_at_current_system(self):
        old_route = {"event": "NavRoute", "Route": [{"StarSystem": "A"}, {"StarSystem": "B"}]}
        cleared = {"event": "NavRouteClear", "Route": []}
        new_route = {"event": "NavRoute", "Route": [{"StarSystem": "B"}, {"StarSystem": "C"}]}
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.nav_route = SimpleNamespace(get_nav_route_data=Mock(side_effect=[old_route, cleared, new_route]))
        autopilot._overlay_route_active = False
        autopilot._overlay_route_signature = ()
        autopilot._overlay_route_systems = []
        autopilot._overlay_route_completed_at = None

        self.assertEqual(
            autopilot._get_overlay_route_progress({"location": "B", "system_address": None}),
            ("complete", 1, 1),
        )
        self.assertEqual(
            autopilot._get_overlay_route_progress({"location": "B", "system_address": None}),
            ("complete", 1, 1),
        )
        self.assertEqual(
            autopilot._get_overlay_route_progress({"location": "B", "system_address": None}),
            ("on_route", 0, 1),
        )

    def test_route_cleared_during_final_jump_keeps_progress_until_arrival(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "A", "SystemAddress": 1},
                {"StarSystem": "B", "SystemAddress": 2},
                {"StarSystem": "C", "SystemAddress": 3},
            ],
        }
        cleared = {"event": "NavRouteClear", "Route": []}
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.nav_route = SimpleNamespace(get_nav_route_data=Mock(side_effect=[route, cleared, cleared, cleared]))
        autopilot._overlay_route_active = False
        autopilot._overlay_route_signature = ()
        autopilot._overlay_route_systems = []
        autopilot._overlay_route_completed_at = None

        self.assertEqual(
            autopilot._get_overlay_route_progress({"location": "B", "system_address": 2}), ("on_route", 1, 2)
        )
        # NavRouteClear arrives while the ship is still in the system before the destination.
        self.assertEqual(
            autopilot._get_overlay_route_progress({"location": "B", "system_address": 2}), ("on_route", 1, 2)
        )
        with patch("core.autopilot.monotonic", return_value=100.0):
            self.assertEqual(
                autopilot._get_overlay_route_progress({"location": "C", "system_address": 3}), ("complete", 2, 2)
            )
        self.assertIsNone(autopilot._get_overlay_route_progress({"location": "X", "system_address": 9}))

    def test_jump_line_is_hidden_without_a_plotted_route(self):
        autopilot = _make_route_overlay(
            {"event": "NavRouteClear", "Route": []},
            {"status": "Flying", "star_class": "G", "location": "Sol", "system_address": 1},
        )

        autopilot.update_overlay()

        autopilot.overlay.overlay_remove_text.assert_any_call("jumps")
        self.assertNotIn(
            "jumps",
            [call.args[0] for call in autopilot.overlay.overlay_text_segments.call_args_list],
        )
        autopilot.overlay.overlay_progress_bar.assert_not_called()

    def test_off_route_line_is_muted_and_has_no_progress_bar(self):
        autopilot = _make_route_overlay(
            {
                "event": "NavRoute",
                "Route": [{"StarSystem": "A", "SystemAddress": 1}, {"StarSystem": "B", "SystemAddress": 2}],
            },
            {"status": "Flying", "star_class": "G", "location": "Other", "system_address": 3},
        )
        autopilot.config["OverlayShowJumpsBar"] = True

        autopilot.update_overlay()

        autopilot.overlay.overlay_text_segments.assert_called_once_with(
            "jumps", [("JUMPS: ", "label"), ("Off route", "muted")], 0, 0
        )
        autopilot.overlay.overlay_progress_bar.assert_not_called()
        autopilot.overlay.overlay_remove_progress_bar.assert_any_call("jumps_bar")

    def test_completed_route_is_green_with_full_progress(self):
        autopilot = _make_route_overlay(
            {"event": "NavRoute", "Route": [{"StarSystem": "A"}, {"StarSystem": "B"}]},
            {"status": "Flying", "star_class": "G", "location": "B", "system_address": None},
        )
        autopilot.config["OverlayShowJumpsBar"] = True

        with patch("core.autopilot.monotonic", return_value=100.0):
            autopilot.update_overlay()

        autopilot.overlay.overlay_text_segments.assert_called_once_with(
            "jumps", [("JUMPS: ", "label"), ("1 of 1", "success")], 0, 0
        )
        autopilot.overlay.overlay_progress_bar.assert_called_once_with("jumps_bar", 1.0, 1)

    def test_unchanged_overlay_content_is_not_redrawn(self):
        ship_state = {"status": "in_supercruise", "star_class": "G", "location": "Sol", "system_address": 1}
        autopilot = _make_route_overlay({"event": "NavRouteClear", "Route": []}, ship_state)
        autopilot.config["OverlayShowShip"] = True

        autopilot.update_overlay()
        autopilot.update_overlay()
        self.assertEqual(autopilot.overlay.overlay_paint.call_count, 1)

        ship_state["status"] = "starting_hyperspace"
        autopilot.update_overlay()
        self.assertEqual(autopilot.overlay.overlay_paint.call_count, 2)
        autopilot.overlay.overlay_text_segments.assert_called_with(
            "ship", [("SHIP STATUS: ", "label"), ("Hyperspace jump", "value")], 0, 0
        )

    def test_config_change_and_reenable_force_a_redraw(self):
        autopilot = _make_route_overlay(
            {"event": "NavRouteClear", "Route": []},
            {"status": "in_space", "star_class": "G", "location": "Sol", "system_address": 1},
        )
        autopilot.config.update(
            {
                "OverlayShowShip": True,
                "OverlayTextFont": "Rajdhani",
                "OverlayTextFontSize": 14,
                "OverlayTextFontWeight": "SemiBold",
                "OverlayPositionAnchor": "Top left",
                "OverlayPositionUnit": "Percent",
                "OverlayTextXOffset": 1,
                "OverlayTextYOffset": 15,
                "OverlayPanelOpacity": 50,
            }
        )

        autopilot.update_overlay()
        autopilot.apply_overlay_config()
        autopilot.overlay.overlay_setfont.assert_called_once_with("Rajdhani", 14, "SemiBold")
        self.assertEqual(autopilot.overlay.overlay_paint.call_count, 2)

        autopilot.set_overlay(False)
        autopilot.set_overlay(True)
        self.assertEqual(autopilot.overlay.overlay_paint.call_count, 4)

    def test_all_bundled_rajdhani_weights_load(self):
        _load_font.cache_clear()
        try:
            for weight in ("Light", "Regular", "Medium", "SemiBold", "Bold"):
                with self.subTest(weight=weight):
                    font = _load_font("Rajdhani", 18, weight)
                    self.assertIsNotNone(font.getbbox("Overlay"))
        finally:
            _load_font.cache_clear()

    def test_refresh_loop_updates_until_terminated(self):
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.terminate = False
        autopilot.update_overlay = Mock(side_effect=[RuntimeError("busy"), None, None])

        def stop_after_three(_seconds):
            if autopilot.update_overlay.call_count == 3:
                autopilot.terminate = True

        with patch("core.autopilot.sleep", side_effect=stop_after_three):
            autopilot._overlay_refresh_loop()

        self.assertEqual(autopilot.update_overlay.call_count, 3)

    def test_monitor_dpi_change_queues_a_redraw(self):
        overlay = Overlay.__new__(Overlay)
        overlay.overlay_paint = Mock()
        overlay._render = Mock()

        self.assertEqual(overlay._window_proc(1, _WM_DPICHANGED, 144, 0), 0)
        overlay.overlay_paint.assert_called_once_with()
        overlay._render.assert_not_called()

    def test_game_resolution_does_not_change_status_surface_at_same_dpi(self):
        images = [
            _render_image(
                width,
                height,
                {},
                {"status": [[("AP MODE: ", "label"), ("Offline", "value")], 0, 0]},
                {},
                "Rajdhani",
                14,
                96,
                (10, 10),
            )[0]
            for width, height in ((1920, 1080), (3840, 2160))
        ]

        self.assertEqual(images[0].size, images[1].size)
        self.assertEqual(images[0].tobytes(), images[1].tobytes())

    def test_font_size_in_points_is_scaled_only_by_dpi(self):
        for font_size, dpi, expected_pixels in ((6, 96, 8), (6, 144, 12), (14, 96, 19), (14, 144, 28)):
            with (
                self.subTest(font_size=font_size, dpi=dpi),
                patch("gui.overlay._load_font", wraps=_load_font) as load_font,
            ):
                _render_image(
                    3840,
                    2160,
                    {},
                    {"status": ["Status", 0, 0, (255, 255, 255)]},
                    {},
                    "Rajdhani",
                    font_size,
                    dpi,
                    (10, 10),
                    font_weight="SemiBold",
                )
                load_font.assert_called_once_with("Rajdhani", expected_pixels, "SemiBold")

    def test_150_percent_dpi_scales_the_panel_by_150_percent(self):
        images = [
            _render_image(
                width,
                height,
                {},
                {"status": [[("AP MODE: ", "label"), ("Offline", "value")], 0, 0]},
                {},
                "Rajdhani",
                14,
                dpi,
                (10, 10),
            )[0]
            for width, height, dpi in ((1920, 1080, 96), (3840, 2160, 144))
        ]

        for before, after in zip(images[0].size, images[1].size):
            self.assertAlmostEqual(after, before * 1.5, delta=max(3, before * 0.06))

    def test_rectangle_is_drawn_on_a_transparent_canvas(self):
        image, origin = _render_image(
            40,
            30,
            {"region": [(4, 4), (14, 14), (0, 255, 0), 2]},
            {},
            {},
            "Arial",
            12,
            96,
            (0, 0),
        )

        self.assertEqual(image.getpixel((4 - origin[0], 4 - origin[1])), (0, 255, 0, 255))
        self.assertEqual(image.getpixel((0, 0)), (0, 0, 0, 0))
        self.assertLess(image.width * image.height, 40 * 30)

    def test_text_and_floating_text_are_rasterized(self):
        image, origin = _render_image(
            200,
            80,
            {},
            {"status": ["Status", 0, 0, (255, 0, 0)]},
            {"debug": ["OCR", 100, 30, (0, 255, 0)]},
            "Arial",
            12,
            96,
            (10, 5),
        )
        alpha = image.getchannel("A")

        self.assertIsNotNone(alpha.crop((10 - origin[0], 5 - origin[1], 80 - origin[0], 30 - origin[1])).getbbox())
        self.assertIsNotNone(alpha.crop((100 - origin[0], 30 - origin[1], 160 - origin[0], 55 - origin[1])).getbbox())

    def test_status_panel_uses_selected_corner_and_opacity(self):
        image, origin = _render_image(
            200,
            100,
            {},
            {"status": ["A", 0, 0, (136, 53, 0)]},
            {},
            "Rajdhani",
            14,
            96,
            (10, 12),
            "Bottom right",
            "Pixels",
            50,
        )

        self.assertGreaterEqual(origin[0], 0)
        self.assertGreaterEqual(origin[1], 0)
        self.assertLessEqual(origin[0] + image.width, 190)
        self.assertLessEqual(origin[1] + image.height, 88)
        self.assertEqual(image.getpixel((image.width - 2, image.height // 2))[3], 128)

    def test_status_text_uses_gui_palette_and_shadow(self):
        image, _origin = _render_image(
            200,
            80,
            {},
            {
                "status": [[("AP MODE: ", "label"), ("Offline", "value")], 0, 0],
                "placeholder": [[("SHIP STATUS: ", "label"), ("<init>", "muted")], 1, 0],
            },
            {},
            "Rajdhani",
            14,
            96,
            (10, 5),
        )
        pixels = set(image.getdata())

        def contains_color(color, min_alpha=220):
            expected = ImageColor.getrgb(color)
            return any(
                pixel[3] >= min_alpha and all(abs(pixel[channel] - expected[channel]) <= 20 for channel in range(3))
                for pixel in pixels
            )

        self.assertTrue(contains_color(PANEL, min_alpha=190))
        self.assertTrue(contains_color(ORANGE))
        self.assertTrue(contains_color(TEXT))
        self.assertTrue(contains_color(MUTED))
        self.assertTrue(any(max(pixel[:3]) <= 20 and pixel[3] >= 175 for pixel in pixels))

    def test_progress_bar_is_blue_and_clamped_to_route_range(self):
        images = [
            _render_image(
                300,
                100,
                {},
                {"jumps": [[("JUMPS: ", "label"), ("1 of 4", "value")], 0, 0]},
                {},
                "Rajdhani",
                14,
                96,
                (10, 10),
                bars={"jumps_bar": (progress, 1)},
            )[0]
            for progress in (0.0, 0.5, 1.0, 2.0)
        ]
        blue = ImageColor.getrgb(BLUE)
        blue_pixel_counts = [
            sum(pixel[:3] == blue and pixel[3] == 255 for pixel in image.getdata()) for image in images
        ]

        self.assertTrue(all(image.size == images[0].size for image in images))
        self.assertEqual(blue_pixel_counts[0], 0)
        self.assertGreater(blue_pixel_counts[1], 0)
        self.assertGreater(blue_pixel_counts[2], blue_pixel_counts[1])
        self.assertEqual(blue_pixel_counts[3], blue_pixel_counts[2])

    def test_progress_bar_stays_inside_panel_at_all_positions(self):
        text = {"jumps": [[("JUMPS: ", "label"), ("1 of 9", "value")], 0, 0]}
        blue = (*ImageColor.getrgb(BLUE), 255)
        for dpi in (96, 144):
            for font_size in (6, 14):
                expected, _ = _render_image(
                    1920, 1080, {}, text, {}, "Rajdhani", font_size, dpi, (10, 10), bars={"jumps_bar": (1 / 9, 1)}
                )
                self.assertIn(blue, expected.getdata())
                for anchor in ("Top left", "Top right", "Bottom left", "Bottom right"):
                    for unit, pos in (
                        ("Pixels", (10, 80)),
                        ("Pixels", (180, 10)),
                        ("Percent", (4, 17)),
                        ("Percent", (25, 3)),
                    ):
                        with self.subTest(dpi=dpi, font_size=font_size, anchor=anchor, unit=unit, pos=pos):
                            image, _ = _render_image(
                                1920,
                                1080,
                                {},
                                text,
                                {},
                                "Rajdhani",
                                font_size,
                                dpi,
                                pos,
                                anchor=anchor,
                                position_unit=unit,
                                bars={"jumps_bar": (1 / 9, 1)},
                            )
                            self.assertEqual(image.size, expected.size)
                            self.assertEqual(image.tobytes(), expected.tobytes())

    def test_progress_bar_row_between_text_rows_pushes_following_text_down(self):
        def render(text, bars):
            image, _ = _render_image(1920, 1080, {}, text, {}, "Rajdhani", 14, 96, (10, 10), bars=bars)
            return image

        first = [("JUMPS: ", "label"), ("1 of 4", "value")]
        second = [("DISTANCE: ", "label"), ("1.0 of 4.0 ly", "value")]
        without_bar = render({"jumps": [first, 0, 0], "distance": [second, 1, 0]}, {})
        with_bar = render({"jumps": [first, 0, 0], "distance": [second, 2, 0]}, {"jumps_bar": (0.25, 1)})

        self.assertEqual(with_bar.size[0], without_bar.size[0])
        self.assertEqual(with_bar.size[1] - without_bar.size[1], 14)
        blue = (*ImageColor.getrgb(BLUE), 255)
        width, height = with_bar.size
        blue_rows = {y for y in range(height) for x in range(width) if with_bar.getpixel((x, y)) == blue}
        # 12 px panel padding + 19 px text row + 2 px bar offset; Pillow draws the 4 px bar bottom inclusively.
        self.assertEqual(blue_rows, set(range(33, 38)))

    def test_progress_bar_without_text_still_has_a_panel(self):
        image, _ = _render_image(1920, 1080, {}, {}, {}, "Rajdhani", 14, 96, (10, 10), bars={"jumps_bar": (0.5, 0)})

        self.assertIn((*ImageColor.getrgb(BLUE), 255), image.getdata())

    def test_enable_refreshes_and_disable_clears_without_restarting(self):
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.config = {"OverlayTextEnable": False}
        autopilot.overlay = Mock()

        with patch.object(autopilot, "update_overlay") as update_overlay:
            autopilot.set_overlay(True)
            self.assertTrue(autopilot.config["OverlayTextEnable"])
            update_overlay.assert_called_once_with()

            autopilot.set_overlay(False)
            self.assertFalse(autopilot.config["OverlayTextEnable"])
            autopilot.overlay.overlay_clear.assert_called_once_with()
            autopilot.overlay.overlay_paint.assert_called_once_with()
            update_overlay.assert_called_once_with()

    def test_every_assist_end_resets_status_to_idle_after_the_stop_callback(self):
        assists = (
            ("travel_assist_enabled", "travel_assist", "travel_stop"),
            ("waypoint_assist_enabled", "waypoint_assist", "waypoint_stop"),
            ("afk_combat_assist_enabled", "afk_combat_loop", "afk_stop"),
            ("dss_assist_enabled", "dss_assist", "dss_stop"),
            ("single_waypoint_enabled", "single_waypoint_assist", "single_waypoint_stop"),
        )
        endings = (("interrupted", EdapInterruptError()), ("finished", None))
        for flag, routine, stop_msg in assists:
            cases = endings
            if flag == "single_waypoint_enabled":
                cases += (
                    ("target-confirmed", None),
                    ("target-failed", None),
                    ("target-interrupted", EdapInterruptError()),
                )
            for ending, error in cases:
                with self.subTest(assist=flag, ending=ending):
                    autopilot = EDAutopilot.__new__(EDAutopilot)
                    autopilot.terminate = False
                    autopilot.refresh_game_language = Mock(return_value=True)
                    autopilot.gui_loaded = False
                    autopilot._sc_sco_active_loop_thread = Mock(is_alive=Mock(return_value=True))
                    for name, _, _ in assists:
                        setattr(autopilot, name, name == flag)
                    autopilot.keys = autopilot.scrReg = None
                    autopilot.update_overlay = Mock()
                    autopilot.ap_ckb = Mock()
                    autopilot.notify_user = Mock()
                    autopilot._waypoint_plot = ({"SystemName": "Sol"}, True) if ending.startswith("target-") else None

                    def run_assist(*args, error=error):
                        autopilot.set_ap_status("Maneuvering")
                        if error is not None:
                            raise error
                        return ending == "target-confirmed"

                    setattr(autopilot, routine, run_assist)
                    if autopilot._waypoint_plot is not None:
                        autopilot.waypoint = SimpleNamespace(plot_destination=Mock(side_effect=run_assist))
                        autopilot.single_waypoint_assist = Mock()

                    def stop_loop(_seconds, autopilot=autopilot):
                        autopilot.terminate = True

                    with (
                        patch("core.autopilot.set_focus_elite_window"),
                        patch("core.autopilot.cv2.waitKey"),
                        patch("core.autopilot.sleep", side_effect=stop_loop),
                    ):
                        autopilot.engine_loop()

                    self.assertFalse(getattr(autopilot, flag))
                    self.assertEqual(autopilot.ap_state, "Idle")
                    self.assertEqual(
                        autopilot.ap_ckb.call_args_list[-2:],
                        [call(stop_msg), call("ap_status", "Idle")],
                    )
                    if ending.startswith("target-"):
                        self.assertIsNone(autopilot._waypoint_plot)
                        autopilot.waypoint.plot_destination.assert_called_once_with({"SystemName": "Sol"}, True)
                        autopilot.single_waypoint_assist.assert_not_called()
                        if ending == "target-interrupted":
                            autopilot.notify_user.assert_not_called()
                        else:
                            autopilot.notify_user.assert_called_once_with(
                                "Waypoint target confirmed."
                                if ending == "target-confirmed"
                                else "Waypoint target could not be confirmed. No flight was started."
                            )

    def _route_info_autopilot(self, location, address, travel=True):
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.travel_assist_enabled = travel
        autopilot.waypoint_assist_enabled = False
        autopilot.single_waypoint_enabled = False
        autopilot.jn = SimpleNamespace(ship_state=lambda: {"location": location, "system_address": address})
        autopilot.nav_route = SimpleNamespace(
            get_nav_route_data=lambda: {
                "event": "NavRoute",
                "Route": [
                    {"StarSystem": "A", "SystemAddress": 1, "StarPos": [0.0, 0.0, 0.0]},
                    {"StarSystem": "B", "SystemAddress": 2, "StarPos": [3.0, 4.0, 0.0]},
                    {"StarSystem": "C", "SystemAddress": 3, "StarPos": [3.0, 4.0, 12.0]},
                ],
            }
        )
        autopilot._overlay_route_active = False
        autopilot._overlay_route_signature = ()
        autopilot._overlay_route_systems = []
        autopilot._overlay_route_completed_at = None
        autopilot.ap_ckb = Mock()
        return autopilot

    def test_route_info_shows_jumps_and_distance_while_a_route_assist_runs(self):
        autopilot = self._route_info_autopilot("B", 2)

        autopilot.update_route_info()
        autopilot.update_route_info()

        autopilot.ap_ckb.assert_called_once_with("route_info", "Jumps: 1 of 2 \u00b7 5.0 of 17.0 ly")

    def test_route_info_is_cleared_at_route_end_and_on_stop(self):
        autopilot = self._route_info_autopilot("B", 2)
        autopilot.update_route_info()

        autopilot.jn = SimpleNamespace(ship_state=lambda: {"location": "C", "system_address": 3})
        autopilot.update_route_info()
        self.assertEqual(autopilot.ap_ckb.call_args_list[-1], call("route_info", ""))

        autopilot.jn = SimpleNamespace(ship_state=lambda: {"location": "B", "system_address": 2})
        autopilot.update_route_info()
        autopilot.travel_assist_enabled = False
        autopilot.update_route_info()
        self.assertEqual(autopilot.ap_ckb.call_args_list[-1], call("route_info", ""))

    def test_route_info_stays_empty_without_a_route_assist(self):
        autopilot = self._route_info_autopilot("B", 2, travel=False)

        autopilot.update_route_info()

        autopilot.ap_ckb.assert_not_called()

    def test_status_lines_can_be_hidden_and_compacted(self):
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.config = {
            "OverlayTextEnable": True,
            "OverlayShowMode": True,
            "OverlayShowStatus": False,
            "OverlayShowShip": False,
            "OverlayShowSystem": True,
            "OverlayShowJumps": True,
            "OverlayShowJumpsBar": True,
            "OverlayShowDistance": False,
        }
        autopilot.travel_assist_enabled = False
        autopilot.waypoint_assist_enabled = False
        autopilot.afk_combat_assist_enabled = False
        autopilot.dss_assist_enabled = False
        autopilot.ap_state = "Idle"
        autopilot.jn = SimpleNamespace(ship_state=lambda: {"status": "Flying", "star_class": "G", "location": "Sol"})
        autopilot.nav_route = SimpleNamespace(
            get_nav_route_data=lambda: {
                "event": "NavRoute",
                "Route": [
                    {"StarSystem": "Leesti", "SystemAddress": 1},
                    {"StarSystem": "Sol", "SystemAddress": 2},
                    {"StarSystem": "Beta", "SystemAddress": 3},
                ],
            }
        )
        autopilot._overlay_route_active = False
        autopilot._overlay_route_signature = ()
        autopilot._overlay_route_systems = []
        autopilot._overlay_route_completed_at = None
        autopilot.overlay = Mock()

        autopilot.update_overlay()

        rendered = [call.args[1] for call in autopilot.overlay.overlay_text_segments.call_args_list]
        rows = [call.args[2] for call in autopilot.overlay.overlay_text_segments.call_args_list]
        self.assertEqual(
            rendered,
            [
                [("AP MODE: ", "label"), ("Offline", "muted")],
                [("CURRENT SYSTEM: ", "label"), ("Sol", "value"), (" | ", "label"), ("G", "value")],
                [("JUMPS: ", "label"), ("1 of 2", "value"), (" (1 left)", "muted")],
            ],
        )
        self.assertEqual(rows, [0, 1, 2])
        autopilot.overlay.overlay_progress_bar.assert_called_once_with("jumps_bar", 0.5, 3)
        removed = {call.args[0] for call in autopilot.overlay.overlay_remove_text.call_args_list}
        self.assertEqual(removed, {"status", "ship", "fuel", "destination", "next_star", "distance"})
        autopilot.overlay.overlay_remove_progress_bar.assert_called_once_with("distance_bar")

    def test_unavailable_status_value_uses_muted_role(self):
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.config = {
            "OverlayTextEnable": True,
            "OverlayShowMode": False,
            "OverlayShowStatus": False,
            "OverlayShowShip": True,
            "OverlayShowSystem": True,
            "OverlayShowJumps": False,
        }
        autopilot.travel_assist_enabled = False
        autopilot.waypoint_assist_enabled = False
        autopilot.afk_combat_assist_enabled = False
        autopilot.dss_assist_enabled = False
        autopilot.ap_state = "Idle"
        autopilot.jn = SimpleNamespace(ship_state=lambda: {"status": None, "star_class": None, "location": None})
        autopilot.overlay = Mock()

        autopilot.update_overlay()

        rendered = [call.args[1] for call in autopilot.overlay.overlay_text_segments.call_args_list]
        self.assertEqual(
            rendered,
            [
                [("SHIP STATUS: ", "label"), ("Unknown", "muted")],
                [
                    ("CURRENT SYSTEM: ", "label"),
                    ("Unknown", "muted"),
                    (" | ", "label"),
                    ("Unknown", "muted"),
                ],
            ],
        )
        autopilot.overlay.overlay_progress_bar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
