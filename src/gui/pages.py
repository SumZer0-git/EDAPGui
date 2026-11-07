"""The pages (tabs) of the main window."""

import tkinter as tk

import ttkbootstrap as ttk

from core.version import EDAP_VERSION
from gui.cv_view import CV_VIEWS
from gui.fields import (
    DEFAULT_OVERLAY_LINE_ORDER,
    DSS_BUTTONS,
    FIELDS_BY_KEY,
    LOG_LEVELS,
    OVERLAY_LINES,
    TAB_OVERLAY,
    fields_of,
    move_overlay_line,
    normalize_overlay_line_order,
)
from gui.theme import BLUE, DISABLED, MUTED, ORANGE, PANEL, TEXT
from gui.waypoint_editor import WaypointEditor
from gui.widgets import RoundButton, add_tooltip
from gui.widgets import section_card as _card

TOOLTIPS = {
    "Waypoint List Button": "Read in a file with with your Waypoints.",
    "Reset Waypoint List": "Reset your waypoint list, \nthe waypoint assist will start again at the first point in the list.",
}


def _columns(app, page):
    page.columnconfigure((0, 1), weight=1, uniform="columns")
    columns = []
    for c in range(2):  # independent columns: a tall card never pushes its neighbour down
        column = ttk.Frame(page)
        column.grid(row=0, column=c, sticky="new", padx=(0, app.metrics.u(5)) if c == 0 else (app.metrics.u(5), 0))
        columns.append(column)
    return columns


def _field(app, card, key, row):
    """One labelled input for a setting, depending on its type."""
    field = FIELDS_BY_KEY[key]
    var = app.vars[key]
    pad = app.metrics.u(4)
    if field.kind == "bool":
        check = ttk.Checkbutton(card, text=field.label, variable=var)
        check.grid(row=row, column=0, columnspan=2, sticky="w", pady=pad)
        add_tooltip(check, field.tip)
        return
    label = ttk.Label(card, text=field.label)
    label.grid(row=row, column=0, sticky="w", pady=pad)
    if field.kind in ("int", "float"):
        widget = ttk.Spinbox(card, from_=field.lo, to=field.hi, increment=field.step, textvariable=var, width=7)
        widget.grid(row=row, column=1, sticky="e", pady=pad)
    elif field.kind == "language":
        locale = app.ed_ap.locale
        names = {"auto": "Auto"} | {
            code: f"{locale.language_names[code]} ({code})" for code in locale.available_languages
        }
        display = tk.StringVar(card, value=names.get(var.get(), var.get()))
        widget = ttk.Combobox(card, values=tuple(names.values()), state="readonly", textvariable=display, width=20)
        widget.grid(row=row, column=1, sticky="e", pady=pad)

        def select_language(_event):
            var.set(next(code for code, name in names.items() if name == display.get()))
            app.commit(field.tab)

        widget.bind("<<ComboboxSelected>>", select_language)
    elif field.kind == "choice":
        widget = ttk.Combobox(card, values=field.choices, state="readonly", textvariable=var, width=16)
        widget.grid(row=row, column=1, sticky="e", pady=pad)
    else:
        widget = ttk.Entry(card, textvariable=var, width=12 if field.kind == "hotkey" else 28)
        widget.grid(row=row, column=1, sticky="e", pady=pad)
    widget.bind("<FocusOut>", lambda e: app.commit(field.tab))
    widget.bind("<Return>", lambda e: app.commit(field.tab))
    add_tooltip(label, field.tip)
    add_tooltip(widget, field.tip)


def _choice(app, card, key, label, choices, row):
    """Radio buttons for a setting with a few fixed values."""
    ttk.Label(card, text=label).grid(row=row, column=0, sticky="w", pady=app.metrics.u(4))
    for i, choice in enumerate(choices):
        ttk.Radiobutton(card, text=choice, value=choice, variable=app.vars[key]).grid(
            row=row + i, column=1, sticky="w", pady=app.metrics.u(2)
        )
    return row + len(choices)


def _button(app, card, text, command, row, tip=""):
    button = RoundButton(card, app.metrics, None, text, command, bg=app.theme.surface)
    button.grid(row=row, column=0, columnspan=2, sticky="ew", pady=app.metrics.u(3))
    add_tooltip(button, tip)
    return button


