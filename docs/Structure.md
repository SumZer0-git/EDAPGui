# Project structure

Use this tree as a codebase index. Place changes where the behavior belongs, not in whichever module happens to call it.

```text
EDAPGui/
|-- start_ed_ap.bat                 # Set up the environment and start the application
|-- install_requirements.bat        # Install runtime dependencies in the private environment
|-- fix_keybinds.bat                # Launch the Elite Dangerous keybinding fixer
|-- requirements.txt                # Runtime dependencies
|-- requirements-dev.txt            # Local development tools
|-- requirements-ci.txt             # Slim dependencies for CI
|-- pyproject.toml                  # Ruff configuration
|-- README.md                       # Project overview and getting started
|-- CHANGELOG.md                    # Unreleased changes and release history
|-- LICENSE                         # Project license
|-- src/
|   |-- main.py                     # Application entry point
|   |-- fix_keybinds.py             # CLI for the game keybinding fixer
|   |-- core/
|   |   |-- autopilot.py            # App state, assist loop, and coordination
|   |   |-- config.py               # Read and write app and ship configuration
|   |   |-- paths.py                # Central paths and user-data initialization
|   |   |-- logger.py               # Logging setup and log rotation
|   |   |-- constants.py            # Shared flags, ship data, and reference tables
|   |   |-- types.py                # Shared enums and exceptions
|   |   |-- version.py              # Single source for the app version
|   |   |-- updates.py              # Check GitHub for application updates
|   |   `-- __init__.py             # Package marker
|   |-- vision/
|   |   |-- screen.py               # Capture the game display and manage focus
|   |   |-- regions.py              # Screen regions, filters, and match helpers
|   |   |-- templates.py            # Load and scale image templates
|   |   |-- ocr.py                  # Recognize text with PaddleOCR
|   |   |-- detection.py             # Detect targets, compass, and SC state
|   |   `-- __init__.py             # Package marker
|   |-- controls/
|   |   |-- keys.py                 # Send actions using game keybindings
|   |   |-- directinput.py          # Low-level DirectInput key events
|   |   |-- mouse_point.py          # Capture mouse coordinates and click
|   |   `-- __init__.py             # Package marker
|   |-- game/
|   |   |-- journal.py              # Parse journal events and derived ship state
|   |   |-- status.py               # Parse Status.json and expose game flags
|   |   |-- cargo.py                # Parse Cargo.json
|   |   |-- market.py               # Parse Market.json
|   |   |-- nav_route.py            # Parse NavRoute.json
|   |   |-- graphics_settings.py    # Read game display and graphics settings
|   |   |-- known_paths.py          # Locate Windows game-data folders
|   |   |-- binds_files.py          # Find active .binds files and presets
|   |   |-- keybindings.py          # Read actions from active game bindings
|   |   |-- keybind_spec.py         # Define required actions and fixer rules
|   |   |-- keybind_defaults.py     # Generated keys from shipped game presets
|   |   |-- keybind_fixer.py        # Plan and apply game-binding changes
|   |   `-- __init__.py             # Package marker
|   |-- panels/
|   |   |-- navigation.py           # Operate the left Navigation panel
|   |   |-- galaxy_map.py           # Operate Galaxy Map selection
|   |   |-- system_map.py           # Operate System Map selection
|   |   |-- internal_status.py      # Operate the right-hand status panel
|   |   |-- station_services.py     # Navigate station services
|   |   |-- ship_control.py         # Change cockpit and ship-control views
|   |   `-- __init__.py             # Package marker
|   |-- routines/
|   |   |-- flight.py               # Alignment, jumps, docking, and refueling
|   |   |-- assists.py              # FSD, SC, DSS, and single-waypoint assists
|   |   |-- waypoints.py            # Waypoint progress, visits, and trade actions
|   |   |-- afk_combat.py           # AFK combat evasion and fighter actions
|   |   `-- __init__.py             # Package marker
|   |-- gui/
|   |   |-- main_window.py          # Main window: sidebar, modes, tabs, autosave, callbacks
|   |   |-- pages.py                # Builders for the Ship (with the log), Waypoints, Settings, Debug, and Info tabs
|   |   |-- fields.py               # Settings model (labels, limits, storage); no Tk, unit tested
|   |   |-- theme.py                # Dark palette, DPI scaling, and native title bar helpers
|   |   |-- widgets.py              # Rounded buttons and tooltips
|   |   |-- window_state.py         # Remembers window position, collapsed state, and always-on-top
|   |   |-- overlay.py              # Optional on-screen overlay
|   |   `-- __init__.py             # Package marker
|   |-- integrations/
|   |   |-- voice.py                # Optional spoken feedback
|   |   |-- tce.py                  # Trade Computer Extension integration
|   |   `-- __init__.py             # Package marker
|   `-- i18n/
|       |-- localization.py         # Load and access localized strings
|       `-- __init__.py             # Package marker
|-- assets/
|   |-- templates/                  # Images used for screen matching
|   |-- locales/                    # English and German language files
|   |-- icons/                      # Application icons
|   `-- keybind_presets/            # Shipped game presets for generated defaults
|-- data/
|   |-- configs/                    # Reference configuration copied on first start
|   `-- waypoints/                  # Example waypoint files
|-- user_data/                      # Runtime config, waypoints, logs, and debug output
|-- tools/
|   |-- make_keybind_defaults.py    # Generate game keybinding defaults
|   `-- make_templates.py           # Generate templates from local screenshots
|-- tests/
|   |-- helpers.py                  # Shared test helpers
|   |-- test_changelog.py           # Changelog format tests
|   |-- test_detection.py           # Screen detection tests
|   |-- test_flight.py              # Flight routine tests
|   |-- test_journal.py             # Journal parsing tests
|   |-- test_keybindings.py         # Game binding parser tests
|   |-- test_keybind_fixer.py       # Binding fixer tests
|   |-- test_logger.py              # Logging tests
|   |-- test_market_cargo.py        # Market and cargo parser tests
|   |-- test_ocr.py                 # OCR tests
|   |-- test_regions.py             # Screen-region tests
|   |-- test_resources.py           # Localization and resource tests
|   |-- test_screenshots.py         # Optional full-screen regression tests
|   |-- test_status.py              # Status parser tests
|   |-- test_updates.py             # Update-check tests
|   |-- test_version.py             # Version tests
|   |-- test_waypoints.py           # Waypoint loading and progress tests
|   |-- fixtures/                   # Test data and image crops
|   |-- integration/                # Tests requiring game/UI integration
|   `-- manual/                     # Manual and debugging utilities
|-- docs/
|   |-- Keybindings.md              # Required game bindings and fixer guide
|   |-- RollPitchYaw.md             # Per-ship rotation-rate tuning
|   |-- Structure.md                # This codebase index and its conventions
|   |-- Waypoint.md                 # Waypoint format and supported actions
|   |-- Workflows.md                # Current assist behavior and follow-up items
|   `-- screenshots/                # Images used in user documentation
`-- .github/
    `-- workflows/
        |-- ci.yml                  # Lint and test pull requests and pushes
        `-- release.yml             # Validate and publish tagged releases
```

