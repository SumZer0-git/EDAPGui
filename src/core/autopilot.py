"""The EDAutopilot class: setup, engine loop and setters.

Ideas taken from: https://github.com/skai2/EDAutopilot"""

import ctypes
import logging
import math
import threading
from time import monotonic, sleep

import cv2
import kthread

import vision.regions
import vision.screen
import vision.templates
from controls.keys import EDKeys
from core import paths
from core.config import ConfigMixin
from core.constants import SCOOPABLE_STAR_CLASSES, FlagsScoopingFuel, FlagsSupercruise, ship_size_map
from core.logger import logger, set_log_level
from core.types import EdapInterruptError
from game.graphics_settings import EDGraphicsSettings
from game.journal import EDJournal, get_ship_fullname
from game.nav_route import NavRouteParser
from game.status import StatusParser
from gui.fields import DEFAULT_OVERLAY_LINE_ORDER, OVERLAY_LINE_SETTINGS, normalize_overlay_line_order
from gui.overlay import Overlay
from i18n import LocalizationManager
from integrations.tce import TceIntegration
from integrations.voice import Voice
from panels.galaxy_map import EDGalaxyMap
from panels.internal_status import EDInternalStatusPanel
from panels.navigation import EDNavigationPanel
from panels.ship_control import EDShipControl
from panels.station_services import EDStationServicesInShip
from panels.system_map import EDSystemMap
from routines.afk_combat import AfkCombat
from routines.assists import AssistsMixin
from routines.flight import FlightMixin
from routines.waypoints import EDWayPoint
from vision.detection import DetectionMixin
from vision.ocr import OCR
from vision.screen import set_focus_elite_window


def _overlay_status_role(status: str) -> str:
    if status in {
        "Arrived at target",
        "Docking Complete",
        "Undock Complete, accelerating",
        "Takeoff Complete, accelerating",
    }:
        return "success"
    if status == "Avoiding star":
        return "warning"
    if status == "Idle":
        return "muted"
    if status in {
        "Align",
        "Approaching target",
        "Docking",
        "DSS Scan",
        "Entering supercruise",
        "Executing Undocking/Launch",
        "Jump",
        "Logout",
        "Maneuvering",
        "Refueling",
        "Refueling and repairing",
        "Requesting docking",
        "SC to Target",
    } or status.startswith(("SC to Station:", "Targeting Station:")):
        return "active"
    return "value"


_SHIP_STATUS_TEXT = {
    "in_space": "Normal space",
    "in_supercruise": "Supercruise",
    "in_station": "Docked",
    "starting_hyperspace": "Hyperspace jump",
    "starting_supercruise": "Entering supercruise",
    "starting_docking": "Docking requested",
    "dockinggranted": "Docking granted",
    "dockingdenied": "Docking denied",
    "in_docking": "Docking",
    "starting_undocking": "Starting undocking",
    "in_undocking": "Undocking",
}


def _overlay_ship_status(status: str | None) -> tuple[str, str]:
    """Return the readable overlay text and color role for an internal ship status key."""
    if not status:
        return "Unknown", "muted"
    text = _SHIP_STATUS_TEXT.get(status)
    if text is None:
        text = status.replace("_", " ").strip().capitalize()
    if status == "in_station":
        return text, "success"
    if status == "dockingdenied":
        return text, "warning"
    return text, "value"


def _set_overlay_config_defaults(config: dict) -> None:
    uses_legacy_positions = "OverlayPositionUnit" not in config
    defaults = (
        ("OverlayTextEnable", True),
        ("OverlayTextXOffset", 50 if uses_legacy_positions else 1),
        ("OverlayTextYOffset", 400 if uses_legacy_positions else 15),
        ("OverlayTextFont", "Rajdhani"),
        ("OverlayTextFontSize", 14),
        ("OverlayTextFontWeight", "Medium"),
        ("OverlayPositionAnchor", "Top left"),
        ("OverlayPositionUnit", "Pixels" if uses_legacy_positions else "Percent"),
        ("OverlayPanelOpacity", 50),
        ("OverlayCaptureVisible", False),
        ("OverlayShowMode", True),
        ("OverlayShowStatus", True),
        ("OverlayShowShip", True),
        ("OverlayShowSystem", True),
        ("OverlayShowJumps", True),
        ("OverlayShowJumpsBar", True),
        ("OverlayShowDistance", True),
        ("OverlayShowDistanceBar", True),
        ("OverlayShowDestination", True),
        ("OverlayShowNextStar", True),
        ("OverlayShowFuel", True),
    )
    for key, default in defaults:
        config.setdefault(key, default)
    config["OverlayLineOrder"] = normalize_overlay_line_order(config.get("OverlayLineOrder"))


def _overlay_fuel_segments(
    fuel_level, fuel_capacity, scooping: bool, refuel_threshold: float, abort_threshold: float
) -> list[tuple[str, str]]:
    """Fuel line colored against the AP refuel and abort thresholds."""
    if fuel_level is None or not fuel_capacity:
        return [("FUEL: ", "label"), ("Unknown", "muted")]
    percent = max(0, min(100, round(fuel_level / fuel_capacity * 100)))
    if percent < abort_threshold:
        role = "error"
    elif percent < refuel_threshold:
        role = "warning"
    else:
        role = "value"
    segments = [("FUEL: ", "label"), (f"{percent} %", role)]
    if scooping:
        segments.append((" (scooping)", "active"))
    return segments


