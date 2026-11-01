# Project structure

Where things belong. When adding a file, pick the folder by what the code *does*, not by who calls it.

```
start_ed_ap.bat         Start script for users (creates the venv on first start and runs src/main.py).
install_requirements.bat  Creates the venv and installs requirements.txt.
requirements.txt        Python dependencies.
requirements-dev.txt    Development tools (Ruff). Install: pip install -r requirements-dev.txt
pyproject.toml          Ruff configuration. Check the code with: ruff check .
README.md, CHANGELOG.md, LICENSE

src/                    All program code (this is the import root; run the program with python src/main.py)
  main.py                 Start script. Only calls gui.main_window.main().

  core/                   Application core, no game or GUI knowledge beyond the autopilot itself
    autopilot.py            EDAutopilot class: setup, engine loop, setters (composed from the mixins below)
    config.py               Reading/writing AP.json and ship_configs.json (ConfigMixin)
    paths.py                Single source of all file paths; creates and seeds user_data/. Never hardcode paths elsewhere
    logger.py               Logging setup and log rotation
    constants.py            Shared constants and game data tables
    types.py                Shared exceptions and enums

  vision/                 Everything that looks at the screen
    screen.py, regions.py   Screen capture, resolution handling, screen regions
    templates.py            Template image loading (images are in assets/templates/)
    ocr.py                  Text recognition
    calibration.py          Calibration of the template matching scale (CalibrationMixin)
    detection.py            Detection of target, compass, supercruise state (DetectionMixin)

  controls/               Everything that sends input to the game
    keys.py                 EDKeys: sends keys bound in the game
    directinput.py          Low level DirectInput key codes and key presses
    mouse_point.py          Mouse position and clicks

  game/                   Reading data from Elite Dangerous (files written by the game)
    journal.py, status.py, cargo.py, market.py, nav_route.py   Journal and status file parsers
    keybindings.py          KeyBindings: reads the game's keybinding file
    graphics_settings.py, known_paths.py   Game settings and Windows folder lookup

  panels/                 In-game UI panels that are operated through the screen (one file per panel)
  routines/               Flight behavior and complete workflows
    flight.py               Maneuvers: align, jump, dock, refuel (FlightMixin)
    assists.py              FSD, SC, waypoint, Robigo, AFK combat, DSS assists (AssistsMixin)
    waypoints.py, robigo.py, afk_combat.py   Self-contained routines

  integrations/           Connections to things outside the game
    voice.py, tce.py        Voice output, Trade Computer Extension
    edmesg/                 EDMesg interface, client and server (the EDMesg library itself is in third_party/)

  gui/                    Tkinter user interface
    main_window.py          Main window and its callbacks
    overlay.py              Screen overlay

  i18n/                   Localization code (the language files are in assets/locales/)

assets/                 Static files shipped with the program
  templates/              Template images for matching
  locales/                Language files (en.json, de.json, ...)
  icons/                  Icons

data/                   Reference files that are copied to user_data/ when missing
  configs/                resolution.json
  waypoints/              Example waypoint files

user_data/              Created at runtime, not in git: configs/, waypoints/, logs/, debug/
docs/                   Documentation (screenshots in docs/screenshots/)
third_party/           Unmodified third-party libraries (EDMesg). Not linted; added to the import path by integrations/edmesg/__init__.py
tests/                  Unit tests (tests/test_*.py), fixtures/ for test images,
                        integration/ for tests that need the running game (set EDAP_INTEGRATION=1),
                        manual/ for debug tools
.github/                Workflows and project settings
```

## Rules

- File and folder names are lowercase `snake_case`; the only exceptions are root files like `README.md`, `CHANGELOG.md` and `LICENSE`.
- Do not put new Python modules into the project root. Every module belongs into one of the packages in `src/`.
- Imports are relative to `src/` (for example `from core.logger import logger`). Do not edit files in `third_party/`.
- Paths come from `core/paths.py`. Files the program writes go to `user_data/`, never next to the code.
- Dependencies point downwards: `gui` and `routines` may use `panels`, `vision`, `controls`, `game` and `core`; `core`, `vision`, `controls` and `game` must not import from `gui` or `routines`. Import `core.autopilot` only inside a function if you need the autopilot from a lower layer, to avoid circular imports.
- New tests go to `tests/`. Tests that need the running game go to `tests/integration/`.
- Do not use `from x import *` in new code; import the names you need.
- Changes to structure or user-visible behavior get an entry in `CHANGELOG.md` under "Unreleased".
