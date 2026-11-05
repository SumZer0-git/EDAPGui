"""Main window for controlling the ED Autopilot.

Ideas taken from: https://github.com/skai2/EDAutopilot"""

import json
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path
from time import sleep
from tkinter import filedialog as fd
from tkinter import messagebox

import keyboard
import ttkbootstrap as ttk

from controls.hotkeys import ActionQueue, HotkeyListener
from controls.mouse_point import MousePoint
from core import paths, updates
from core.autopilot import EDAutopilot
from core.logger import logger
from core.version import EDAP_VERSION
from gui import fields, window_state
from gui.fields import FIELDS, TAB_OVERLAY, fields_of
from gui.pages import PAGES
from gui.theme import (
    BG,
    GREEN,
    MUTED,
    ORANGE,
    PANEL,
    RED,
    TEXT,
    YELLOW,
    Metrics,
    Theme,
    dark_titlebar,
    enable_dpi_awareness,
    min_caption_width,
    remove_maximize,
    window_dpi,
)
from gui.widgets import RoundButton, add_tooltip

MODES = (
    ("travel", "Travel Assist"),
    ("waypoint", "Waypoint Assist"),
    ("afk", "AFK Combat Assist"),
    ("dss", "DSS Assist"),
)
MODE_KEYS = {key for key, _ in MODES}
SAVE_TABS = ("Ship", "Settings", TAB_OVERLAY, "Debug")
SAVE_TEXT = {
    "saved": ("\u2713 Saved", GREEN),
    "dirty": ("\u25cf Unsaved changes", YELLOW),
    "error": ("\u2715 Not saved", RED),
}
SAVE_DELAY_MS = 800
SAVED_FADE_MS = 3000

# Window size in logical pixels; 1000 fits next to other windows on a portrait 1080p monitor
WINDOW_WIDTH = 820
WINDOW_HEIGHT = 650
COLLAPSED_HEIGHT = 392
SIDEBAR_WIDTH = 200
OUTER_PAD = 10


def hyperlink_callback(url):
    webbrowser.open_new(url)