Generated files such as `src/game/keybind_defaults.py` should be regenerated with
`tools/make_keybind_defaults.py`, not edited by hand. Raw full-screen game screenshots in
`tests/fixtures/screenshots/` are local-only and must not be committed.

## Conventions and boundaries

- Python source belongs under `src/`, in the package that owns its behavior.
- `gui/` handles the desktop interface; it does not implement flight routines.
- `panels/` automates in-game interfaces; it does not own general flight policy.
- `vision/` interprets screen data; it does not navigate panels or choose workflows.
- `controls/` sends input; it does not implement game or assist workflows.
- `game/` parses game data and bindings; it does not perform screen automation.
- `routines/` coordinates game state, panels, vision, and controls.
- Lower-level packages must not import `gui/` or `routines/`.
- Resolve application file paths through `core/paths.py`; keep runtime data in `user_data/`.
- Keep shipped defaults in `data/` or `assets/`; do not store them with runtime output.
- Use lowercase `snake_case` for new Python modules and folders; avoid wildcard imports.
- Add user-visible changes to the `Unreleased` section of `CHANGELOG.md`.

## Documentation map

- [README](../README.md): project overview and getting started.
- [Keybindings](Keybindings.md): required Elite Dangerous actions and the fixer.
- [Waypoint Assist](Waypoint.md): waypoint file format and supported workflows.
- [Assist workflows](Workflows.md): current assist behavior and follow-up items.
- [Ship tuning](RollPitchYaw.md): calibrating per-ship rotation rates.
