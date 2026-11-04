"""Tests for rendering overlay contents without creating a Win32 window."""

import unittest
from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import ImageColor

from core.autopilot import EDAutopilot, _overlay_status_role, _set_overlay_config_defaults
from gui.overlay import _WM_DPICHANGED, Overlay, _load_font, _render_image
from gui.theme import BLUE, MUTED, ORANGE, PANEL, TEXT


def _make_route_overlay(route_data, ship_state):
    autopilot = EDAutopilot.__new__(EDAutopilot)
    autopilot.config = {
        "OverlayTextEnable": True,
        "OverlayShowMode": False,
        "OverlayShowStatus": False,
        "OverlayShowShip": False,
        "OverlayShowSystem": False,
        "OverlayShowJumps": True,
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
                "OverlayPositionAnchor": "Top left",
                "OverlayPositionUnit": "Percent",
                "OverlayPanelOpacity": 50,
                "OverlayShowMode": True,
                "OverlayShowStatus": True,
                "OverlayShowShip": True,
                "OverlayShowSystem": True,
                "OverlayShowJumps": True,
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
                    overlay._pos = (10, 10)
                    overlay._anchor = "Top left"
                    overlay._position_unit = "Pixels"
                    overlay._panel_opacity = 78
                    overlay.overlay_set_progress(progress)
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
                    self.assertEqual(render_image.call_args.kwargs["progress"], progress)
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

    def test_cleared_route_is_not_reported_complete_when_not_at_destination(self):
        route = {"event": "NavRoute", "Route": [{"StarSystem": "A"}, {"StarSystem": "B"}]}
        cleared = {"event": "NavRouteClear", "Route": []}
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.nav_route = SimpleNamespace(get_nav_route_data=Mock(side_effect=[route, cleared]))
        autopilot._overlay_route_active = False
        autopilot._overlay_route_signature = ()
        autopilot._overlay_route_systems = []
        autopilot._overlay_route_completed_at = None

        self.assertEqual(
            autopilot._get_overlay_route_progress({"location": "A", "system_address": None}),
            ("on_route", 0, 1),
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
        autopilot.overlay.overlay_set_progress.assert_called_once_with(None)

    def test_off_route_line_is_muted_and_has_no_progress_bar(self):
        autopilot = _make_route_overlay(
            {
                "event": "NavRoute",
                "Route": [{"StarSystem": "A", "SystemAddress": 1}, {"StarSystem": "B", "SystemAddress": 2}],
            },
            {"status": "Flying", "star_class": "G", "location": "Other", "system_address": 3},
        )

        autopilot.update_overlay()

        autopilot.overlay.overlay_text_segments.assert_called_once_with(
            "jumps", [("JUMPS: ", "label"), ("Off route", "muted")], 0, 0
        )
        autopilot.overlay.overlay_set_progress.assert_called_once_with(None)

    def test_completed_route_is_green_with_full_progress(self):
        autopilot = _make_route_overlay(
            {"event": "NavRoute", "Route": [{"StarSystem": "A"}, {"StarSystem": "B"}]},
            {"status": "Flying", "star_class": "G", "location": "B", "system_address": None},
        )

        with patch("core.autopilot.monotonic", return_value=100.0):
            autopilot.update_overlay()

        autopilot.overlay.overlay_text_segments.assert_called_once_with(
            "jumps", [("JUMPS: ", "label"), ("1 of 1", "success")], 0, 0
        )
        autopilot.overlay.overlay_set_progress.assert_called_once_with(1.0)

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
                )
                load_font.assert_called_once_with("Rajdhani", expected_pixels)

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
                progress=progress,
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
                    1920, 1080, {}, text, {}, "Rajdhani", font_size, dpi, (10, 10), progress=1 / 9
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
                                progress=1 / 9,
                            )
                            self.assertEqual(image.size, expected.size)
                            self.assertEqual(image.tobytes(), expected.tobytes())

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

    def test_status_lines_can_be_hidden_and_compacted(self):
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.config = {
            "OverlayTextEnable": True,
            "OverlayShowMode": True,
            "OverlayShowStatus": False,
            "OverlayShowShip": False,
            "OverlayShowSystem": True,
            "OverlayShowJumps": True,
        }
        autopilot.travel_assist_enabled = False
        autopilot.waypoint_assist_enabled = False
        autopilot.afk_combat_assist_enabled = False
        autopilot.dss_assist_enabled = False
        autopilot.ap_state = "Idle"
        autopilot.jump_cnt = 1
        autopilot.total_jumps = 2
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
                [("CURRENT SYSTEM: ", "label"), ("Sol", "value"), (", ", "value"), ("G", "value")],
                [("JUMPS: ", "label"), ("1 of 2", "value")],
            ],
        )
        self.assertEqual(rows, [0, 1, 2])
        autopilot.overlay.overlay_set_progress.assert_called_once_with(0.5)
        self.assertEqual(autopilot.overlay.overlay_remove_text.call_count, 2)

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
        autopilot.jump_cnt = 0
        autopilot.total_jumps = 0
        autopilot.jn = SimpleNamespace(ship_state=lambda: {"status": None, "star_class": None, "location": None})
        autopilot.overlay = Mock()

        autopilot.update_overlay()

        rendered = [call.args[1] for call in autopilot.overlay.overlay_text_segments.call_args_list]
        self.assertEqual(
            rendered,
            [
                [("SHIP STATUS: ", "label"), ("<init>", "muted")],
                [
                    ("CURRENT SYSTEM: ", "label"),
                    ("<init>", "muted"),
                    (", ", "value"),
                    ("<init>", "muted"),
                ],
            ],
        )
        autopilot.overlay.overlay_set_progress.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()