def _save_label(app, page, tab, row=2):
    label = tk.Label(page, bg=app.theme.surface, font=("TkDefaultFont", 9))
    label.grid(row=row, column=0, columnspan=2, sticky="se")
    app.save_labels[tab] = label


def _page_layout(page):
    page.rowconfigure(1, weight=1)


def build_ship(app, page):
    left, right = _columns(app, page)
    card = _card(app, left, "Ship rates")
    for row, field in enumerate(fields_of("Ship")):
        _field(app, card, field.key, row)
    tests = _card(app, right, "Rate tests")
    _button(app, tests, "Test Roll Rate", app.ship_tst_roll, 0)
    _button(app, tests, "Test Pitch Rate", app.ship_tst_pitch, 1)
    _button(app, tests, "Test Yaw Rate", app.ship_tst_yaw, 2)
    _page_layout(page)
    page.rowconfigure(1, weight=0)
    page.rowconfigure(3, weight=1)
    _save_label(app, page, "Ship", row=1)
    _build_log(app, page)


def build_waypoints(app, page):
    app.waypoint_editor = WaypointEditor(app, page)


def build_settings(app, page):
    left, right = _columns(app, page)
    autopilot = _card(app, left, "Autopilot")
    row = 0
    for key in (
        "Language",
        "SunBrightThreshold",
        "NavAlignTries",
        "JumpTries",
        "DockingRetries",
        "WaitForAutoDockTimer",
    ):
        _field(app, autopilot, key, row)
        row += 1
    for key in ("EnableRandomness", "ActivateEliteEachKey", "AutomaticLogout"):
        _field(app, autopilot, key, row)
        row += 1
    fuel = _card(app, left, "Fuel")
    for row, key in enumerate(("RefuelThreshold", "FuelScoopTimeOut", "FuelThreasholdAbortAP")):
        _field(app, fuel, key, row)
    buttons = _card(app, right, "Buttons")
    row = _choice(app, buttons, "DSSButton", "DSS Button", DSS_BUTTONS, 0)
    _field(app, buttons, "HotKey_StartTravel", row)
    _field(app, buttons, "HotKey_StopAllAssists", row + 1)
    voice = _card(app, right, "Voice")
    _field(app, voice, "VoiceEnable", 0)
    _page_layout(page)
    _save_label(app, page, "Settings")


def build_overlay(app, page):
    left, right = _columns(app, page)
    position = _card(app, left, "Overlay position")
    for row, key in enumerate(
        (
            "OverlayTextEnable",
            "OverlayPositionAnchor",
            "OverlayPositionUnit",
            "OverlayTextXOffset",
            "OverlayTextYOffset",
        )
    ):
        _field(app, position, key, row)

    appearance = _card(app, right, "Appearance")
    _field(app, appearance, "OverlayTextFontSize", 0)
    _field(app, appearance, "OverlayTextFontWeight", 1)
    _field(app, appearance, "OverlayPanelOpacity", 2)

    visible = _card(app, right, "Visible information")
    _overlay_lines(app, visible)

    _page_layout(page)
    _save_label(app, page, TAB_OVERLAY)


def _overlay_lines(app, card):
    """Checkbox per overlay line with arrows to change the line order."""
    order_var = app.vars["OverlayLineOrder"]
    pad = app.metrics.u(2)
    rows = {}

    def arrow(text, key, step):
        label = tk.Label(card, text=text, bg=app.theme.surface, cursor="hand2", font=("TkDefaultFont", 9))
        label.bind("<Button-1>", lambda e: move(key, step))
        label.bind("<Enter>", lambda e: label.cget("fg") == MUTED and label.configure(fg=ORANGE))
        label.bind("<Leave>", lambda e: label.cget("fg") == ORANGE and label.configure(fg=MUTED))
        return label

    for key, setting in OVERLAY_LINES:
        field = FIELDS_BY_KEY[setting]
        check = ttk.Checkbutton(card, text=field.label, variable=app.vars[setting])
        add_tooltip(check, field.tip)
        rows[key] = (check, arrow("▲", key, -1), arrow("▼", key, 1))

    def layout():
        order = normalize_overlay_line_order(order_var.get())
        last = len(order) - 1
        for index, key in enumerate(order):
            check, up, down = rows[key]
            check.grid(row=index, column=0, sticky="w", pady=pad)
            up.grid(row=index, column=1, padx=(app.metrics.u(8), app.metrics.u(2)))
            down.grid(row=index, column=2)
            up.configure(fg=DISABLED if index == 0 else MUTED)
            down.configure(fg=DISABLED if index == last else MUTED)

    def move(key, step):
        order = move_overlay_line(order_var.get(), key, step)
        if order != normalize_overlay_line_order(order_var.get()):
            order_var.set(",".join(order))
            layout()

    def reset():
        order_var.set(",".join(DEFAULT_OVERLAY_LINE_ORDER))
        layout()

    layout()
    reset_button = _button(app, card, "Reset order", reset, len(rows), "Restore the default line order.")
    reset_button.grid_configure(columnspan=3, pady=(app.metrics.u(12), app.metrics.u(3)))