class APGui:
    def __init__(self, root, ed_ap=None, services=True):
        """ed_ap and services exist for tests: they allow a stand-in autopilot and no hotkeys or update check."""
        self.root = root
        root.title("EDAutopilot")
        root.protocol("WM_DELETE_WINDOW", self.close_window)
        root.configure(bg=BG)

        self.metrics = Metrics(root)
        self.theme = Theme(root, self.metrics)

        self.gui_loaded = False
        self.log_lines = deque(maxlen=2000)
        self.log_text = None
        self.ui_queue = queue.Queue()  # messages from other threads, handled by the GUI thread
        self.notify_user(f"Starting ED Autopilot {EDAP_VERSION}.")

        self.ed_ap = ed_ap if ed_ap is not None else EDAutopilot(cb=self.callback)
        self.mouse = MousePoint()
        self.hotkeys = None
        self.active_hotkeys = {}
        self.hotkey_poll_id = None

        self.single_waypoint_system = tk.StringVar()
        self.single_waypoint_station = tk.StringVar()
        self.swp_var = tk.BooleanVar()
        waypoint = getattr(self.ed_ap, "waypoint", None)
        if waypoint is not None and getattr(waypoint, "route_loaded", False):
            waypoint_label = "loaded: " + Path(waypoint.filename).name
        else:
            waypoint_label = "<no list loaded>"
        self.wp_filelabel = tk.StringVar(value=waypoint_label)
        self.update_text = tk.StringVar(value="Not checked yet.")
        self.update_tag = None
        self.download_button = None

        self.TRAVEL_A_running = False
        self.WP_A_running = False
        self.DSS_A_running = False
        self.SWP_A_running = False
        self.active_mode = None

        self.vars = {}
        self.applied = {}
        self._loading = False
        self.save_state = {tab: "saved" for tab in SAVE_TABS}
        self.save_faded = {tab: True for tab in SAVE_TABS}
        self._fade_jobs = {}
        self.save_labels = {}
        self._save_jobs = {}
        for field in FIELDS:
            self.vars[field.key] = tk.BooleanVar() if field.kind == "bool" else tk.StringVar()
        self.load_vars()
        for field in FIELDS:
            self.vars[field.key].trace_add("write", lambda *args, f=field: self._on_var(f))

        self.state = window_state.load()
        self.collapsed = self.state["collapsed"]
        self.pinned = self.state["topmost"]
        self.status_text = "Idle"
        self.route_text = ""
        self.status = None
        self.route_info = None
        self.tab_index = 0
        root.attributes("-topmost", self.pinned)

        root.update_idletasks()
        self._dpi = window_dpi(root)
        self.metrics.set_dpi(self._dpi)
        self.theme.apply()
        self._build_all()
        dark_titlebar(root)
        remove_maximize(root)
        self._restore_position()
        root.bind("<Configure>", self._on_configure)

        if services:
            self.hotkey_actions = ActionQueue()
            self.hotkeys = HotkeyListener(keyboard)
            # Hotkeys are only registered at startup, so the tooltips show these and not later edits.
            self.active_hotkeys = {
                "stop": self.ed_ap.config["HotKey_StopAllAssists"],
                "travel": self.ed_ap.config["HotKey_StartTravel"],
            }
            self.hotkeys.add_hotkey(self.active_hotkeys["stop"], lambda: self.hotkey_actions.put(self.stop_all_assists))
            self.hotkeys.add_hotkey(
                self.active_hotkeys["travel"],
                lambda: self.hotkey_actions.put(lambda: self.callback("travel_start", None)),
            )
            self.hotkeys.start()
            self._refresh_modes()
            self.hotkey_poll_id = self.root.after(50, self.process_hotkey_actions)
            self.check_updates(manual=False)

        self.gui_loaded = True
        self.ed_ap.gui_loaded = True
        self.notify_user("ED Autopilot loaded successfully.")

    # window layout

    def _build_all(self):
        """Create all widgets. State lives in the Tk variables and attributes of this class, so it survives a rebuild."""
        u = self.metrics.u
        if hasattr(self, "waypoint_editor"):
            self.waypoint_form_state = self.waypoint_editor.form_state()
        for child in self.root.winfo_children():
            child.destroy()
        self.save_labels = {}
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_content()
        self.statusbar = ttk.Frame(self.root)
        self.statusbar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=u(OUTER_PAD), pady=(0, u(4)))
        self.statusbar.columnconfigure((0, 2), weight=1, uniform="footer")
        self.status = ttk.Label(self.statusbar, text=self.status_text, padding=(u(4), u(2)), foreground=MUTED)
        self.status.grid(row=0, column=0, sticky="w")
        self.route_info = ttk.Label(self.statusbar, text=self.route_text, padding=(u(4), u(2)), foreground=MUTED)
        self.route_info.grid(row=0, column=1)
        right = ttk.Frame(self.statusbar)
        right.grid(row=0, column=2, sticky="e")
        self.update_label = ttk.Label(
            right, padding=(u(4), u(2)), foreground=ORANGE, cursor="hand2", font="TkDefaultFont"
        )
        self.update_label.grid(row=0, column=0, padx=(0, u(12)))
        self.update_label.bind("<Button-1>", lambda e: self._open_info_tab())
        self._show_update_notice()
        ttk.Label(right, text=EDAP_VERSION, padding=(u(4), u(2)), foreground=MUTED).grid(row=0, column=1)
        self._apply_layout()
        self._refresh_modes()

    def _build_sidebar(self):
        u = self.metrics.u
        self.sidebar = tk.Frame(self.root, bg=PANEL)
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(u(OUTER_PAD), u(5)), pady=(u(OUTER_PAD), u(5)))
        self.sidebar.grid_propagate(False)
        self.sidebar.pack_propagate(False)
        tk.Frame(self.sidebar, bg=PANEL, height=u(8)).pack()
        self.items = {}
        self.mode_tips = {}
        self.mode_labels = dict(MODES)
        for key, label in MODES:
            button = RoundButton(self.sidebar, self.metrics, key, label, lambda k=key: self._mode_clicked(k))
            button.pack(fill="x", padx=u(8), pady=u(2))
            self.items[key] = button
            self.mode_tips[key] = add_tooltip(button, label)
        self.stop_button = RoundButton(
            self.sidebar, self.metrics, "stop", "Stop All", self.stop_all_assists, danger=True
        )
        self.stop_button.pack(fill="x", padx=u(8), pady=(u(14), u(2)))
        self.stop_tip = add_tooltip(self.stop_button, "Stop All")
        self.bottom = tk.Frame(self.sidebar, bg=PANEL)
        self.bottom.pack(side="bottom", fill="x", pady=u(8))
        self.pin = RoundButton(self.bottom, self.metrics, "pin", command=self.toggle_pin, framed=False)
        self.power = RoundButton(self.bottom, self.metrics, "power", command=self._power_menu, framed=False)
        self.fold = RoundButton(self.bottom, self.metrics, "left", command=self.toggle_collapse, framed=False)
        self.pin.active = self.pinned
        self.menu = tk.Menu(
            self.root, tearoff=0, bg=PANEL, fg=TEXT, activebackground=ORANGE, activeforeground=TEXT, bd=0
        )
        self.menu.add_command(label="Restart", command=self.restart_program)
        self.menu.add_command(label="Exit", command=self.close_window)
        for widget in (self.sidebar, self.bottom):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)

    def _layout_bottom(self):
        u = self.metrics.u
        buttons = (self.pin, self.power, self.fold)
        for button in buttons:
            button.grid_forget()
        for i, button in enumerate(buttons):
            if self.collapsed:
                button.grid(row=i, column=0, sticky="ew", pady=u(3), padx=u(8))
            else:
                button.grid(row=0, column=i, sticky="ew", padx=u(3))
        for c in range(3):
            self.bottom.columnconfigure(c, weight=1 if (not self.collapsed or c == 0) else 0)

    def _build_content(self):
        u = self.metrics.u
        self.content = ttk.Frame(self.root)
        self.content.grid(row=0, column=1, sticky="nsew", padx=(u(5), u(OUTER_PAD)), pady=(u(OUTER_PAD), u(5)))
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self.tabs = ttk.Notebook(self.content)
        self.tabs.grid(row=0, column=0, sticky="nsew")
        for name, build in PAGES:
            page = ttk.Frame(self.tabs, padding=(0, u(OUTER_PAD), 0, 0))
            self.tabs.add(page, text=name)
            build(self, page)
        for tab, label in self.save_labels.items():
            self._show_save(tab, label)
        self.tabs.select(self.tab_index)
        self.tabs.bind("<<NotebookTabChanged>>", lambda e: setattr(self, "tab_index", self.tabs.index("current")))

    def _show_update_notice(self):
        if self.update_tag:
            self.update_label.configure(text=f"Update available: {self.update_tag}")
            self.update_label.grid()
        else:
            self.update_label.grid_remove()

    def _open_info_tab(self):
        self.tabs.select(len(PAGES) - 1)

    def _set_size(self, width, height):
        self.root.minsize(1, 1)
        self.root.maxsize(width, height)
        self.root.minsize(width, height)
        self.root.geometry(f"{width}x{height}")

    def _apply_layout(self):
        """Switch between the full window and the narrow icon strip. The size is fixed in both states."""
        px, u = self.metrics.px, self.metrics.u
        if self.collapsed:
            self.content.grid_remove()
            self.statusbar.grid_remove()
            width = min_caption_width(self.root)
            self.root.columnconfigure(0, weight=1)
            self.root.columnconfigure(1, weight=0)
            self.sidebar.configure(width=width - 2 * px(OUTER_PAD))
            self.sidebar.grid(sticky="nsew", padx=u(OUTER_PAD))
            self._set_size(width, px(COLLAPSED_HEIGHT))
        else:
            self.content.grid()
            self.statusbar.grid()
            self.root.columnconfigure(0, weight=0)
            self.root.columnconfigure(1, weight=1)
            self.sidebar.configure(width=px(SIDEBAR_WIDTH))
            self.sidebar.grid(sticky="ns", padx=(u(OUTER_PAD), u(5)))
            self._set_size(px(WINDOW_WIDTH), px(WINDOW_HEIGHT))
        self._layout_bottom()
        self.fold.set_icon("right" if self.collapsed else "left")
        for item in (*self.items.values(), self.stop_button):
            item.set_icon_only(self.collapsed)
        for item in (self.pin, self.power, self.fold):
            item.redraw()

    def toggle_collapse(self):
        self.collapsed = not self.collapsed
        self._apply_layout()

    def toggle_pin(self):
        self.pinned = not self.pinned
        self.pin.set_active(self.pinned)
        self.root.attributes("-topmost", self.pinned)

    def _power_menu(self):
        self.menu.tk_popup(self.power.winfo_rootx() + self.power.winfo_width(), self.power.winfo_rooty())

    def _drag_start(self, event):
        self._drag = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag_move(self, event):
        self.root.geometry(f"+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}")

    def _restore_position(self):
        x, y = self.state["x"], self.state["y"]
        if x is None or y is None:
            return
        left, top = self.root.winfo_vrootx(), self.root.winfo_vrooty()
        width, height = self.root.winfo_vrootwidth(), self.root.winfo_vrootheight()
        if left <= x < left + width - 100 and top <= y < top + height - 100:
            self.root.geometry(f"+{x}+{y}")

    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        dpi = window_dpi(self.root)
        if dpi != self._dpi:
            self._dpi = dpi
            self.root.after(10, self._rescale)

    def _rescale(self):
        """The window moved to a monitor with another scaling: rebuild everything at the new size."""
        self.metrics.set_dpi(self._dpi)
        self.theme.apply()
        self._build_all()

    # tab content helpers used by gui.pages

    def fill_log(self):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", "\n".join(self.log_lines) + ("\n" if self.log_lines else ""))
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def open_url(self, url):
        hyperlink_callback(url)

    def refresh_update_button(self):
        if self.download_button is not None and self.download_button.winfo_exists():
            self.download_button.set_disabled(not self.update_tag)

    # settings: loading, autosave

    def load_vars(self, tab=None):
        """Show the values the autopilot currently has."""
        self._loading = True
        try:
            for field in FIELDS:
                if tab is not None and field.tab != tab:
                    continue
                value = fields.read(field, self.ed_ap)
                self.vars[field.key].set(value)
                try:
                    self.applied[field.key] = fields.parse(field, value)
                except ValueError:
                    self.applied[field.key] = None
        finally:
            self._loading = False

    def _on_var(self, field):
        if self._loading:
            return
        self._set_save(field.tab, "dirty")
        self._cancel_save_job(field.tab)
        delay = 1 if field.kind in ("bool", "choice", "order") else SAVE_DELAY_MS
        self._save_jobs[field.tab] = self.root.after(delay, lambda: self.commit(field.tab))

    def _cancel_save_job(self, tab):
        job = self._save_jobs.pop(tab, None)
        if job is not None:
            self.root.after_cancel(job)

    def commit(self, tab):
        """Check the values of a tab and, if all are valid, apply them and write the configuration."""
        self._cancel_save_job(tab)
        if self.save_state.get(tab) == "saved":
            return
        tab_fields = fields_of(tab)
        try:
            parsed = {field.key: fields.parse(field, self.vars[field.key].get()) for field in tab_fields}
            if tab == TAB_OVERLAY:
                self._convert_overlay_offsets(parsed)
            fields.validate_tab(tab, parsed)
        except (ValueError, tk.TclError) as e:
            logger.debug(f"Settings not saved: {e}")
            self._set_save(tab, "error")
            return
        try:
            changed = False
            pos = (self.root.winfo_x() + self.root.winfo_width() + 4, self.root.winfo_y())
            for field in tab_fields:
                if self.applied.get(field.key) != parsed[field.key]:
                    fields.write(field, self.ed_ap, parsed[field.key], pos)
                    self.applied[field.key] = parsed[field.key]
                    changed = True
            if changed:
                if tab == TAB_OVERLAY:
                    self.ed_ap.apply_overlay_config()
                if tab == "Ship":
                    self.ed_ap.update_ship_configs()
                else:
                    self.ed_ap.update_config()
        except Exception as e:
            logger.warning(f"Settings of tab {tab} could not be saved: {e}")
            self._set_save(tab, "error")
            return
        self._set_save(tab, "saved")

    def _convert_overlay_offsets(self, values):
        converted_keys = fields.convert_overlay_offsets(
            values,
            self.applied,
            self.ed_ap.scr.screen_width,
            self.ed_ap.scr.screen_height,
        )
        self._loading = True
        try:
            for key in converted_keys:
                self.vars[key].set(str(values[key]))
        finally:
            self._loading = False

    def _set_save(self, tab, state):
        self.save_state[tab] = state
        self.save_faded[tab] = False
        job = self._fade_jobs.pop(tab, None)
        if job:
            self.root.after_cancel(job)
        if state == "saved":
            self._fade_jobs[tab] = self.root.after(SAVED_FADE_MS, lambda: self._fade_save(tab))
        label = self.save_labels.get(tab)
        if label is not None and label.winfo_exists():
            self._show_save(tab, label)

    def _fade_save(self, tab):
        self._fade_jobs.pop(tab, None)
        self.save_faded[tab] = True
        label = self.save_labels.get(tab)
        if label is not None and label.winfo_exists():
            self._show_save(tab, label)

    def _show_save(self, tab, label):
        text, color = SAVE_TEXT[self.save_state[tab]]
        if self.save_faded.get(tab):
            text = ""
        label.configure(text=text, fg=color)

    # callback from the EDAP, to configure GUI items
    def callback(self, msg, body=None):
        if threading.current_thread() is not threading.main_thread():
            self.ui_queue.put((msg, body))
            return
        if msg == "log":
            self.notify_user(body)
        elif msg == "log+vce":
            self.notify_user(body, speak=True)
        elif msg == "user_message":
            message, speak = body
            self.notify_user(message, speak=speak)
        elif msg == "ap_status":
            self.update_statusline(body)
        elif msg == "single_waypoint_stop":
            logger.debug("Detected 'single_waypoint_stop' callback msg")
            self.swp_var.set(False)
            self.toggle_single_waypoint()
        elif msg == "stop_all_assists":
            logger.debug("Detected 'stop_all_assists' callback msg")
            self.stop_active_mode()
            self.swp_var.set(False)
            self.toggle_single_waypoint()
        elif msg == "route_info":
            self.update_route_info(body)
        elif msg == "update_ship_cfg":
            self.update_ship_cfg()
        else:
            mode, _, action = msg.rpartition("_")
            if mode in MODE_KEYS and action in ("start", "stop"):
                if action == "stop":
                    logger.debug(f"Detected '{msg}' callback msg")
                self.set_mode(mode, action == "start")

    def update_ship_cfg(self):
        """Load up the display with what we read from ED_AP for the current ship."""
        self.load_vars("Ship")
        self._cancel_save_job("Ship")
        self._set_save("Ship", "saved")

    def process_hotkey_actions(self):
        self.hotkey_poll_id = self.root.after(50, self.process_hotkey_actions)
        self.hotkey_actions.run_pending()
        while True:
            try:
                msg, body = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            self.callback(msg, body)

    # modes: only one can run at a time

    def _mode_clicked(self, key):
        self.set_mode(key, self.active_mode != key)

    def set_mode(self, key, on):
        if on:
            if self.SWP_A_running or self.ed_ap.single_waypoint_enabled:
                self.notify_user("Stop the running target selection or Single Waypoint Assist first.")
                return
            if self.active_mode is not None:
                return
            if self._start_mode(key) is False:
                return
            self.active_mode = key
        elif self.active_mode == key:
            self._stop_mode(key)
            self.active_mode = None
        self._refresh_modes()

    def stop_active_mode(self):
        if self.active_mode is not None:
            self.set_mode(self.active_mode, False)

    def _start_mode(self, key):
        if key == "travel":
            self.start_travel()
        elif key == "waypoint":
            return self.start_waypoint()
        elif key == "dss":
            self.start_dss()
        else:
            self.ed_ap.set_afk_combat_assist(True)
            self.notify_user("AFK Combat Assist start")

    def _stop_mode(self, key):
        if key == "travel":
            self.stop_travel()
        elif key == "waypoint":
            self.stop_waypoint()
        elif key == "dss":
            self.stop_dss()
        else:
            self.ed_ap.set_afk_combat_assist(False)
            self.notify_user("AFK Combat Assist stop")

    def _refresh_modes(self):
        for key, button in self.items.items():
            button.set_active(key == self.active_mode)
            blocked = self.active_mode is not None and key != self.active_mode
            button.set_disabled(blocked)
            self.mode_tips[key].configure(text="Stop the running assist first." if blocked else self._tip(key))
        self.stop_tip.configure(text=self._tip("stop", "Stop All"))
        if hasattr(self, "waypoint_editor"):
            self.waypoint_editor.set_running()

    def _tip(self, key, label=None):
        label = label or self.mode_labels[key]
        hotkey = self.active_hotkeys.get(key)
        return f"{label} ({hotkey.upper()})" if hotkey else label

    def quit(self):
        logger.debug("Entered: quit")
        self.close_window()

    def _save_window_state(self):
        window_state.save(
            {"x": self.root.winfo_x(), "y": self.root.winfo_y(), "collapsed": self.collapsed, "topmost": self.pinned}
        )

    def close_window(self):
        logger.debug("Entered: close_window")
        if hasattr(self, "waypoint_editor") and not self.waypoint_editor.discard():
            return
        self._save_window_state()
        if self.hotkeys is not None:
            self.hotkeys.stop()
        if self.hotkey_poll_id is not None:
            self.root.after_cancel(self.hotkey_poll_id)
        self.stop_travel()
        self.ed_ap.quit()
        sleep(0.1)
        self.root.destroy()

    # this routine is to stop any current autopilot activity
    def stop_all_assists(self):
        logger.debug("Entered: stop_all_assists")
        self.callback("stop_all_assists")

    def start_travel(self):
        logger.debug("Entered: start_travel")
        self.ed_ap.set_travel_assist(True)
        self.TRAVEL_A_running = True
        self.notify_user("Travel Assist start")
        self.ed_ap.vce.say("Travel Assist On")

    def stop_travel(self):
        logger.debug("Entered: stop_travel")
        self.ed_ap.set_travel_assist(False)
        self.TRAVEL_A_running = False
        self.notify_user("Travel Assist stop")
        self.ed_ap.vce.say("Travel Assist Off")

    def start_waypoint(self):
        logger.debug("Entered: start_waypoint")
        if hasattr(self, "waypoint_editor") and not self.waypoint_editor.prepare_start():
            return False
        self.ed_ap.set_waypoint_assist(True)
        self.WP_A_running = True
        self.notify_user("Waypoint Assist start")
        self.ed_ap.vce.say("Waypoint Assist On")
        return True

    def stop_waypoint(self):
        logger.debug("Entered: stop_waypoint")
        self.ed_ap.set_waypoint_assist(False)
        self.WP_A_running = False
        self.notify_user("Waypoint Assist stop")
        self.ed_ap.vce.say("Waypoint Assist Off")

    def start_dss(self):
        logger.debug("Entered: start_dss")
        self.ed_ap.set_dss_assist(True)
        self.DSS_A_running = True
        self.notify_user("DSS Assist start")
        self.ed_ap.vce.say("DSS Assist On")

    def stop_dss(self):
        logger.debug("Entered: stop_dss")
        self.ed_ap.set_dss_assist(False)
        self.DSS_A_running = False
        self.notify_user("DSS Assist stop")
        self.ed_ap.vce.say("DSS Assist Off")

    def toggle_single_waypoint(self):
        if self.swp_var.get() and not self.SWP_A_running:
            self.start_single_waypoint_assist()
            if not self.SWP_A_running:
                self.swp_var.set(False)
        elif not self.swp_var.get() and self.SWP_A_running:
            self.stop_single_waypoint_assist()

    def start_single_waypoint_assist(self):
        """The debug command to go to a system or station or both."""
        logger.debug("Entered: start_single_waypoint_assist")
        if self.active_mode is not None:
            self.notify_user("Stop the running assist first.")
            return
        system = self.single_waypoint_system.get()
        station = self.single_waypoint_station.get()

        if system != "" or station != "":
            self.ed_ap.set_single_waypoint_assist(system, station, True)
            self.SWP_A_running = True
            self.notify_user("Single Waypoint Assist start")
            self.ed_ap.vce.say("Single Waypoint Assist On")

    def stop_single_waypoint_assist(self):
        """The debug command to go to a system or station or both."""
        logger.debug("Entered: stop_single_waypoint_assist")
        self.ed_ap.set_single_waypoint_assist("", "", False)
        self.SWP_A_running = False
        self.notify_user("Single Waypoint Assist stop")
        self.ed_ap.vce.say("Single Waypoint Assist Off")

    # info and updates

    def about(self):
        webbrowser.open_new("https://github.com/DopeEx/EDAPGui")

    def check_updates(self, manual=True):
        """Look for a newer release in the background. The result is shown on the Info tab."""
        result = {}

        def worker():
            result["tag"] = updates.get_latest_release()
            result["done"] = True

        def show_result():
            if not result.get("done"):
                self.root.after(200, show_result)
                return
            self._update_result(result["tag"], manual)

        self.update_text.set("Checking for updates...")
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(200, show_result)

    def _update_result(self, tag, manual):
        if tag is not None and updates.is_newer(tag):
            self.update_tag = tag
            self.update_text.set(f"A new release ({tag}) is available.")
            self.notify_user(f"A new release version ({tag}) is available, see the Info tab.")
        else:
            self.update_tag = None
            if tag is None:
                self.update_text.set("Could not find a published release.")
            else:
                self.update_text.set(f"You are up to date ({EDAP_VERSION}).")
        self._show_update_notice()
        self.refresh_update_button()

    def open_download(self):
        webbrowser.open_new(updates.LATEST_RELEASE_PAGE)

    def open_changelog(self):
        webbrowser.open_new("https://github.com/DopeEx/EDAPGui/blob/main/CHANGELOG.md")

    def open_logfile(self):
        os.startfile(paths.LOG_FILE)

    # log and status

    def notify_user(self, msg, speak=False):
        if threading.current_thread() is not threading.main_thread():
            self.ui_queue.put(("user_message", (msg, speak)))
            return
        if speak and not hasattr(self, "ed_ap"):
            self.ui_queue.put(("user_message", (msg, speak)))
            return
        self.log_msg(msg)
        if speak:
            self.ed_ap.vce.say(msg)

    def log_msg(self, msg):
        message = datetime.now().strftime("%H:%M:%S: ") + msg
        logger.info(msg)
        self.log_lines.append(message)
        if self.log_text is not None and self.log_text.winfo_exists():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.configure(state="disabled")
            self.log_text.see("end")

    def update_route_info(self, txt):
        self.route_text = txt
        self.route_info.configure(text=txt)

    def update_statusline(self, txt):
        self.status_text = txt
        self.status.configure(text=txt)
        self.log_msg(f"Status update: {txt}")

    # ship and waypoints

    def ship_tst_pitch(self):
        self.ed_ap.ship_tst_pitch()

    def ship_tst_roll(self):
        self.ed_ap.ship_tst_roll()

    def ship_tst_yaw(self):
        self.ed_ap.ship_tst_yaw()

    def open_wp_file(self):
        if hasattr(self, "waypoint_editor"):
            self.waypoint_editor.open()
            return
        if self.WP_A_running:
            messagebox.showerror(
                "Waypoint List Error", "Waypoint Assist must be disabled before loading another route."
            )
            return
        filetypes = (("json files", "*.json"), ("All files", "*.*"))
        filename = fd.askopenfilename(title="Waypoint File", initialdir=paths.WAYPOINTS_DIR, filetypes=filetypes)
        if filename != "":
            res = self.ed_ap.waypoint.load_waypoint_file(filename)
            if res:
                self.wp_filelabel.set("loaded: " + Path(filename).name)

    def reset_wp_file(self):
        if not self.WP_A_running:
            mb = messagebox.askokcancel(
                "Waypoint List Reset",
                "Reset route progress and remaining commodity quantities? Waypoint Assist will start again from the first point.",
            )
            if mb:
                if not self.ed_ap.waypoint.mark_all_waypoints_not_complete():
                    messagebox.showerror(
                        "Waypoint List Error", "Waypoint progress could not be saved. Check the log file."
                    )
        else:
            messagebox.showerror(
                "Waypoint List Error", "Waypoint Assist must be disabled before you can reset the list."
            )

    def load_tce_dest(self):
        filename = self.vars["TCEDestinationFilepath"].get()
        if os.path.exists(filename):
            with open(filename, "r") as json_file:
                f_details = json.load(json_file)

            self.single_waypoint_system.set(f_details["StarSystem"])
            self.single_waypoint_station.set(f_details["Station"])

    def restart_program(self):
        logger.debug("Entered: restart_program")
        if hasattr(self, "waypoint_editor") and not self.waypoint_editor.discard():
            return

        self._save_window_state()
        self.stop_travel()
        self.ed_ap.quit()
        sleep(0.1)

        logger.info(f"Restarting: {sys.executable} {sys.argv}")
        print("Restarting EDAPGui...")

        os.execv(sys.executable, ["python"] + sys.argv)


def main():
    enable_dpi_awareness()
    root = ttk.Window(themename="darkly")
    root.configure(bg=BG)
    app = APGui(root)  # noqa: F841 - keep a reference for the lifetime of the main loop

    root.mainloop()


if __name__ == "__main__":
    main()
