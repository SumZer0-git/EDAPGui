# Unreleased
 - Important notice: Runtime files moved to the new `user_data/` folder. Existing users must manually copy `configs/AP.json`, `configs/ship_configs.json` and their own waypoint files from `waypoints/` into `user_data/configs/` and `user_data/waypoints/`.
 - Removed the unused EDMesg integration, its bundled library, configuration settings and dependencies.
 - Removed the obsolete ELW scanner, its FSS automation, GUI option, configuration, vision templates, and documentation.
 - Removed the obsolete Robigo passenger-mission assist, its GUI controls and configuration, dedicated vision templates, and documentation.
 - Added `core/version.py` as the single place for the application version (still 1.7.0); the window title and log read it from there.
 - Added the update check (`core/updates.py`): at startup, and via Help > Check for Updates, the program looks up the latest release of `DopeEx/EDAPGui` in the background and offers to open the download page if it is newer. Nothing happens at startup if there is no release yet or GitHub cannot be reached.
 - Added the Ruff linter (`pyproject.toml`, `requirements-dev.txt`) with the rule groups `F` (pyflakes), `I` (import sorting), `N` (pep8-naming, except `N806`), `W` (whitespace) and the checks `E711`, `E712`, `E713`, `E714`, `E722` and `F841`; run `ruff check .`. The code is formatted with `ruff format .` (check with `ruff format --check .`).
 - Added offline unit tests (no game needed) for the status, cargo, market and navigation route parsers, journal event handling, waypoint files and routing, localization, shared paths, reference data and screen region scaling.
 - Added offline unit tests for reading the Elite Dangerous keybindings (`game/keybindings.py`), using an anonymized sample bindings file in `tests/fixtures/bindings/`.
 - Added offline tests for template matching and screen detection (compass, nav point, target, occlusion, supercruise disengage message, region filters) using the screenshot crops in `tests/fixtures/` and a fake screen instead of the game.
 - Added a regression test with real game screenshots (`tests/test_screenshots.py`, 3840x2160 and 1920x1080, HDR and SDR) that is skipped when the git-excluded screenshots in `tests/fixtures/screenshots/` are missing.
 - Added `docs/Structure.md` describing the folder structure and rules for where new files belong.
 - Added native templates for 3840x2160 (`assets/templates/2160p/`), used unscaled at that resolution; for every other screen height the nearest larger set is scaled down (for example for 1920x1080), or the largest set is scaled up. `tools/make_templates.py` creates them from full screenshots (the raw screenshots in `tests/fixtures/screenshots/` are git-excluded and never committed).
 - Added language-independent detection of the supercruise disengage message (blue text gate plus OCR compared with the localized text) instead of the English-only `sc-disengage` template, which works for German and English.
 - Added detection of a target hidden behind a planet or moon with a white-filter ring template (`target_occluded`) that is also matched in a beige filter (the ring is white with HDR and beige without), plus fallbacks for very bright scenes (stars) and the localized "line of sight" message of Supercruise Assist.
 - Changed the target offset to be computed from the fitted center of the target circle instead of fixed correction values, so it is independent of the resolution.
 - Changed the supported languages to German and English; removed the French and Russian locales, the `sc-disengage` template and the deprecated `sc_disengage`.
 - Changed the supported and recommended Python version to 3.12; CI, release checks and the installer and startup scripts now use Python 3.12. Python 3.13 has not been validated yet.
 - Changed the dependencies that are independent of PaddleOCR to `mss` 10.2.0, `Pillow` 11.3.0, `colorlog` 6.12.0, `kthread` 0.2.3, `PyAutoGUI` 0.9.54, `pynput` 1.8.2, `pywin32` 312, `strsimpy` 0.3 and `xmltodict` 1.0 (`requirements.txt` and `requirements-ci.txt`). Existing installations must run `install_requirements.bat` to install the updates; starting EDAPGui does not update packages in an existing virtual environment.
 - Updated OCR to PaddleOCR 3.6.0 and PaddlePaddle 3.2.2, migrated to the v3 prediction/result API, and aligned NumPy 2.2.6, OpenCV contrib 4.10.0.84 and Requests 2.34.2 with the OCR stack. Existing installations must remove the old `venv` folder and run `install_requirements.bat` to avoid leftover PaddleOCR 2 dependencies.
 - Removed the unused legacy PaddleOCR result conversion; panel detection now consumes recognized text directly from PaddleOCR 3 results.
 - Fixed supercruise disengage checks being skipped when the target ring cannot be found, lowered the HUD prompt gate so smaller dropout messages trigger OCR, and log when OCR returns no text.
 - Added debug logging of the target-ring match score and its screen offset during alignment.
 - Added GitHub workflows: `ci.yml` runs Ruff and the unit tests (without the OCR test, using the slim `requirements-ci.txt`) on pushes and pull requests to `main`; `release.yml` runs the full checks including OCR when a `vX.Y.Z` tag is pushed, verifies that the tag is on `main` and matches `core/version.py`, and creates a GitHub release with the changelog notes and a source ZIP.
 - Changed class names to CapWords and exception names to end with `Error`: `Screen_Regions` to `ScreenRegions`, `Image_Templates` to `ImageTemplates`, `AFK_Combat` to `AfkCombat`, `EDAP_Interrupt` to `EdapInterruptError` and `PathNotFoundException` to `PathNotFoundError`.
 - Changed function and argument names to snake_case: `PressKey`/`ReleaseKey` to `press_key`/`release_key`, `rotateLeft`, `rotateRight`, `pitchUp`, `pitchDown`, `yawLeft` and `yawRight` to `rotate_left` etc., and arguments such as `scaleX`/`scaleY`, `fileName`, `doThread`, `fontSize`, `vSay` and `noOp` to `scale_x`/`scale_y`, `file_name`, `do_thread`, `font_size`, `text` and `no_op`. Names that follow the Windows API (`wndProc`, `hWnd`, `wParam`, `lParam`, `Input_I`) are kept.
 - Changed config, waypoint and log files to be stored in `user_data/` (configs, waypoints, logs, debug output). The folder is created on first start.
 - Changed reference files (`resolution.json` and the example waypoint files) to live in `data/` and be copied to `user_data/` when missing.
 - Changed paths to be resolved relative to the project folder instead of the working directory.
 - Changed `templates/`, `locales/` and `screen/edap.ico` to `assets/templates/`, `assets/locales/` and `assets/icons/edap.ico`; the documentation screenshots from `screen/` to `docs/screenshots/`. The disabled build workflow still references the old `screen\` paths and will be reworked separately.
 - Changed `readme.md` and `ChangeLog.md` to `README.md` and `CHANGELOG.md`.
 - Changed the in-app links (About, Changelog) and the clone URL in the README to point to this repository instead of the upstream repository.
 - Removed the disabled `build-executable.yml` workflow; a build of the executable will be added later.
 - Removed the "Join Discord" menu entry, the Discord link and the email contact addresses.
 - Changed `controls/keys.py` (`EDKeys`) to be split: reading the Elite Dangerous keybindings now lives in `game/keybindings.py` (`KeyBindings`), while `controls/keys.py` only sends keys.
 - Removed the manual template calibration (File > Calibrate Target/Compass, `vision/calibration.py`, `docs/Calibration.md`), the `TargetScale` setting and the per-ship `compass_scale`, as well as the legacy 3440x1440 templates: all templates are now derived from the native 2160p set.
 - Changed `ED_AP.py` to `core/autopilot.py` and split `EDAutopilot` into mixin classes with identical behavior: `core/config.py` (`ConfigMixin`), `vision/calibration.py` (`CalibrationMixin`), `vision/detection.py` (`DetectionMixin`), `routines/flight.py` (`FlightMixin`) and `routines/assists.py` (`AssistsMixin`). `EDAP_Interrupt` and `ScTargetAlignReturn` moved to `core/types.py`.
 - Changed the GUI code of `EDAPGui.py` to `gui/main_window.py`; `EDAPGui.py` in the project root remains as the thin start script (`python EDAPGui.py`, `start_ed_ap.bat`).
 - Changed the file headers of all source files to a short module docstring; author lines and the copy of the hotkey list (see README) were removed. Credits to the original projects stay in the affected modules and the README.
 - Changed the start script `EDAPGui.py` in the project root to `main.py` (`python main.py`); `start_ed_ap.bat` is unchanged for users.
 - Changed all program packages (`controls/`, `core/`, `game/`, `gui/`, `i18n/`, `integrations/`, `panels/`, `routines/`, `vision/`) and `main.py` to live in the new `src/` folder; start the program with `python src/main.py` (`start_ed_ap.bat` is unchanged for users). The bundled `EDMesg/` library moved to `third_party/EDMesg/`.
 - Changed `EDWayPoint.py`, `Robigo.py` and `EDafk_combat.py` to live in the new `routines/` package as `routines/waypoints.py`, `routines/robigo.py` and `routines/afk_combat.py`.
 - Changed `TCE_Integration.py`, `Voice.py` and the `EDAP_EDMesg_*.py` modules to live in the new `integrations/` package as `integrations/tce.py`, `integrations/voice.py` and `integrations/edmesg/{interface,client,server}.py`.
 - Changed `Overlay.py` to `gui/overlay.py` and the `simple_localization/` package to `i18n/`.
 - Changed `EDNavigationPanel.py`, `EDInternalStatusPanel.py`, `EDGalaxyMap.py`, `EDSystemMap.py`, `EDStationServicesInShip.py` and `EDShipControl.py` to live in the new `panels/` package as `panels/navigation.py`, `panels/internal_status.py`, `panels/galaxy_map.py`, `panels/system_map.py`, `panels/station_services.py` and `panels/ship_control.py`.
 - Changed `EDJournal.py`, `StatusParser.py`, `CargoParser.py`, `MarketParser.py`, `NavRouteParser.py`, `EDGraphicsSettings.py` and `WindowsKnownPaths.py` to live in the new `game/` package as `game/journal.py`, `game/status.py`, `game/cargo.py`, `game/market.py`, `game/nav_route.py`, `game/graphics_settings.py` and `game/known_paths.py`.
 - Changed `EDKeys.py`, `directinput.py` and `MousePt.py` to live in the new `controls/` package as `controls/keys.py`, `controls/directinput.py` and `controls/mouse_point.py`.
 - Changed `Screen.py`, `Screen_Regions.py`, `OCR.py` and `Image_Templates.py` to live in the new `vision/` package as `vision/screen.py`, `vision/regions.py`, `vision/ocr.py` and `vision/templates.py`.
 - Changed `paths.py`, `EDlogger.py` and `EDAP_data.py` to live in the new `core/` package as `core/paths.py`, `core/logger.py` and `core/constants.py`.
 - Changed tests to live in `tests/` (`tests/test_*.py`), test images in `tests/fixtures/`, and the manual debug tool `Test_Routines.py` to `tests/manual/debug_routines.py` (run with `python -m tests.manual.debug_routines`). Run the unit tests with `python -m unittest discover -s tests -t .`. Tests that need the running game live in `tests/integration/` and are skipped unless `EDAP_INTEGRATION=1` is set.
 - Changed all `from x import *` to explicit imports, removed unused imports and sorted the imports in all modules. Comparisons with `None`, `True` and `False` were rewritten to `is None` or plain truth checks, bare `except:` became `except Exception:`, trailing whitespace was removed, and unused local variables were removed.
 - Changed log rotation to keep only the 10 newest rotated log files in `user_data/logs/`.
 - Fixed the discovery scan (honk) ending early during FSD route assist: the scan button is now held until the journal reports the finished scan (`FSSDiscoveryScan`) instead of a fixed 7 seconds, and the scan is retried up to three times (10 s each) if no confirmation arrives, while the scan keeps running in parallel to refueling and positioning. Keys that share a physical key or modifier with a currently held button (for example `S` for pitch up and the scanner button) now wait until it is released instead of cutting the scan off.
 - Fixed rotated log files (`autopilot <date>.log`) not being excluded by `.gitignore`.
 - Fixed the OCR unit test to check only the known text of its screenshot instead of the complete HUD text.
 - Fixed circular imports between `ED_AP.py` and the `routines/` and `panels/` modules; all modules can now be imported on their own.
 - Fixed a startup error when the previous log file could not be renamed because a rotated log with the same timestamp already existed.
 - Fixed the screen detection and capture on setups with monitors of different Windows scaling (for example a 100% monitor next to a 150% one), where the monitor size and the Elite window position were reported scaled and the compass was not found; the detection now runs in a per-monitor DPI aware context without changing the DPI behavior of the UI and the overlay.
 - Fixed the unit tests rotating away the log files of real sessions; the tests now log to a temporary folder (`EDAP_LOG_DIR`).
 - Cleaned up `.gitignore`.

# 8/19/2025 v1.7.0: General updates.
 - Changed all Parser files to UTF-8 format.
 - Fixed CARTOGRAPHICS detection.
 - Improved key collision reporting.
 - Fixed nav point directly behind us causing ship to roll continually.
 - Added simple OCR detection to Nav Panel tab
 - Reworked internal (right) panel with OCR and debug overlay.
 - Added OCR checks for Gal map and Sys map.
 - Added Debug Overlay option.
 - Fix not selling CMM Composites and any other item with space in name.
 - Improved nav point behind logic.
 - Added new template matching mode with separate H, S and V channel detection.
 - Changed timeout for auto dock.
 - Speed/simplify docking request.
 - Added additional checks when market.json is not available (never been docked at station).
 - Added startup and requirements batch files from Glasses branch.

# 7/28/2025 v1.6.1: Debug_overlay bug.
 - Removed debug_overlay bug.

# 7/28/2025 v1.6.0: Panther Clipper + small improvements.
 - Added quick fix for Robigo issue not selecting the system.
 - Changed logger level on startup to INFO to allow logging of startup info before the user settings are read. Added mostly so we can log the version of EDAP that is started.
 - Updated Russian language file.
 - Moved default ship data from files to EDAP_data.py and included all ships.
 - Deleted unused old config files.
 - Added panther clipper data.
 - Improve disengage check while in a loop.

# 7/3/2025 Stumpii: Small improvements.
 - Added Russian localisation file.
 - Added language selection for OCR.
 - Added localisation to nav panel.
 - Added TCE Integration class.
 - Added OCR to station services screen check.
 - Added fix for Robigo issue not selecting system in gal map.
 - Improved debug for gal map.
 - Separated Station Services and Construction Services because OCR only works for Station Services (Construction Services are not as slow to open).
 - Moved docking cleanup to Nav Panel class.
 - Added OCR test class.
 - Test code for gal map.
 - Prevent gal map being opened twice for no reason.
 - Added region scaling for stations.
 - Added EDNavigationPanel.py for navigation panel code.
 - Disabled build-executable.yml as it always fails.

# 6/1/2025 Stumpii: Bug fix.
 - Removed 'deprecated' warning that does not work in old python versions.

# 5/30/2025 Stumpii: Various minor updates. 
 - Added check for disengage while in target align.
 - Log new file on each startup of EDAP. Store previous runs.
 - Increase scroll up time for buy/sell to make sure at top of list.
 - Attempt to improve status.json file reading that sometimes results in a file error.

# 5/28/2025 Stumpii: Various minor updates.
 - Added cobra-mk5 config file.
 - Added galaxy and system map selection to EDMesg server.
 - Allow more target align tires.
 - Updated waypoints to new format. Removed some no longer required.
 - Renamed capture_region as there was a duplicate.
 - Added debug and improvment to gal map.
 - Changed log message to avoid double timestamp and unnecessary text. Cleans up log file.

# 5/24/2025 Stumpii: Check update crash
 - Fix crash when checking for updates.
 - Updated version.

# 5/20/2025 Stumpii: Waypoints
 - Added new waypoint system. NOTE: This breaks compatibility with the old waypoints, so needs any existing waypoint to be remade.
 - Added EDMesg system.
 - Enabled target occlusion.
 - Added localisation for OCR.
 - A whole slew of other changes. Too many to mention.
 - This has a number of new modules added, so update python modules.

# 4/26/2025 Stumpii: Minor updates.
- Added support for negative sunpitch times.
- Added docking retries to GUI.
- Added better logging for docking and return to nav tab.
- Added reload of templates after calibration.

# 4/8/2025 Stumpii: Added Corsair.
 - Added Corsair to ED_Data and ship config.
 - 
# 3/31/2025 Stumpii: Flags2 bug fix.
 - Added None check for Flags2 giving error when ED is not running.
 - Moved new auto property to the end of the config. Set default value.
 
# 3/30/2025 DopeEx
 - Added DSS Assist mode - activates DSS scanner when changing system with manual jump
 - Added automatic logout to the main menu option when the FSD assist has arrived at the destination and the destination is in space

# 3/30/2025 Stumpii: Minor updates.
 - SCO without OCR, using Status.json
 - Made honk global to prevent premature disabling in fast ships (Dolphin)
 - Added FSD SCO Active flag to status parser.
 - Added time delta and destination data to status parser and simplified general code.
 - Added glide detection for SC Assist to planet surface.

# 3/10/2025 Stumpii: Added System Colonisation Ship support into waypoint system
 - Added System Colonisation Ship support into waypoint system.
 - Updated waypoints doc with new feature.
 - Add compass scaling to test routines.

# 3/9/2025 Stumpii
 - Added logging of key name (key_a) to send log.
 - Modified FSD Jump logic to better handle Braben Tunnels.
 - Changed logging of callbacks to stop assists.
 - Added timestamp to autopilot log.

# 3/8/2025 Stumpii
 - Added button to load TCE (Trade Computer Extension) destination.
 - Added hyperlink to TCE for those that do not know of it.
 - Moved Honk to start when entering a system instead of when leaving to allow commanders to cancel FSD Assist if there is something interesting in the system.
 - Updated requirements text to include Pillow 10.4.

# 3/5/2025 Stumpii
 - Added single waypoint assist feature. A couple of text boxes and checkbox on the debug screen allow you to enter the system name to go to and then check the box to start your travels to that system.
 - Fix to gal map send key that accepts hex values only, not string.
 - Tweak to journal to remove all the if checks when only one type of event may occur at a time.
 - Changed camyaw to cam zoom and added explanation why the shortcut works.
 - Added alt, lat and longitude to status parser for future angle of approach calc.
 - Added NavRouteParser for NavRoute.json files.
 - Added CargoParser for Cargo.json files.
 - Added MarketParser for Market.json files.
 - Added voice messages to assist routines.

# 3/4/205 SumZer0
 - Updated EDKeys.py to add back in the keyboard binding name to the autopilot.log file instead of just the keyboard scancode.  Also handle KeyError exception when dumping bindings to log file

# 3/2/205 Stumpii: Compass update and OCR fix for high CPU
 - Removed the OCR detection of SCO as it was using high CPU. Now it will only use OCR when the disengage template is detected.
 - Lowered discharge threshold so that the discharge template will detect both disengage and sco and use OCR to determine which is active.
 - Added navpoint-behind template and image to detect when nav point is behind us.
 - Added rotate right and yaw right control as nav logic can use both now.
 - Added python 3.9 support to EDKeys update.
 - Added auto activate ED back into EDKeys (was removed in last update).
 - Added CamZoomIn for Gal Map to remove mouse click in the future.
 - Added SCO FSD detection to journal.
 - Added timestamp to status parser.
 - Added log if jumping and not in analysis mode.

# 2/28/2025 DGotshalk/SumZer0
 - Update EDKeys.py
 - Update to EDKeys.py to import the environ module

# 2/1/2025 RatherRude
 - Support all buttons on all keyboard layouts
 - Add hold key, add multiple buttons, add Support for all buttons on all keyboard layouts

# 1/6/2025 Stumpii: Undock from planetary surface
 - Added undocking from planetary surface (i.e. takeoff when not at a docking station). Ship will thrust up, toggle landing gear, rotate roughly 90 deg, boost and SCO out of orbit.
 - Added extra key bindings for undocking.

# 1/6/2025 Stumpii: OCR for SCO detection
 - Added OCR routine.
 - Added SCO active detection using OCR. Detection is performed on a separate thread to prevent the main loop being delayed for processing.
 - Added SCO deactivation is SCO is active and we are low on fuel or high on temperature.
 - Updated requirements for PaddleOCR.
 - Added separate color filter range for SCO text.

# 1/5/2025 Stumpii: Separated target and compass calibration
 - Separated compass from target calibration.
 - Added ship config file that will hold ship data.
 - Moved calibrated screen scaling from resolution file to settings file.
 - Increased range of compass region for the Mandalay.
 - Added additional methods for overlays to add item as rectangle and also to remove overlay items.
 - Updated requirements text file.

# 12/13/2024 Stumpii: Added Cobra Mk V and ship detection
 - Added Cobra Mk V to data file.
 - Fixed defaulting of new AP.json properties on startup.
 - Added AP engine loop delay until GUI started to prevent error logging to listbox too early.
 - Added detection of ship on startup and on journal change.
 - Added warning of no fuel scoop or autopilot on start and on ship change.
 - Added new callback option of log and voice to try to reduce the redundant logging code.
 - Added journal code to return full ship names.
 - Added journal detection of fuel scoop.
 - Added journal modified date detection to avoid reading journal when it has not changed.
 - Added word replacement for some words that are not pronounced correctly by voice engine.

# 11/27/2024 Stumpii: Various minor changes.
 - Fixed minor issue with interdiction timing that would occasionally cause SCO trigger coming out of interdiction.
 - Added detection of other SC drop locations that do not need a request to dock.
 - Get lower case of ship name as journal is inconsistent in places.


# 11/17/2024 Stumpii: Improved launch from planetary base.
 - Updated Mandalay and Python MkII ship turn values.
 - Set voice enable/disable based on loaded setting. Gets rid of the 'Welcome to' speach if voice disabled.
 - Added improved launch from planetary base. Will now head out 90 deg from planet, SC and SCO until out of orbit.
 - Updated status flags.

# 11/10/2024 Stumpii: Various changes.
 - Added SupercruiseDestinationDrop to determine if we drop at signal source and cannot request docking.
 - Only log journal on change, not every request.
 - Removed logging of statusparser.json file timestamp changes.
 - Added Elite Window check.
 - Added option to screen to allow alternate image for testing.
 - Added a couple of screen functions need for OCR.

# 11/3/2024 Stumpii: Added test buttons for ship calibration.
 - Added test buttons for ship calibration.
 - Updated Mandalay.

# 11/2/2024 Stumpii: Added Mandalay.
 - Added Mandalay.

# 10/28/2024 Stumpii: Minor debug additions.
 - Minor debug additions.

# 10/22/2024 Stumpii: Minor updates.
 - Minor updates.

# 10/20/2024 Stumpii: Added logging.
 - To aid debugging, status bar updates are written to the gui log. Also gui log updates are written to the autopilot log.

# 10/13/2024 Stumpii: Fixed FuelScoop detection.
 - Change fuelscoop detection from ModulesInfo.json to the Journal because ModulesInfo.json was not updated by the game enough to be useful.

# 10/6/2024 Stumpii: Various changes:
 - Added status flags and status parser for processing Status.json file.
 - Change interdiction check to check Status.json instead of Journal and image matching.
 - Added interdiction checks when avoiding sun and fuel scooping.
 - Force module into updates by going to the interior panel before undocking.
 - Updated screen region to use the correct monitor.
 - Added code to allow Python 3.9 and maybe earlier to run correctly with a workaround for the changes that use new features.

# 9/30/2024 Stumpii: Various changes:
 - Added ship type and ship size to the journal and ship status.
 - Added ED_data file for constants.
 - Added ModulesInfoParser to detect if fuel scoop is installed. The other parsers will be added as needed.
 - Removed setting speed to 100% when target lost as this happen when target is in front and causes gravity well message.
 - Removed time delay on SC disengage as it was sometimes too slow and overshooting the station.
 - Detection of monitor > 1 and identify which monitor ED is on.

# 9/10/2024 Updated docs and minor fixes.
 - Stumpii: Correction to mouse click.
 - Stumpii: Add hotkey data entry on GUI for Robigo Assist (Pg Up) which is not shown anywhere.
 - Stumpii: Updated docs.

# 8/20/2024 Added debug options to GUI.
 - Stumpii: Added debug/test tab to GUI.
 - Stumpii: Added debug options and log file open to the GUI to make for easier troubleshooting.

# 8/19/2024 Improved calibration and overlay features.
 - Stumpii: Added Floating Test option to the Overlay class to be able to write text anywhere on the screen.
 - Stumpii: Added Clear method to the Overlay class to clear all overlay items.
 - Stumpii: When overlay checkbox unchecked, overlay now clears. The checkbox said restart required, but that does not appear to be the case.
 - Stumpii: Improved text for calibration popup.
 - Stumpii: When performing calibration, the compass and target regions are shown as well as the current and bast matches.
 - Stumpii: Changed regions test function to display all the regions wanted on the Elite client screen.
 - Stumpii: For regions test, the region name is printed within the region box (the reason floating text was added to the Overlay class).

# 8/18/2024 Cleanup - in prep for additional testing changes.
 - Stumpii: Moved most threshold values to Screen_Regions for consisancy throughout the program and match coded and display values.
 - Stumpii: Cleaned up many comments.
 - Stumpii: Moved the one test routine out to its own file. Added more test routines. These are described in the Test_Routines.py file.

# 8/17/2024 New ships and auto focus
 - Stumpii: Added configs for the two new ships (Python Mk2 and Type-8).
 - Stumpii: Added option to refocus Elite client window before each new key press to avoid sending keys to an unwanted window.

# 6/24/2024 Update
 - Stumpii: Added undocking if necessary to start of supercruise assist.
 - Stumpii: Removed speed demands from the nav alignment code. Nav align should just do the alignment, the calling function determine what to do if alignment is successful or not. All but one of the calling routines sets the speed after calling the routine anyway.
 - Stumpii: sc_assist no longer spams 50% speed every iteration of its loop. So pilot is free to control the speed and just let AP do the alignment. Works great for manual 75% throttle at 0:07 from target and when using new SCO in SC.
 - Stumpii: sc_target_align now returns false if the target was found and now is lost and as no other cause was captured, then we went past the target.
 - Stumpii: While in SC, if we fly past the target, keep going for 5 secs, then slow to 50% and turn around using nav_align.

# 6/23/2024 Targetting update
- Stumpii provided change to Nav Offset to include Z axis where Z=+1 for target ahead and Z=-1 for target behind. Use the data to navigate to the target quicker when the target is behind us (pitch up or down depending if target is above/below us).

# 8/6/23 latest mss library causing crash
- if you are seeing:  AttributeError: '_thread._local' object has no attribute 'srcdc'   then you need to downgrade the mss library.  Updated the requirements.txt file accordingly
- pip install mss==8.0.3

# 6/25/2023 Update by EpicStuff
- Made it so that the state of Enable_CV_View is saved to configs/AP.json and loads previously loaded ship config on start.
also autoformatting (removed trailing whitespaces)

# 12/7/2022 Update
- Update to support ED 4.0 menu layout, so this AP works with both Odyssey and Horizon 4.0
- Waypoint processing, after adding System name in Galaxy Map had to add a Mouse click center screen so that keybindings would work when selecting Plot Route icon
- Robigo had to add a setSpeed50 after coming out of FSD in Sothis.  Still some issues with some users where the Robigo loop cannot find Siruis Atmos in the left menu
- No EDAPGui.exe in this update, if there is a demand for it then will make a formal released version

# 05/30/2022 Update
- V1.1.0 Release which includes EDAPGui.exe.  With the binary, one does not need to install all the python packages

# 05/17/2022 Update
- Added hotkey for starting Robigo as defined in config/AP.json file ("HotKey_StartRobigo": "pgup"). Added ability to only do single loop of Robigo run where user will complete and select missions (see config/AP.json "Robigo_Single_Loop": false)
- With single loop set to True, the Robigo Assist will work in Horizons.
  - CMDR would complete and select Missions, set Route to SOTHIS on GalaxyMap and then start the Robigo AP, which will undock, execute the loop and redock and terminate
  - Additional keybindings are required, see autopilot.log for missing keybindings (such as SelectTarget, Supercruise)

# 05/12/2022 Update
- Added a statemachine to Robigo Mines loop.  Will now determine where your ship is at in the loop and start from there.
  You can then stop the Robigo Assist to handle a Interiction and simply restart it to continue with the loop (it will
  pick up where you left off).  No need to start at Robigo Mines.  See docs/Robigo.md for details

# 05/11/2022 Update
- For Waypoints, the completed state is now updated directly in the wp list.  New option to reset the waypoint completion state via button on the GUI.  The idea is to allow picking up where you left off in your waypoint list.  Also, the loading of a waypoint list has been separated from the activation of the waypoint assist.  (DopeEx is fine tuning the Waypoint system)

# 05/09/2022 Update
- Added the Robigo Mines Passenger Mission autopilot.   See docs/Robigo.md for further details

# 05/07/2022 Update
- Major Gui usability improvements
- Add bookmark as station destination option for waypoints
- If not close enough to the station during the first dock attempt, then another short throttle and reattempt docking request
- Fix missing waypoint assist in ap modes
- Add a new version check and discord and changelog links
- This effort brought to you buy DopeEx

# 05/06/2022 Update - Baselined codebase V1.0

# 05/02/2022 Update - thanks CMDRs for providing these updates
- Fix EDkeys.py to null key modifier if using Secondary binding used (see issue #2)
- Fix AP state to account for undocking from Outposts as opposed to Stations

# 04/28/2022 Update
The goal is to show in the overlay all the info that is needed without having to see the gui or have tts enabled.
The following things have been adjusted:
-	ap mode shows the mode in which the ap is currently running
-	ap status shows the same info as the statusline in the gui (align, maneuver, jump etc.)
-	ship status shows continuously the ship status (before partly in ap mode if no ap mode was active)
-	elw scanner shows if an elw was found

Also, the overlay was sometimes very hard to read, so the default font was changed and the option to change the font itself was added in the config.


# 03/07/2022 Update
- Minor update to the ELW image template to help with accuracy of detection
- Updated the AP.json file and added SunBrightThreshold (set to 125) use to detect Sun in front of ship when jumping into a system
- Updated the code to use the SunBrightThreshold configuration item

# 2/26/2022 Update
- Modified Sun low limit threshold to account for star density when close to core of galaxy
- Enlarged region that looks for Sun in support of sun avoidance
- Fixed jump count total on last jump
- Timing tweaks to account for accasional heating around Sun

# 2/24/2022 Update
- Update to Sun avoidance.  The Sun avoidance looks for brightness at the center of the display to go below 5% to know have pitched
  up sufficiently to go over the Sun.  If close to the core of the galaxy, the star density is high and thus the overall brightness
  of the center of the screen is higher so the ship may continue to pitch further up. Adjusted the brightness criteria to account for this.
  Also, if jumping into a non scoopable star, adjusted the brightness threshold to ensure pitching up/over the Sun works.

# 2/23/2022 Update
- Fixed sun avoidance for dark red/non-scoopable stars, will pitch up properly
- Use different screen grab package (mss) which is about 10x faster than ImageGrab.  New requirements.txt file.
  Must perform:  pip install mss
- The disengage popup "PRESS [J] TO DISENGAGE" image now only looks for "TO DISENGAGE" so user can have any key binding
  they want for that function
- Restructure folder.  Subdirectories now includes:  ships/  configs/  and waypoints/
- Fix issue when Saved Games has been moved out of C:
- Add more useful error for unrecognised key
- Add colour to debug images
- Allow for calibrating of larger screens
- Added Journal trap for interdiction, as well image matching from screen
- Waypoint, fixed undocking from Station


# 2/20/2022 Update
## HOWTO's added:
  - HOWTO-Calibration.md
  - HOWTO-RollPitchYaw.md
  - HOWTO-Waypoint.md

## Configurable Settings
  config-AP.json
    - Aded EnableRandomness flag to adjust sleep times
    - OverlayTextEnable flag to show overlay on ED, prototype
    - OverlayTextYOffset the Y location to put overlay (X hardcoded)
    - OverlayTextFontSize allows you to specify size
    - FuelScoopTimeOut how long to wait in fuel scooping before aborting
    - and others

## Autopilot
  - Added Waypoint Assist  (works both in Odyssey and Horisons)
    - Jumps to Systems defined in waypoints.json (or user selected) file
      - Can dock with a station that is defined in the file also (requires X, Y of mouse to select the
        station from the System Map, this too is a little more complex so see separate HowTo)
        - Added GUI Button "Get X, Y Mouse" to help with determining the StationCoord
      - Once docked can perform trades (somewhat complex to setup, will need separate HowTo), Sells first
        then Buys
      - Auto undock to take you to next waypoint system
      - If last line in the waypoint file is "REPEAT", it will loop to top and do it again, forever, otherwise
        Waypoint assist terminates at the end
  - GUI, in statusline, how shows: Distance Jumped, Jumps/Total Jumps, #Refuels, Sec/Jump
  - GUI, added text field for SunPitchUP+Time (in seconds) which adds this number of seconds after
    sun avoidance to continue pitching up.  If your ship heats up easy (like my Cutter), then you will want
    to add a second or two to be pitch away from the Sun
  - While in SC, check for being interdicted, if so take action (submit, booster away), [initial approach]
  - Optimized number of seconds per jump.   Average just under 60 sec/jump, with fuel scooping once in a while at 70 s/j
  - Added Target Occlusion detection.  As you approach the Station it might suddenly show that
    it is behind the Planet.  This will now be detected and repositioning will occurs to go
    around the planet
  - Tuned color ranges for masking the region for better image template matching.  If using anything other
    than default ED HUD color scheme, this AP will not work at all
  - Handled non FGB FOAM star avoidance when jumping into those Systems (for dim red suns),
    so now won't crashed into those
  - Added journal catch to check if game odyssey, capture distance jumped, jumps remaining
  - Added Galaxy and System Map Open for key binding lookup
  - Added total light years traveled for FSD Route Assist and Waypoint Assit
  - Ship configurations provided that contain the values Roll, Pitch, and Yaw for various type ships
    (Only DBX, APSX, Cutter, and Sidewinder tested)

## Update requirements.txt file
  - One new packages is required to be installed, pynput==1.7.6, to support mouse click