def _build_log(app, page):
    """The one and only log view, below the ship rates."""
    u = app.metrics.u
    title = tk.Label(page, text="Log", fg=BLUE, bg=app.theme.surface, font=("TkDefaultFont", 10, "bold"))
    frame = ttk.LabelFrame(page, labelwidget=title, padding=u(12))
    frame.grid(row=3, column=0, columnspan=2, sticky="nsew")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    app.log_text = tk.Text(frame, bg=PANEL, fg=TEXT, relief="flat", wrap="none", state="disabled", height=10)
    app.log_text.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(frame, command=app.log_text.yview, bootstyle="secondary-round")
    scrollbar.grid(row=0, column=1, sticky="ns")
    app.log_text.configure(yscrollcommand=scrollbar.set)
    app.fill_log()


def build_debug(app, page):
    left, right = _columns(app, page)
    logging_card = _card(app, left, "Logging")
    row = _choice(app, logging_card, "log_level", "Log level", LOG_LEVELS, 0)
    _field(app, logging_card, "DebugOverlay", row)
    _button(app, logging_card, "Open Log File", app.open_logfile, row + 1)
    cv_card = _card(app, left, "CV Views")
    for row, (name, title) in enumerate(CV_VIEWS.items()):
        _button(app, cv_card, title, lambda name=name: app.cv_view.open_view(name), row)

    single = _card(app, right, "Single Waypoint Assist")
    for row, (text, var) in enumerate(
        (("System", app.single_waypoint_system), ("Station", app.single_waypoint_station))
    ):
        ttk.Label(single, text=text).grid(row=row, column=0, sticky="w", pady=app.metrics.u(4))
        ttk.Entry(single, textvariable=var, width=28).grid(row=row, column=1, sticky="e", pady=app.metrics.u(4))
    ttk.Checkbutton(
        single, text="Single Waypoint Assist", variable=app.swp_var, command=app.toggle_single_waypoint
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=app.metrics.u(4))
    link = tk.Label(
        single, text="Trade Computer Extension (TCE)", fg=ORANGE, bg=app.theme.surface, cursor="hand2", anchor="w"
    )
    link.bind(
        "<Button-1>",
        lambda e: app.open_url("https://forums.frontier.co.uk/threads/trade-computer-extension-mk-ii.223056/"),
    )
    link.grid(row=3, column=0, columnspan=2, sticky="w", pady=app.metrics.u(4))
    _field(app, single, "TCEDestinationFilepath", 4)
    _button(app, single, "Load TCE Destination", app.load_tce_dest, 5)
    _page_layout(page)
    _save_label(app, page, "Debug")


def build_info(app, page):
    left, right = _columns(app, page)
    about = _card(app, left, "About")
    ttk.Label(about, text=f"EDAutopilot {EDAP_VERSION}").grid(row=0, column=0, sticky="w", pady=app.metrics.u(4))
    _button(app, about, "Open GitHub Page", app.about, 1)
    _button(app, about, "View Changelog", app.open_changelog, 2)

    updates_card = _card(app, right, "Updates")
    ttk.Label(updates_card, textvariable=app.update_text).grid(row=0, column=0, sticky="w", pady=app.metrics.u(4))
    _button(app, updates_card, "Check for Updates", app.check_updates, 1)
    app.download_button = _button(app, updates_card, "Download Update", app.open_download, 2)
    app.refresh_update_button()

    program = _card(app, right, "Program")
    _button(app, program, "Restart", app.restart_program, 0)
    _button(app, program, "Exit", app.close_window, 1)
    _page_layout(page)


PAGES = (
    ("Ship", build_ship),
    ("Waypoints", build_waypoints),
    ("Overlay", build_overlay),
    ("Settings", build_settings),
    ("Debug", build_debug),
    ("Info", build_info),
)