def _overlay_next_star_segments(star_class) -> list[tuple[str, str]]:
    if not star_class:
        return [("NEXT STAR: ", "label"), ("Unknown", "muted")]
    if star_class in SCOOPABLE_STAR_CLASSES:
        return [("NEXT STAR: ", "label"), (star_class, "value"), (" (scoopable)", "muted")]
    return [("NEXT STAR: ", "label"), (star_class, "value"), (" (not scoopable)", "warning")]


OVERLAY_REFRESH_INTERVAL = 1.0


class EDAutopilot(ConfigMixin, DetectionMixin, FlightMixin, AssistsMixin):
    # Class-level defaults keep partially constructed instances (tests) working; __init__ sets per-instance values.
    _overlay_lock = threading.RLock()
    _overlay_last_frame = None
    _overlay_status = None
    _route_info_text = ""

    def __init__(self, cb, do_thread=True):

        # NOTE!!! When adding a new config value below, add the same after read_config() to set
        # a default value or an error will occur reading the new value!
        self.config = {
            "DSSButton": "Primary",  # if anything other than "Primary", it will use the Secondary Fire button for DSS
            "JumpTries": 3,  #
            "NavAlignTries": 3,  #
            "RefuelThreshold": 65,  # if fuel level get below this level, it will attempt refuel
            "FuelThreasholdAbortAP": 10,  # level at which AP will terminate, because we are not scooping well
            "WaitForAutoDockTimer": 240,  # After docking granted, wait this amount of time for us to get docked with autodocking
            "SunBrightThreshold": 125,  # The low level for brightness detection, range 0-255, want to mask out darker items
            "FuelScoopTimeOut": 35,  # number of second to wait for full tank, might mean we are not scooping well or got a small scooper
            "DockingRetries": 30,  # number of time to attempt docking
            "HotKey_StartTravel": "home",  # if going to use other keys, need to look at the python keyboard package
            "HotKey_StopAllAssists": "end",
            "EnableRandomness": False,  # add some additional random sleep times to avoid AP detection (0-3sec at specific locations)
            "ActivateEliteEachKey": False,  # Activate Elite window before each key or group of keys
            "OverlayTextEnable": True,
            "OverlayTextYOffset": 15,
            "OverlayTextXOffset": 1,
            "OverlayTextFont": "Rajdhani",
            "OverlayTextFontSize": 14,
            "OverlayTextFontWeight": "Medium",
            "OverlayPositionAnchor": "Top left",
            "OverlayPositionUnit": "Percent",
            "OverlayPanelOpacity": 50,
            "OverlayCaptureVisible": False,  # True shows the overlay in screenshots, recordings and screen detection
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
            "DiscordWebhook": False,  # discord not implemented yet
            "DiscordWebhookURL": "",
            "DiscordUserID": "",
            "VoiceEnable": False,
            "VoiceID": 1,  # my Windows only have 3 defined (0-2)
            "LogDEBUG": False,  # enable for debug messages
            "LogINFO": True,
            "ShipConfigFile": None,  # Ship config to load on start - deprecated
            "TCEDestinationFilepath": "C:\\TCE\\DUMP\\Destination.json",  # Destination file for TCE
            "TCEInstallationPath": "C:\\TCE",
            "AutomaticLogout": False,  # Logout when we are done with the mission
            "FCDepartureTime": 5.0,  # Extra time to fly away from a Fleet Carrier
            "Language": "auto",  # Journal language, or a folder name in assets/locales
            "DebugOverlay": False,
        }
        # NOTE!!! When adding a new config value above, add the same after read_config() to set
        # a default value or an error will occur reading the new value!

        self.ship_configs = {
            "Ship_Configs": {},  # Dictionary of ship types with additional settings
        }
        self._sc_sco_active_loop_thread = None
        self._sc_sco_active_loop_enable = False
        self.sc_sco_is_active = 0
        self._sc_sco_active_on_ls = 0
        self._single_waypoint_station = None
        self._single_waypoint_system = None
        self._waypoint_plot = None
        self._prev_star_system = None
        self.honk_thread = None
        self._tce_integration = None

        # used this to write the self.config table to the json file
        # self.write_config(self.config)

        cnf = self.read_config()
        # if we read it then point to it, otherwise use the default table above
        if cnf is not None:
            # NOTE!!! Add default values for new entries below!
            if "SunBrightThreshold" not in cnf:
                cnf["SunBrightThreshold"] = 125
            if "TCEDestinationFilepath" not in cnf:
                cnf["TCEDestinationFilepath"] = "C:\\TCE\\DUMP\\Destination.json"
            if "TCEInstallationPath" not in cnf:
                cnf["TCEInstallationPath"] = "C:\\TCE"
            if "AutomaticLogout" not in cnf:
                cnf["AutomaticLogout"] = False
            if "FCDepartureTime" not in cnf:
                cnf["FCDepartureTime"] = 5.0
            if "Language" not in cnf:
                cnf["Language"] = "auto"
            cnf.pop("OCRLanguage", None)
            if "DebugOverlay" not in cnf:
                cnf["DebugOverlay"] = False
            _set_overlay_config_defaults(cnf)
            if str(cnf.get("OverlayTextFont", "")).casefold() == "eurostyle":
                cnf["OverlayTextFont"] = "Rajdhani"
            cnf.pop("OverlayGraphicEnable", None)
            if "HotKey_StartTravel" not in cnf:
                cnf["HotKey_StartTravel"] = cnf.get("HotKey_StartFSD", self.config["HotKey_StartTravel"])
            cnf.pop("HotKey_StartFSD", None)
            cnf.pop("HotKey_StartSC", None)
            cnf.pop("HotKey_StartRobigo", None)
            cnf.pop("Robigo_Single_Loop", None)
            cnf.pop("ElwScannerEnable", None)
            cnf.pop("EnableEDMesg", None)
            cnf.pop("EDMesgActionsPort", None)
            cnf.pop("EDMesgEventsPort", None)
            self.config = cnf
            logger.debug("read AP json:" + str(cnf))
        else:
            self.write_config(self.config)

        # Load selected language
        self.locale = LocalizationManager(str(paths.LOCALES_DIR), "en")
        self._language_signature = None
        self._language_failed_signature = None

        shp_cnf = self.read_ship_configs()
        # if we read it then point to it, otherwise use the default table above
        if shp_cnf is not None:
            if len(shp_cnf) != len(self.ship_configs):
                # If configs of different lengths, then a new parameter was added.
                # self.write_config(self.config)
                # Add default values for new entries
                if "Ship_Configs" not in shp_cnf:
                    shp_cnf["Ship_Configs"] = dict()
                self.ship_configs = shp_cnf
                logger.debug("read Ships Config json:" + str(shp_cnf))
            else:
                self.ship_configs = shp_cnf
                logger.debug("read Ships Config json:" + str(shp_cnf))
        else:
            self.write_ship_configs(self.ship_configs)

        # config the voice interface
        self.vce = Voice()
        self.vce.v_enabled = self.config["VoiceEnable"]
        self.vce.set_voice_id(self.config["VoiceID"])
        self.vce.say("Welcome to Autopilot")
        self._ui_callback = cb
        self.ap_ckb = self._dispatch_callback

        # set log level based on config input, defaulting to warning
        level = logging.WARNING
        if self.config["LogINFO"]:
            level = logging.INFO
        if self.config["LogDEBUG"]:
            level = logging.DEBUG
        set_log_level(level, "at startup")

        # initialize all to false
        self.travel_assist_enabled = False
        self.afk_combat_assist_enabled = False
        self.waypoint_assist_enabled = False
        self.dss_assist_enabled = False
        self.single_waypoint_enabled = False

        # Create instance of each of the needed Classes
        self.gfx_settings = EDGraphicsSettings()

        self.scr = vision.screen.Screen(self.ap_ckb)

        self.jn = EDJournal(self.ap_ckb)
        if not self.refresh_game_language():
            raise RuntimeError("The game OCR language could not be initialized. Check the GUI log and technical log.")
        self.templ = vision.templates.ImageTemplates(self.scr.screen_height)
        self.scrReg = vision.regions.ScreenRegions(self.scr, self.templ)
        logger.info(f"Screen {self.scr.screen_width}x{self.scr.screen_height}")
        self.keys = EDKeys(self.ap_ckb)
        self.keys.activate_window = self.config["ActivateEliteEachKey"]
        self.afk_combat = AfkCombat(self.keys, self.jn, self.vce)
        self.waypoint = EDWayPoint(self, self.jn.ship_state()["odyssey"])
        self.status = StatusParser()
        # Separate parser: the overlay refresh thread must not share the AP thread's parser state.
        self._overlay_status = StatusParser()
        self.nav_route = NavRouteParser()
        self.ship_control = EDShipControl(self, self.scr, self.keys, self.ap_ckb)
        self.internal_panel = EDInternalStatusPanel(self, self.scr, self.keys, self.ap_ckb)
        self.galaxy_map = EDGalaxyMap(self, self.scr, self.keys, self.ap_ckb, self.jn.ship_state()["odyssey"])
        self.system_map = EDSystemMap(self, self.scr, self.keys, self.ap_ckb, self.jn.ship_state()["odyssey"])
        self.stn_svcs_in_ship = EDStationServicesInShip(self, self.scr, self.keys, self.ap_ckb)
        self.nav_panel = EDNavigationPanel(self, self.scr, self.keys, self.ap_ckb)

        # rate as ship dependent. Can be found on the outfitting page for the ship. However, it looks like supercruise
        # has worse performance for these rates
        # see:  https://forums.frontier.co.uk/threads/supercruise-handling-of-ships.396845/
        #
        # If you find that you are overshoot in pitch or roll, need to adjust these numbers.
        # Algorithm will roll the vehicle for the nav point to be north or south and then pitch to get the nave point
        # to center
        self.yawrate = 8.0
        self.rollrate = 80.0
        self.pitchrate = 33.0
        self.sunpitchuptime = 0.0

        self.total_dist_jumped = 0
        self._overlay_route_active = False
        self._overlay_route_signature = ()
        self._overlay_route_systems = []
        self._overlay_route_completed_at = None
        self.current_ship_type = None
        self.gui_loaded = False

        # Overlay vars
        self.ap_state = "Idle"

        # Initialize the Overlay class
        self._overlay_lock = threading.RLock()
        self._overlay_last_frame = None
        self.overlay = Overlay("", elite=1)
        self.apply_overlay_config()

        self.debug_overlay = self.config["DebugOverlay"]

        # debug window
        from gui.cv_view import CvFrames

        self.cv_frames = CvFrames()

        # start the engine thread
        self.terminate = False  # terminate used by the thread to exit its loop
        if do_thread:
            self.ap_thread = kthread.KThread(target=self.engine_loop, name="EDAutopilot")
            self.ap_thread.start()
            self.overlay_refresh_thread = threading.Thread(
                target=self._overlay_refresh_loop, name="EDAP overlay refresh", daemon=True
            )
            self.overlay_refresh_thread.start()

    @property
    def tce_integration(self) -> TceIntegration:
        """Load TCE Integration class when needed."""
        if not self._tce_integration:
            self._tce_integration = TceIntegration(self, self.ap_ckb)
        return self._tce_integration

    def set_language(self, language: str) -> None:
        """Queue a game-language selection; only the engine replaces OCR between assists."""
        if language != "auto" and language not in self.locale.available_languages:
            raise ValueError(f"Unknown game language: {language!r}")
        self.config["Language"] = language
        self._language_failed_signature = None
        self.notify_user("Game language selection saved. It will be applied between assists.")

    def refresh_game_language(self) -> bool:
        """Recheck journal headers without replacing an OCR engine during an input sequence."""
        state = self.jn.ship_state()
        journal_language = state.get("language")
        selection = self.config["Language"]
        signature = (selection, journal_language, self.jn.current_log)
        if signature == self._language_failed_signature:
            return False
        if selection == "auto" and state.get("language_pending") and signature != self._language_signature:
            logger.debug("Waiting for the new journal's game-language header.")
            deadline = monotonic() + 15
            while state.get("language_pending") and monotonic() < deadline:
                sleep(0.2)
                state = self.jn.ship_state()
            journal_language = state.get("language")
            signature = (selection, journal_language, self.jn.current_log)
        if signature == self._language_failed_signature:
            return False
        if signature != self._language_signature:
            language = self.locale.resolve_language(selection, journal_language)
            ocr_language = self.locale.ocr_language_for(language)
            if not OCR.supports_language(ocr_language):
                self.locale.warn(f"OCR language {ocr_language!r} in pack {language!r} is not supported. Using English.")
                language = "en"
                ocr_language = self.locale.ocr_language_for(language)
            try:
                ocr = getattr(self, "ocr", None)
                if ocr is None or ocr.language != ocr_language:
                    ocr = OCR(self.scr, ocr_language)
            except (OSError, ValueError, RuntimeError) as error:
                logger.exception("Could not initialize OCR for game language %s", language)
                self.notify_user(f"Could not initialize OCR for {language}: {error}. Change Game language or restart.")
                self._language_failed_signature = signature
                return False
            self.locale.change_language(language)
            self.ocr = ocr
            for name in ("internal_panel", "galaxy_map", "system_map", "stn_svcs_in_ship", "nav_panel"):
                panel = getattr(self, name, None)
                if panel is not None:
                    panel.ocr = ocr
            self._language_signature = signature
            logger.debug(
                "Game language selected: setting=%s journal=%r active=%s OCR=%s",
                selection,
                journal_language,
                language,
                ocr_language,
            )
            self.ap_ckb("game_language", language)
        for warning in self.locale.take_warnings():
            self.notify_user(warning)
        return True

    # draw the overlay data on the ED Window
    #
    def _get_overlay_route_progress(self, ship_state):
        route_data = self.nav_route.get_nav_route_data()
        route = route_data.get("Route") or []
        if not isinstance(route, list):
            route = []
        current_address = ship_state.get("system_address")
        current_name = ship_state.get("location")

        if route_data.get("event") == "NavRoute" and len(route) < 2:
            self._overlay_route_active = False
            self._overlay_route_signature = ()
            self._overlay_route_systems = []
            self._overlay_route_completed_at = None
            return None

        if route_data.get("event") == "NavRoute":
            signature = tuple(
                (system.get("SystemAddress"), system.get("StarSystem")) if isinstance(system, dict) else (None, None)
                for system in route
            )
            if not self._overlay_route_active or signature != self._overlay_route_signature:
                self._overlay_route_completed_at = None
                self._overlay_route_signature = signature
            self._overlay_route_active = True
            self._overlay_route_systems = route

            if current_address is None and not current_name:
                return None

            index = None
            if current_address is not None:
                for route_index, system in enumerate(route):
                    if isinstance(system, dict) and system.get("SystemAddress") == current_address:
                        index = route_index
                        break
            if index is None and current_name:
                for route_index, system in enumerate(route):
                    if not isinstance(system, dict):
                        continue
                    if system.get("StarSystem") == current_name and (
                        current_address is None or system.get("SystemAddress") is None
                    ):
                        index = route_index
                        break

            total = len(route) - 1
            if index is None:
                self._overlay_route_completed_at = None
                return ("off_route", None, total)
            if index == total:
                now = monotonic()
                if self._overlay_route_completed_at is None:
                    self._overlay_route_completed_at = now
                if now - self._overlay_route_completed_at < 60:
                    return ("complete", total, total)
                return None

            self._overlay_route_completed_at = None
            return ("on_route", index, total)

        self._overlay_route_active = False
        route = self._overlay_route_systems
        if len(route) < 2:
            return None
        destination = route[-1]
        if not isinstance(destination, dict):
            return None
        destination_address = destination.get("SystemAddress")
        destination_name = destination.get("StarSystem")
        at_destination = (
            current_address == destination_address
            if current_address is not None and destination_address is not None
            else bool(current_name and current_name == destination_name)
        )
        if not at_destination:
            # The game clears the route shortly after the final jump starts, before arrival.
            if self._is_route_system(route[-2], current_address, current_name):
                total = len(route) - 1
                return ("on_route", total - 1, total)
            self._overlay_route_systems = []
            self._overlay_route_signature = ()
            self._overlay_route_completed_at = None
            return None

        now = monotonic()
        if self._overlay_route_completed_at is None:
            self._overlay_route_completed_at = now
        if now - self._overlay_route_completed_at < 60:
            total = len(route) - 1
            return ("complete", total, total)

        self._overlay_route_systems = []
        self._overlay_route_signature = ()
        self._overlay_route_completed_at = None
        return None

    @staticmethod
    def _is_route_system(system, current_address, current_name) -> bool:
        if not isinstance(system, dict):
            return False
        address = system.get("SystemAddress")
        if current_address is not None and address is not None:
            return current_address == address
        return bool(current_name and current_name == system.get("StarSystem"))

    @staticmethod
    def _get_overlay_route_distance(route: list, route_index: int) -> tuple[float, float] | None:
        if len(route) < 2 or not 0 <= route_index < len(route):
            return None

        positions = []
        for system in route:
            position = system.get("StarPos") if isinstance(system, dict) else None
            if (
                not isinstance(position, (list, tuple))
                or len(position) != 3
                or any(
                    isinstance(coordinate, bool)
                    or not isinstance(coordinate, (int, float))
                    or not math.isfinite(coordinate)
                    for coordinate in position
                )
            ):
                return None
            positions.append(position)

        leg_distances = [math.dist(start, end) for start, end in zip(positions, positions[1:])]
        return sum(leg_distances[route_index:]), sum(leg_distances)

    def _overlay_fuel_line(self, ship_state: dict) -> list[tuple[str, str]]:
        """Prefer live Status.json fuel; the journal only updates on fuel events."""
        fuel_level = ship_state.get("fuel_level")
        scooping = bool(ship_state.get("is_scooping"))
        if self._overlay_status is not None:
            try:
                status = self._overlay_status.get_cleaned_data()
                if status.get("FuelMain") is not None:
                    fuel_level = status["FuelMain"]
                scooping = bool(status["Flags"] & FlagsScoopingFuel)
            except Exception as exc:
                logger.debug(f"Overlay fuel status unavailable: {exc}")
        return _overlay_fuel_segments(
            fuel_level,
            ship_state.get("fuel_capacity"),
            scooping,
            self.config.get("RefuelThreshold", 65),
            self.config.get("FuelThreasholdAbortAP", 10),
        )

    def update_overlay(self):
        """Refresh the status overlay; it is only redrawn when the shown content changed."""
        with self._overlay_lock:
            if not self.config["OverlayTextEnable"]:
                return
            ship_state = self.jn.ship_state()
            ap_mode = "Offline"
            if self.travel_assist_enabled:
                ap_mode = "Travel Assist"
            elif self.waypoint_assist_enabled:
                ap_mode = "Waypoint Assist"
            elif self.afk_combat_assist_enabled:
                ap_mode = "AFK Combat Assist"
            elif self.dss_assist_enabled:
                ap_mode = "DSS Assist"

            ap_mode_color = "muted" if ap_mode == "Offline" else "active"
            ship_status, ship_color = _overlay_ship_status(ship_state["status"])

            sclass = ship_state["star_class"]
            if sclass is None:
                sclass = "Unknown"
                sclass_color = "muted"
            else:
                sclass_color = "value"

            location = ship_state["location"]
            if location is None:
                location = "Unknown"
                location_color = "muted"
            else:
                location_color = "value"
            config = self.config

            def shown(key):
                return bool(config.get(OVERLAY_LINE_SETTINGS[key], False))

            route_progress = (
                self._get_overlay_route_progress(ship_state)
                if any(
                    shown(key) for key in ("jumps", "jumps_bar", "distance", "distance_bar", "destination", "next_star")
                )
                else None
            )
            route = self._overlay_route_systems if route_progress is not None else []
            on_route = route_progress is not None and route_progress[0] != "off_route"
            complete = on_route and route_progress[0] == "complete"

            # Text lines hold segments, progress bars a fraction; None hides the line.
            lines = dict.fromkeys(OVERLAY_LINE_SETTINGS)
            if shown("mode"):
                lines["mode"] = [("AP MODE: ", "label"), (ap_mode, ap_mode_color)]
            if shown("status"):
                lines["status"] = [("AP STATUS: ", "label"), (self.ap_state, _overlay_status_role(self.ap_state))]
            if shown("ship"):
                lines["ship"] = [("SHIP STATUS: ", "label"), (ship_status, ship_color)]
            if shown("fuel"):
                lines["fuel"] = self._overlay_fuel_line(ship_state)
            if shown("system"):
                lines["system"] = [
                    ("CURRENT SYSTEM: ", "label"),
                    (location, location_color),
                    (" | ", "label"),
                    (sclass, sclass_color),
                ]

            destination = route[-1] if route and isinstance(route[-1], dict) else {}
            if shown("destination") and destination.get("StarSystem"):
                lines["destination"] = [
                    ("DESTINATION: ", "label"),
                    (destination["StarSystem"], "success" if complete else "value"),
                ]

            if shown("next_star") and on_route and not complete:
                next_index = route_progress[1] + 1
                next_system = route[next_index] if next_index < len(route) else None
                if isinstance(next_system, dict):
                    lines["next_star"] = _overlay_next_star_segments(next_system.get("StarClass"))

            if route_progress is not None and not on_route:
                if shown("jumps"):
                    lines["jumps"] = [("JUMPS: ", "label"), ("Off route", "muted")]
            elif on_route:
                _state, completed, total = route_progress
                if shown("jumps"):
                    lines["jumps"] = [
                        ("JUMPS: ", "label"),
                        (f"{completed} of {total}", "success" if complete else "value"),
                    ]
                    if not complete:
                        lines["jumps"].append((f" ({total - completed} left)", "muted"))
                if shown("jumps_bar"):
                    lines["jumps_bar"] = completed / total

            route_distance = (
                self._get_overlay_route_distance(route, route_progress[1])
                if on_route and (shown("distance") or shown("distance_bar"))
                else None
            )
            if route_distance is not None:
                remaining, total = route_distance
                if shown("distance"):
                    lines["distance"] = [
                        ("DISTANCE: ", "label"),
                        (f"{total - remaining:,.1f} of {total:,.1f} ly", "success" if complete else "value"),
                    ]
                    if not complete:
                        lines["distance"].append((f" ({remaining:,.1f} left)", "muted"))
                if shown("distance_bar") and total > 0:
                    lines["distance_bar"] = (total - remaining) / total

            # (key, content, row) in the user's order; hidden lines take no row.
            frame = []
            row = 0
            for key in normalize_overlay_line_order(config.get("OverlayLineOrder")):
                content = lines[key]
                frame.append((key, content, None if content is None else row))
                if content is not None:
                    row += 1
            if frame == self._overlay_last_frame:
                return
            self._overlay_last_frame = frame

            for key, content, line_row in frame:
                if key.endswith("_bar"):
                    if content is None:
                        self.overlay.overlay_remove_progress_bar(key)
                    else:
                        self.overlay.overlay_progress_bar(key, content, line_row)
                elif content is None:
                    self.overlay.overlay_remove_text(key)
                else:
                    self.overlay.overlay_text_segments(key, content, line_row, 0)
            self.overlay.overlay_paint()

    def _overlay_refresh_loop(self):
        """Keep the overlay current while assists block the engine loop."""
        last_error = None
        while not self.terminate:
            try:
                self.update_overlay()
                self.update_route_info()
                last_error = None
            except Exception as e:
                if str(e) != last_error:
                    logger.warning(f"Overlay refresh failed: {e}")
                    last_error = str(e)
            sleep(OVERLAY_REFRESH_INTERVAL)

    def apply_overlay_config(self):
        self.overlay.overlay_setfont(
            self.config["OverlayTextFont"],
            self.config["OverlayTextFontSize"],
            self.config["OverlayTextFontWeight"],
        )
        self.overlay.overlay_set_layout(
            self.config["OverlayPositionAnchor"],
            self.config["OverlayPositionUnit"],
            self.config["OverlayTextXOffset"],
            self.config["OverlayTextYOffset"],
            self.config["OverlayPanelOpacity"],
        )
        self.overlay.overlay_set_capture_visible(bool(self.config["OverlayCaptureVisible"]))
        self._overlay_last_frame = None
        if self.config["OverlayTextEnable"]:
            self.update_overlay()
        else:
            self.overlay.overlay_paint()

    def update_route_info(self):
        """Publish route progress to the GUI footer while a route assist runs; otherwise clear it."""
        text = ""
        if self.travel_assist_enabled or self.waypoint_assist_enabled or self.single_waypoint_enabled:
            with self._overlay_lock:
                route_progress = self._get_overlay_route_progress(self.jn.ship_state())
                route = self._overlay_route_systems
            if route_progress is not None and route_progress[0] == "on_route":
                _state, completed, total = route_progress
                text = f"Jumps: {completed} of {total}"
                route_distance = self._get_overlay_route_distance(route, completed)
                if route_distance is not None:
                    remaining, total_distance = route_distance
                    text += f" \u00b7 {total_distance - remaining:,.1f} of {total_distance:,.1f} ly"
        if text != self._route_info_text:
            self._route_info_text = text
            self.ap_ckb("route_info", text)

    def set_ap_status(self, txt):
        """Publish the current AP status to the overlay and GUI."""
        self.ap_state = txt
        self.update_overlay()
        self.ap_ckb("ap_status", txt)

    def notify_user(self, message, speak=False):
        """Publish an intentional user-facing message to the GUI log only."""
        self.ap_ckb("user_message", (message, speak))

    def _dispatch_callback(self, msg, body=None):
        if msg == "log":
            self.notify_user(body)
        elif msg == "log+vce":
            self.notify_user(body, speak=True)
        else:
            self._ui_callback(msg, body)

    def _finish_assist(self, stop_msg):
        """Reports the end of an assist after its thread work is done, so no late status can override Idle."""
        self.ap_ckb(stop_msg)
        self.set_ap_status("Idle")
        self.update_route_info()

        # Performs left menu ops to request docking

        # a set of convience routes to pitch, rotate by specified degress

        # Disabled until SC to station enabled.
        # if self._single_waypoint_station != "":
        #     res = self.supercruise_to_station(self.scrReg, self._single_waypoint_station)
        #     if res is False:
        #         return False

    # raising an exception to the engine loop thread, so we can terminate its execution
    #  if thread was in a sleep, the exception seems to not be delivered
    def ctype_async_raise(self, thread_obj, exception):
        found = False
        target_tid = 0
        for tid, tobj in threading._active.items():
            if tobj is thread_obj:
                found = True
                target_tid = tid
                break

        if not found:
            raise ValueError("Invalid thread object")

        ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(target_tid), ctypes.py_object(exception))
        # ref: http://docs.python.org/c-api/init.html#PyThreadState_SetAsyncExc
        if ret == 0:
            raise ValueError("Invalid thread ID")
        elif ret > 1:
            # Huh? Why would we notify more than one threads?
            # Because we punch a hole into C level interpreter.
            # So it is better to clean up the mess.
            ctypes.pythonapi.PyThreadState_SetAsyncExc(target_tid, 0)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    #
    # Setter routines for state variables
    #
    def set_travel_assist(self, enable=True):
        if not enable and self.travel_assist_enabled:
            self.ctype_async_raise(self.ap_thread, EdapInterruptError)
        self.travel_assist_enabled = enable

    def set_waypoint_assist(self, enable=True):
        if not enable and self.waypoint_assist_enabled:
            self.ctype_async_raise(self.ap_thread, EdapInterruptError)
        self.waypoint_assist_enabled = enable

    def set_afk_combat_assist(self, enable=True):
        if not enable and self.afk_combat_assist_enabled:
            self.ctype_async_raise(self.ap_thread, EdapInterruptError)
        self.afk_combat_assist_enabled = enable

    def set_dss_assist(self, enable=True):
        if not enable and self.dss_assist_enabled:
            self.ctype_async_raise(self.ap_thread, EdapInterruptError)
        self.dss_assist_enabled = enable

    def set_single_waypoint_assist(self, system: str, station: str, enable=True):
        if not enable and self.single_waypoint_enabled:
            self.ctype_async_raise(self.ap_thread, EdapInterruptError)
        self._single_waypoint_system = system
        self._single_waypoint_station = station
        self._waypoint_plot = None
        self.single_waypoint_enabled = enable

    def set_waypoint_plot(self, entry, station: bool) -> bool:
        if any(
            (
                self.travel_assist_enabled,
                self.waypoint_assist_enabled,
                self.afk_combat_assist_enabled,
                self.dss_assist_enabled,
                self.single_waypoint_enabled,
            )
        ):
            self.notify_user("Stop the running assist before selecting a waypoint target.")
            return False
        self._waypoint_plot = (dict(entry), station)
        self.single_waypoint_enabled = True
        return True

    def set_debug_overlay(self, enable):
        self.debug_overlay = enable
        self.config["DebugOverlay"] = bool(enable)
        if not enable:
            self.overlay.overlay_clear_diagnostics()
        self.overlay.overlay_paint()

    def set_randomness(self, enable=False):
        self.config["EnableRandomness"] = enable

    def set_activate_elite_eachkey(self, enable=False):
        self.config["ActivateEliteEachKey"] = enable

    def set_automatic_logout(self, enable=False):
        self.config["AutomaticLogout"] = enable

    def set_overlay(self, enable=False):
        with self._overlay_lock:
            self.config["OverlayTextEnable"] = enable
        if not enable:
            with self._overlay_lock:
                self.overlay.overlay_clear()
                self.overlay.overlay_paint()
                self._overlay_last_frame = None
        else:
            self.update_overlay()

    def set_voice(self, enable=False):
        if enable:
            self.vce.set_on()
        else:
            self.vce.set_off()

    def set_log_error(self, enable=False):
        self.config["LogDEBUG"] = False
        self.config["LogINFO"] = False
        set_log_level(logging.ERROR)

    def set_log_debug(self, enable=False):
        self.config["LogDEBUG"] = True
        self.config["LogINFO"] = False
        set_log_level(logging.DEBUG)

    def set_log_info(self, enable=False):
        self.config["LogDEBUG"] = False
        self.config["LogINFO"] = True
        set_log_level(logging.INFO)

    # quit() is important to call to clean up, if we don't terminate the threads we created the AP will hang on exit
    # have then then kill python exec
    def quit(self):
        for name in ("compass", "target", "occluded", "hud"):
            self.cv_frames.close(name)
        if self.vce is not None:
            self.vce.quit()
        if self.overlay is not None:
            self.overlay.overlay_quit()
        self.terminate = True

    #
    # This function will execute in its own thread and will loop forever until
    # the self.terminate flag is set
    #
    def engine_loop(self):
        while not self.terminate:
            if not self.refresh_game_language():
                sleep(1)
                continue
            self._sc_sco_active_loop_enable = True

            if self._sc_sco_active_loop_enable:
                if self._sc_sco_active_loop_thread is None or not self._sc_sco_active_loop_thread.is_alive():
                    self._sc_sco_active_loop_thread = threading.Thread(target=self._sc_sco_active_loop, daemon=True)
                    self._sc_sco_active_loop_thread.start()

            if self.travel_assist_enabled:
                logger.debug("Running travel_assist")
                set_focus_elite_window()
                self.update_overlay()
                try:
                    self.travel_assist(self.scrReg)
                except EdapInterruptError:
                    logger.debug("Caught stop exception")
                except Exception as e:
                    logger.exception(f"Unexpected error in Travel Assist: {e}")

                logger.debug("Completed travel_assist")
                self.travel_assist_enabled = False
                self._finish_assist("travel_stop")

            elif self.waypoint_assist_enabled:
                logger.debug("Running waypoint_assist")

                set_focus_elite_window()
                self.update_overlay()
                self.total_dist_jumped = 0
                try:
                    self.waypoint_assist(self.keys, self.scrReg)
                except EdapInterruptError:
                    logger.debug("Caught stop exception")
                except Exception as e:
                    logger.exception(f"Unexpected error in waypoint assist: {e}")

                self.waypoint_assist_enabled = False
                self._finish_assist("waypoint_stop")

            elif self.afk_combat_assist_enabled:
                self.update_overlay()
                try:
                    self.afk_combat_loop()
                except EdapInterruptError:
                    logger.debug("Stopping afk_combat")
                self.afk_combat_assist_enabled = False
                self._finish_assist("afk_stop")

            elif self.dss_assist_enabled:
                logger.debug("Running dss_assist")
                set_focus_elite_window()
                self.update_overlay()
                try:
                    self.dss_assist()
                except EdapInterruptError:
                    logger.debug("Stopping DSS Assist")
                self.dss_assist_enabled = False
                self._finish_assist("dss_stop")

            elif self.single_waypoint_enabled:
                self.update_overlay()
                try:
                    plot = self._waypoint_plot
                    if plot is None:
                        self.single_waypoint_assist()
                    else:
                        set_focus_elite_window()
                        entry, station = plot
                        if self.waypoint.plot_destination(entry, station):
                            self.notify_user("Waypoint target confirmed.")
                        else:
                            self.notify_user("Waypoint target could not be confirmed. No flight was started.")
                except EdapInterruptError:
                    logger.debug("Stopping Single Waypoint Assist")
                self._waypoint_plot = None
                self.single_waypoint_enabled = False
                self._finish_assist("single_waypoint_stop")

            # Check once EDAPGUI loaded to prevent errors logging to the listbox before loaded
            if self.gui_loaded:
                # Check if ship has changed
                ship = self.jn.ship_state()["type"]
                # Check if a ship and not a suit (on foot)
                if ship not in ship_size_map:
                    # Clear current ship
                    self.current_ship_type = ""
                else:
                    ship_fullname = get_ship_fullname(ship)

                    # Check if ship changed or just loaded
                    if ship != self.current_ship_type:
                        if self.current_ship_type is not None:
                            cur_ship_fullname = get_ship_fullname(self.current_ship_type)
                            self.ap_ckb(
                                "log+vce", f"Switched ship from your {cur_ship_fullname} to your {ship_fullname}."
                            )
                        else:
                            self.ap_ckb("log+vce", f"Welcome aboard your {ship_fullname}.")

                        # Check for fuel scoop and advanced docking computer
                        if not self.jn.ship_state()["has_fuel_scoop"]:
                            self.ap_ckb("log+vce", f"Warning, your {ship_fullname} is not fitted with a Fuel Scoop.")
                        if not self.jn.ship_state()["has_adv_dock_comp"]:
                            self.ap_ckb(
                                "log+vce",
                                f"Warning, your {ship_fullname} is not fitted with an Advanced Docking Computer.",
                            )
                        if self.jn.ship_state()["has_std_dock_comp"]:
                            self.ap_ckb(
                                "log+vce", f"Warning, your {ship_fullname} is fitted with a Standard Docking Computer."
                            )

                        # Store ship for change detection BEFORE loading config and GUI update
                        self.current_ship_type = ship

                        # Load ship configuration with proper hierarchy
                        self.load_ship_configuration(ship)

                        # Update GUI with ship config
                        self.ap_ckb("update_ship_cfg")

                        # Reload templates
                        self.templ.reload_templates()

            sleep(1)

    def ship_tst_pitch(self):
        """Performs a ship pitch test by pitching 360 degrees.
        If the ship does not rotate enough, decrease the pitch value.
        If the ship rotates too much, increase the pitch value.
        """
        if not self.status.get_flag(FlagsSupercruise):
            self.ap_ckb("log", "Enter Supercruise and try again.")
            return

        if self.jn.ship_state()["target"] is None:
            self.ap_ckb("log", "Select a target system and try again.")
            return

        set_focus_elite_window()
        sleep(0.25)
        self.keys.send("SetSpeed50")
        self.pitch_up(360)

    def ship_tst_roll(self):
        """Performs a ship roll test by pitching 360 degrees.
        If the ship does not rotate enough, decrease the roll value.
        If the ship rotates too much, increase the roll value.
        """
        if not self.status.get_flag(FlagsSupercruise):
            self.ap_ckb("log", "Enter Supercruise and try again.")
            return

        if self.jn.ship_state()["target"] is None:
            self.ap_ckb("log", "Select a target system and try again.")
            return

        set_focus_elite_window()
        sleep(0.25)
        self.keys.send("SetSpeed50")
        self.rotate_left(360)

    def ship_tst_yaw(self):
        """Performs a ship yaw test by pitching 360 degrees.
        If the ship does not rotate enough, decrease the yaw value.
        If the ship rotates too much, increase the yaw value.
        """
        if not self.status.get_flag(FlagsSupercruise):
            self.ap_ckb("log", "Enter Supercruise and try again.")
            return

        if self.jn.ship_state()["target"] is None:
            self.ap_ckb("log", "Select a target system and try again.")
            return

        set_focus_elite_window()
        sleep(0.25)
        self.keys.send("SetSpeed50")
        self.yaw_left(360)


#
# This main is for testing purposes.
#
def main():
    # handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
    # if handle != None:
    #    win32gui.SetForegroundWindow(handle)  # put the window in foreground

    ed_ap = EDAutopilot(cb=None, do_thread=False)
    sleep(2)

    for x in range(10):
        # target_align(scrReg)
        print("Calling nav_align")
        # ed_ap.nav_align(ed_ap.scrReg)

        # loc = get_destination_offset(scrReg)
        # print("get_dest: " +str(loc))
        # loc = get_nav_offset(scrReg)
        # print("get_nav: " +str(loc))
        cv2.waitKey(0)
        print("Done nav")
        sleep(8)

    ed_ap.overlay.overlay_quit()
