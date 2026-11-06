"""Route selection and inline waypoint/commodity editing in the Waypoints tab."""

import copy
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk

from core import paths
from core.commodities import commodity_id_matches_name, get_localization, is_commodity_id
from core.logger import logger
from gui.commodity_catalogue import load_catalogue, suggestions
from gui.route_import import imported_waypoints, parse_trade_route, resolve_commodities
from gui.theme import CARD, FIELD, ORANGE, PANEL, RED, TEXT, Metrics
from gui.waypoint_model import RouteDocument, RouteIssue, entry_issues, new_waypoint
from gui.widgets import RoundButton, add_tooltip, section_card


def action_button(parent, text="", command=None, icon=None):
    metrics = Metrics(parent)
    button = RoundButton(parent, metrics, icon, text, command, bg=ttk.Style().lookup("TFrame", "background"))
    item = button.icon_item if icon else button.text_item
    bounds = button.bbox(item)
    button.configure(width=bounds[2] - bounds[0] + metrics.px(20 if icon else 28), takefocus=True)
    button.bind("<Return>", lambda _event: button.invoke())
    button.bind("<space>", lambda _event: button.invoke())
    return button


def trade_quantity_summary(commodities):
    if commodities == {"All": 0}:
        return "All cargo"
    if any(type(quantity) is not int or quantity < 0 for quantity in commodities.values()):
        return "Invalid quantity"
    fixed = sum(quantity for quantity in commodities.values() if quantity != 9999)
    if 9999 in commodities.values():
        return f"All + {fixed}" if fixed else "All"
    return str(fixed)


def _game_language(app):
    locale = getattr(getattr(app, "ed_ap", None), "locale", None)
    available = getattr(locale, "available_languages", None)
    if not isinstance(available, (list, tuple)) or not available:
        available = get_localization().available_languages
    language = getattr(locale, "language", None) or getattr(app, "waypoint_commodity_language", None)
    if not isinstance(language, str):
        language = getattr(app, "waypoint_commodity_language", None)
    if language in available:
        return language
    return "en" if "en" in available else available[0]


def style_table(tree):
    metrics = Metrics(tree)
    style = ttk.Style()
    style.configure(
        "Waypoint.Treeview",
        rowheight=tkfont.nametofont("TkDefaultFont", root=tree).metrics("linespace") + metrics.px(12),
    )
    style.configure(
        "Waypoint.Treeview.Heading",
        background=PANEL,
        foreground=TEXT,
        relief="flat",
        padding=(metrics.px(8), metrics.px(8)),
    )
    style.map(
        "Waypoint.Treeview.Heading",
        background=[("active", CARD), ("!active", PANEL)],
        foreground=[("disabled", TEXT), ("!disabled", TEXT)],
    )
    # ttkbootstrap normalizes custom style prefixes away; assign the exact style through Tk.
    tree.tk.call(tree._w, "configure", "-style", "Waypoint.Treeview")
    tree.tag_configure("even", background=FIELD)
    tree.tag_configure("odd", background="#3b3b3b")


class WaypointTable(ttk.Treeview):
    def __init__(self, parent, **options):
        self._separator_update = None
        super().__init__(parent, **options)
        style_table(self)
        columns = ("#0", *self.cget("columns"))[:-1]
        self.column_separators = [
            (
                tk.Frame(self, background="#5a5a5a", borderwidth=0, highlightthickness=0),
                tk.Frame(self, background="#343434", borderwidth=0, highlightthickness=0),
            )
            for _column in columns
        ]
        self.divider_columns = columns
        for pair in self.column_separators:
            for separator in pair:
                for sequence in ("<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>", "<MouseWheel>"):
                    separator.bind(sequence, lambda event, sequence=sequence: self.forward_table_event(event, sequence))
        for sequence in ("<Map>", "<Configure>", "<B1-Motion>", "<ButtonRelease-1>"):
            self.bind(sequence, self.schedule_column_separators, add="+")
        self.bind("<Destroy>", self.cancel_separator_update, add="+")

    def forward_table_event(self, event, sequence):
        options = {
            "x": event.widget.winfo_x() + event.x,
            "y": event.widget.winfo_y() + event.y,
            "state": event.state,
        }
        if sequence == "<MouseWheel>":
            options["delta"] = event.delta
        self.event_generate(sequence, **options)

    def schedule_column_separators(self, _event=None):
        if self._separator_update is None:
            self._separator_update = self.after_idle(self.run_separator_update)

    def run_separator_update(self):
        self._separator_update = None
        self.update_column_separators()

    def cancel_separator_update(self, event):
        if event.widget is self and self._separator_update is not None:
            self.after_cancel(self._separator_update)
            self._separator_update = None

    def update_column_separators(self):
        if not self.winfo_exists():
            return
        # Treeview has no native vertical grid; split each line at the actual header boundary.
        header_bottom = 1
        for y in range(1, self.winfo_height()):
            if self.identify_region(10, y) == "heading":
                header_bottom = y + 1
            elif header_bottom > 1:
                break
        x = 1
        for column, (heading, body) in zip(self.divider_columns, self.column_separators):
            x += self.column(column, "width")
            if x < self.winfo_width() - 1:
                heading.place(x=x, y=1, width=1, height=header_bottom - 1)
                body.place(x=x, y=header_bottom, width=1, relheight=1, height=-header_bottom - 1)
                heading.lift()
                body.lift()
            else:
                heading.place_forget()
                body.place_forget()


class ActiveWaypointTable(WaypointTable):
    def __init__(self, parent, on_toggle, **options):
        self.active_buttons = {}
        self.on_toggle = on_toggle
        super().__init__(parent, **options)
        style = ttk.Style()
        layout = style.layout("TCheckbutton")
        indicator = layout[0][1]["children"][0][0]
        style.layout("WaypointActive.TCheckbutton", [(indicator, {"sticky": ""})])

    def update_active(self, entries, locked):
        ids = {entry["Id"] for entry in entries}
        for row in list(self.active_buttons):
            if row not in ids:
                self.active_buttons.pop(row)[0].destroy()
        for entry in entries:
            row = entry["Id"]
            if row not in self.active_buttons:
                variable = tk.BooleanVar(self)
                button = ttk.Checkbutton(
                    self, variable=variable, command=lambda row=row: self.on_toggle(row), takefocus=False
                )
                # Keep the themed indicator, without the opaque spacer and empty label.
                button.tk.call(button._w, "configure", "-style", "WaypointActive.TCheckbutton")
                button.bind("<MouseWheel>", lambda event: self.forward_table_event(event, "<MouseWheel>"))
                self.active_buttons[row] = (button, variable)
            button, variable = self.active_buttons[row]
            variable.set(entry["Enabled"])
            button.configure(state="disabled" if locked else "normal")
        self.schedule_column_separators()

    def update_column_separators(self):
        super().update_column_separators()
        if not self.winfo_exists():
            return
        for row, (button, _variable) in self.active_buttons.items():
            bounds = self.bbox(row, "enabled") if self.exists(row) else ()
            if bounds:
                x, y, width, height = bounds
                button.place(
                    x=x + (width - button.winfo_reqwidth()) // 2,
                    y=y + (height - button.winfo_reqheight()) // 2,
                )
                button.lift()
            else:
                button.place_forget()


class CommodityList(ttk.Frame):
    def __init__(self, parent, values, language=None, catalogue=None, allow_all=False):
        super().__init__(parent)
        self.values = dict(values)
        self.on_change = None
        self.allow_all = allow_all
        self.selected_commodity_id = None
        self._updating_name = False
        metrics = Metrics(self)
        self.columnconfigure(0, weight=1)
        self.tree = WaypointTable(self, columns=("quantity",), show="tree headings", height=5)
        self.tree.heading("#0", text="Commodity (game language)")
        self.tree.heading("quantity", text="Quantity / All")
        self.tree.column("#0", width=250)
        quantity_width = tkfont.nametofont("TkDefaultFont", root=self).measure("Quantity / All") + Metrics(self).px(24)
        self.tree.column("quantity", width=quantity_width, minwidth=quantity_width, stretch=False)
        self.tree.grid(row=0, column=0, columnspan=3, sticky="nsew")
        self.rowconfigure(0, weight=1)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=3, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.name = tk.StringVar()
        self.quantity = tk.StringVar(value="1")
        self.language = language if language is not None else tk.StringVar(self, value="en")
        self.catalogue = catalogue if catalogue is not None else load_catalogue()
        self.name_picker = ttk.Combobox(self, textvariable=self.name, postcommand=self.filter_names)
        self.name_picker.grid(row=1, column=0, sticky="nsew", pady=metrics.u(8))
        self.name_picker.bind("<<ComboboxSelected>>", self.choose_name)
        self.quantity_picker = ttk.Combobox(self, textvariable=self.quantity, values=("All",), width=8)
        self.quantity_picker.grid(row=1, column=1, sticky="ns", padx=metrics.u(8), pady=metrics.u(8))
        action_button(self, text="Set", command=self.set_item).grid(row=1, column=2, pady=metrics.u(8))
        controls = ttk.Frame(self)
        controls.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, metrics.u(8)))
        self.action_buttons = []
        self.action_tooltips = []
        for icon, tip, command in (
            ("delete", "Remove selected commodities", self.remove),
            ("up", "Move selected commodities up", lambda: self.move(-1)),
            ("down", "Move selected commodities down", lambda: self.move(1)),
        ):
            button = action_button(controls, icon=icon, command=command)
            button.pack(side="left", padx=Metrics(self).u(2))
            self.action_buttons.append(button)
            self.action_tooltips.append(add_tooltip(button, tip))
        language_row = ttk.Frame(self)
        language_row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, metrics.u(8)))
        ttk.Label(language_row, text="Game commodity language").pack(side="left")
        self.localization = get_localization(self.language.get())
        self.language_picker = ttk.Combobox(
            language_row,
            textvariable=self.language,
            values=self.localization.available_languages,
            state="readonly",
            width=8,
        )
        self.language_picker.pack(side="left", padx=metrics.u(8))
        ttk.Label(language_row, text="[unchecked] = name not game-verified").pack(side="left")
        self.name_trace = self.name.trace_add("write", self.name_changed)
        self.language_trace = self.language.trace_add("write", self.language_changed)
        self.quantity_trace = self.quantity.trace_add("write", self.changed)
        self.bind("<Destroy>", self.destroyed, add="+")
        self.tree.bind("<<TreeviewSelect>>", self.selected)
        self.filter_names()
        self.refresh()

    def destroyed(self, event):
        if event.widget is self:
            self.name.trace_remove("write", self.name_trace)
            self.language.trace_remove("write", self.language_trace)
            self.quantity.trace_remove("write", self.quantity_trace)

    def changed(self, *_args):
        if self.on_change is not None:
            self.on_change()

    def name_changed(self, *_args):
        if not self._updating_name:
            self.selected_commodity_id = None
        self.filter_names()

    def language_changed(self, *_args):
        self.localization = get_localization(self.language.get())
        self.filter_names()
        self.refresh_labels()
        if self.selected_commodity_id is not None:
            self.set_name(self.display_name(self.selected_commodity_id), self.selected_commodity_id)

    def set_name(self, value, commodity_id=None):
        self._updating_name = True
        try:
            self.name.set(value)
        finally:
            self._updating_name = False
        self.selected_commodity_id = commodity_id

    def filter_names(self, *_args):
        rows, verified = self.catalogue
        self.name_choices = suggestions(rows, verified, self.language.get(), "", self.localization)
        matches = suggestions(rows, verified, self.language.get(), self.name.get(), self.localization)
        self.name_picker.configure(values=tuple(matches))
        self.changed()

    def display_name(self, commodity_id):
        if commodity_id == "All":
            return "All cargo"
        labels = self.name_choices
        for label, item_id in labels.items():
            if item_id == commodity_id:
                return label.removesuffix(" [unchecked]")
        item = self.catalogue[0].get(commodity_id)
        return self.localization.commodity_name(commodity_id) if item else commodity_id

    def refresh_labels(self):
        for commodity_id in self.tree.get_children():
            self.tree.item(commodity_id, text=self.display_name(commodity_id))

    def choose_name(self, _event=None):
        selected = self.name.get()
        if selected in self.name_choices:
            self.set_name(selected.removesuffix(" [unchecked]"), self.name_choices[selected])

    def refresh(self):
        selection = self.tree.selection()
        focus = self.tree.focus()
        self.tree.delete(*self.tree.get_children())
        for index, (commodity_id, quantity) in enumerate(self.values.items()):
            self.tree.insert(
                "",
                "end",
                iid=commodity_id,
                text=self.display_name(commodity_id),
                values=("All" if quantity == 9999 else quantity,),
                tags=("odd" if index % 2 else "even",),
            )
        current_items = set(self.tree.get_children())
        retained = [item for item in selection if item in current_items]
        if retained:
            self.tree.selection_set(retained)
        if focus in current_items:
            self.tree.focus(focus)
        self.changed()

    def selected(self, _event=None):
        selection = self.tree.selection()
        if selection:
            commodity_id = selection[0]
            self.set_name(self.display_name(commodity_id), commodity_id)
            self.quantity.set(self.tree.item(selection[0], "values")[0])

    def set_item(self):
        try:
            self.choose_name()
            name = self.name.get().strip()
            quantity = self.quantity_value()
            if self.selected_commodity_id is not None:
                commodity_id = self.selected_commodity_id
            elif name in self.name_choices:
                commodity_id = self.name_choices[name]
            elif is_commodity_id(name) and name in self.catalogue[0]:
                commodity_id = name
            elif self.allow_all and name.casefold() == "all" and quantity == 0:
                commodity_id = "All"
            else:
                matches = commodity_id_matches_name(name, self.localization)
                if len(matches) != 1 or not matches <= self.catalogue[0].keys():
                    raise ValueError
                commodity_id = matches.pop()
            if commodity_id == "All" and (not self.allow_all or quantity != 0):
                raise ValueError
            if quantity < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Commodity",
                "Choose one known commodity and enter a non-negative whole quantity, or choose All.",
                parent=self,
            )
            return
        self.values[commodity_id] = quantity
        self.refresh()
        self.set_name("")
        self.quantity.set("1")

    def remove(self):
        for item in self.tree.selection():
            del self.values[item]
        self.refresh()
        self.set_name("")
        self.quantity.set("1")

    def move(self, offset):
        selected = set(self.tree.selection())
        if not selected:
            return
        names = list(self.values)
        indices = range(len(names)) if offset < 0 else range(len(names) - 1, -1, -1)
        for index in indices:
            target = index + offset
            if names[index] in selected and 0 <= target < len(names) and names[target] not in selected:
                names[index], names[target] = names[target], names[index]
        self.values = {name: self.values[name] for name in names}
        self.refresh()
        items = [item for item in self.tree.get_children() if item in selected]
        self.tree.selection_set(items)
        self.tree.see(items[0])

    def get(self):
        name = self.name.get().strip()
        if name:
            try:
                quantity = self.quantity_value()
            except ValueError:
                raise ValueError(
                    "A commodity entry is still pending. Press Set or clear its name before applying."
                ) from None
            commodity_id = self.selected_commodity_id or self.name_choices.get(name)
            if commodity_id not in self.values or quantity != self.values[commodity_id]:
                raise ValueError("A commodity entry is still pending. Press Set or clear its name before applying.")
        return dict(self.values)

    def quantity_value(self):
        value = self.quantity.get().strip()
        return 9999 if value.casefold() == "all" else int(value)


class WaypointForm(ttk.Frame):
    def __init__(self, parent, entry, on_apply, on_cancel, app, global_list=False):
        super().__init__(parent)
        self.entry = copy.deepcopy(entry)
        self.global_list = global_list
        self.on_apply = on_apply
        self.card = section_card(app, self, "Global shopping list" if global_list else "Waypoint")
        self.card.pack_configure(fill="both", expand=True, pady=0)
        self.card.rowconfigure(0, weight=1)
        self.notebook = notebook = ttk.Notebook(self.card)
        notebook.grid(row=0, column=0, sticky="nsew")
        general = ttk.Frame(notebook, padding=8)
        general.columnconfigure(1, weight=1)
        notebook.add(general, text="General")
        self.variables = {}
        self.field_widgets = {}
        row = 0
        if not global_list:
            fields = (
                ("SystemName", "System", None),
                ("StationName", "Station", None),
                ("GalaxyBookmarkType", "Galaxy bookmark", ("", "Fav", "System", "Body", "Station", "Settlement")),
                ("GalaxyBookmarkNumber", "Galaxy bookmark position", None),
                ("SystemBookmarkType", "System bookmark", ("", "Fav", "Body", "Station", "Settlement", "Navigation")),
                ("SystemBookmarkNumber", "System bookmark position", None),
            )
            for key, label, choices in fields:
                var = self.variables[key] = tk.StringVar(value=str(entry[key]))
                ttk.Label(general, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=5)
                widget = (
                    ttk.Combobox(general, textvariable=var, values=choices, width=23)
                    if choices is not None
                    else ttk.Entry(general, textvariable=var, width=25)
                )
                widget.grid(row=row, column=1, sticky="ew", pady=3)
                self.field_widgets[key] = widget
                row += 1
        checks = [("UpdateCommodityCount", "Reduce remaining quantities after trades")]
        if not global_list:
            checks += [("FleetCarrierTransfer", "Fleet Carrier transfer (instead of trading)")]
        checks += [("Enabled", "Enable this shopping list" if global_list else "Enable this waypoint")]
        for key, label in checks:
            var = self.variables[key] = tk.BooleanVar(value=entry[key])
            ttk.Checkbutton(general, text=label, variable=var).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
            row += 1
        self.language = tk.StringVar(self, value=_game_language(app))
        self.app = app
        try:
            catalogue = load_catalogue()
        except (OSError, ValueError, KeyError) as error:
            logger.error("Could not load commodity catalogue: %s", error)
            messagebox.showerror("Commodity catalogue", str(error), parent=self)
            catalogue = ({}, {})
        self.buy = CommodityList(notebook, entry["BuyCommodities"], self.language, catalogue)
        notebook.add(self.buy, text="Buy")
        self.sell = None
        if not global_list:
            self.sell = CommodityList(notebook, entry["SellCommodities"], self.language, catalogue, allow_all=True)
            notebook.add(self.sell, text="Sell / transfer")
        buttons = ttk.Frame(self.card)
        buttons.grid(row=1, column=0, sticky="ew", pady=(app.metrics.u(8), 0))
        self.apply_button = action_button(buttons, text="Apply", command=self.apply)
        self.apply_button.pack(side="right")
        self.cancel_button = action_button(buttons, text="Cancel", command=on_cancel)
        self.cancel_button.pack(side="right", padx=8)
        self.plot_buttons = []
        if not global_list:
            plot_row = ttk.Frame(general)
            plot_row.grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
            for label, station in (("Plot to System", False), ("Plot to Station", True)):
                button = action_button(plot_row, text=label, command=lambda station=station: self.plot(station))
                button.pack(side="left", padx=(0, app.metrics.u(8)))
                self.plot_buttons.append(button)
        checks_page = ttk.Frame(notebook)
        self.checks_text = tk.Text(checks_page, wrap="word", height=5, width=35, bg=FIELD, fg=TEXT, borderwidth=0)
        self.checks_text.pack(fill="both", expand=True)
        self.checks_text.tag_configure("error", foreground=RED)
        self.checks_text.tag_configure("warning", foreground=ORANGE)
        notebook.add(checks_page, text="Checks")
        self.checks_page = checks_page
        self.validation_status = ttk.Label(buttons, text="", wraplength=220)
        self.validation_status.pack(side="left", fill="x", expand=True)
        self.variable_traces = [(var, var.trace_add("write", self.validate_live)) for var in self.variables.values()]
        self.buy.on_change = self.validate_live
        if self.sell is not None:
            self.sell.on_change = self.validate_live
        self.bind("<Destroy>", self.validation_destroyed, add="+")
        self.validate_live()

    def set_game_language(self, code):
        if code in self.buy.localization.available_languages:
            self.language.set(code)

    def plot(self, station):
        try:
            entry = self.current_entry()
            problems = [
                issue.describe()
                for issue in entry_issues(entry)
                if issue.severity == "error" and issue.field not in ("BuyCommodities", "SellCommodities")
            ]
            if problems:
                raise ValueError("\n".join(problems))
            if station and not entry["StationName"].strip():
                raise ValueError("Enter a station name before plotting a station.")
        except ValueError as error:
            messagebox.showerror("Target selection", str(error), parent=self)
            return
        if self.app.active_mode is not None or self.app.SWP_A_running:
            messagebox.showerror("Target selection", "Stop the running assist first.", parent=self)
            return
        if self.app.ed_ap.set_waypoint_plot(entry, station):
            self.app.SWP_A_running = True
            self.app.notify_user("Waypoint target selection started; no flight or trade will be performed.")

    def validation_destroyed(self, event):
        if event.widget is self:
            for var, trace in self.variable_traces:
                var.trace_remove("write", trace)

    def current_entry(self):
        entry = copy.deepcopy(self.entry)
        for key, var in self.variables.items():
            value = var.get()
            if key.endswith("BookmarkNumber"):
                try:
                    value = int(value)
                except ValueError:
                    pass
            entry[key] = value
        entry["BuyCommodities"] = dict(self.buy.values)
        if self.sell is not None:
            entry["SellCommodities"] = dict(self.sell.values)
        return entry

    def validate_live(self, *_args):
        issues = entry_issues(self.current_entry(), global_list=self.global_list)
        editor = self.master
        if not self.global_list and isinstance(editor, WaypointEditor):
            candidate = copy.deepcopy(editor.document)
            index = editor.form_index
            if editor.form_insert:
                candidate.data["waypoints"].insert(index, self.current_entry())
            elif index is None:
                index = len(candidate.data["waypoints"])
                candidate.data["waypoints"].append(self.current_entry())
            else:
                candidate.data["waypoints"][index] = self.current_entry()
            issues = [issue for issue in candidate.issues() if issue.index == index]
        for field, table in (("BuyCommodities", self.buy), ("SellCommodities", self.sell)):
            if table is None:
                continue
            try:
                table.get()
            except ValueError as error:
                issues.append(RouteIssue("error", None if self.global_list else 0, field, str(error)))
            table.tree.tag_configure("invalid", foreground=RED)
            for item in table.tree.get_children():
                commodity_id = item
                quantity = table.values[commodity_id]
                tags = tuple(tag for tag in table.tree.item(item, "tags") if tag != "invalid")
                is_all_transfer = table.allow_all and commodity_id == "All" and type(quantity) is int and quantity == 0
                invalid = not is_commodity_id(commodity_id) and not is_all_transfer
                invalid = invalid or type(quantity) is not int or quantity < 0
                table.tree.item(item, tags=(("invalid",) if invalid else ()) + tags)
            table.name_picker.configure(
                bootstyle="danger" if any(i.field == field and i.severity == "error" for i in issues) else "default"
            )
            try:
                pending_quantity = table.quantity_value()
                invalid_quantity = pending_quantity < 0
            except ValueError:
                invalid_quantity = True
            table.quantity_picker.configure(bootstyle="danger" if invalid_quantity else "default")
        for field, widget in self.field_widgets.items():
            matches = [issue for issue in issues if issue.field == field]
            role = "danger" if any(i.severity == "error" for i in matches) else "warning" if matches else "default"
            widget.configure(bootstyle=role)
        errors = sum(issue.severity == "error" for issue in issues)
        warnings = len(issues) - errors
        self.apply_button.set_disabled(errors > 0)
        self.validation_status.configure(
            text=f"{errors} error(s), {warnings} warning(s) - see Checks" if issues else "No issues",
            foreground=RED if errors else ORANGE if warnings else TEXT,
        )
        self.notebook.tab(self.checks_page, text=f"Checks ({len(issues)})")
        self.checks_text.configure(state="normal")
        self.checks_text.delete("1.0", "end")
        for issue in issues:
            self.checks_text.insert("end", f"{issue.severity.upper()}: {issue.message}\n\n", issue.severity)
        if not issues:
            self.checks_text.insert("end", "No issues found. Live game conditions are not checked here.")
        self.checks_text.configure(state="disabled")
        self.live_issues = issues

    def apply(self):
        try:
            entry = copy.deepcopy(self.entry)
            for key, var in self.variables.items():
                value = var.get()
                entry[key] = (
                    int(value) if key.endswith("BookmarkNumber") else value.strip() if isinstance(value, str) else value
                )
            entry["BuyCommodities"] = self.buy.get()
            if self.sell is not None:
                entry["SellCommodities"] = self.sell.get()
            document = RouteDocument()
            if self.global_list:
                document.data["GlobalShoppingList"] = entry
            else:
                document.data["waypoints"] = [entry]
            document.validate()
        except ValueError as error:
            messagebox.showerror("Waypoint", str(error), parent=self)
            return
        self.on_apply(entry)

    def snapshot(self):
        tables = {}
        for key, table in (("buy", self.buy), ("sell", self.sell)):
            if table is not None:
                tables[key] = (dict(table.values), table.name.get(), table.quantity.get())
        return {
            "entry": copy.deepcopy(self.entry),
            "variables": {key: var.get() for key, var in self.variables.items()},
            "tables": tables,
            "tab": self.notebook.index("current"),
            "global_list": self.global_list,
            "commodity_language": self.language.get(),
        }

    def restore(self, state):
        self.language.set(state["commodity_language"])
        for key, value in state["variables"].items():
            self.variables[key].set(value)
        for key, (values, name, quantity) in state["tables"].items():
            table = self.buy if key == "buy" else self.sell
            table.values = dict(values)
            table.refresh()
            table.name.set(name)
            table.quantity.set(quantity)
        self.notebook.select(state["tab"])


class RouteImportForm(ttk.Frame):
    def __init__(self, parent, app, on_apply, on_cancel, on_legacy):
        super().__init__(parent)
        self.app = app
        self.on_apply = on_apply
        self.language = tk.StringVar(self, value=_game_language(app))
        self.target = tk.StringVar(self, value="New route")
        self.repeat = tk.BooleanVar(self)
        self.route = None
        self.quantities = {}
        self.selected_good = None
        self.card = section_card(app, self, "Import trade route")
        self.card.pack_configure(fill="both", expand=True, pady=0)
        self.card.rowconfigure(1, weight=1)
        options = ttk.Frame(self.card)
        options.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Combobox(
            options, textvariable=self.target, values=("New route", "Append to current"), state="readonly", width=18
        ).pack(side="left")
        ttk.Label(options, text="Game language").pack(side="left", padx=8)
        language_choices = getattr(getattr(app.ed_ap, "locale", None), "available_languages", None)
        if not language_choices:
            language_choices = get_localization(self.language.get()).available_languages
        self.language_picker = ttk.Combobox(
            options, textvariable=self.language, values=language_choices, state="readonly", width=8
        )
        self.language_picker.pack(side="left")
        ttk.Checkbutton(options, text="Repeat route", variable=self.repeat).pack(side="left", padx=8)
        self.notebook = ttk.Notebook(self.card)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        paste = ttk.Frame(self.notebook)
        paste.columnconfigure(0, weight=1)
        paste.rowconfigure(1, weight=1)
        self.notebook.add(paste, text="Paste")
        ttk.Label(paste, text="Paste one complete trade result (German or English).").grid(
            row=0, column=0, sticky="w", pady=6
        )
        self.text = tk.Text(paste, wrap="word", height=8, width=35, bg=FIELD, fg=TEXT, insertbackground=TEXT, undo=True)
        self.text.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(paste, command=self.text.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scroll.set)
        action_button(paste, text="Preview", command=self.preview).grid(row=2, column=0, sticky="e", pady=6)
        preview = ttk.Frame(self.notebook)
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(1, weight=1)
        self.notebook.add(preview, text="Preview")
        self.description = ttk.Label(preview, text="Paste a route, then choose Preview.", wraplength=450)
        self.description.grid(row=0, column=0, sticky="ew", pady=6)
        self.goods = WaypointTable(
            preview, columns=("quantity",), show="tree headings", height=3, selectmode="extended"
        )
        self.goods.heading("#0", text="Commodity")
        self.goods.heading("quantity", text="Quantity")
        self.goods.column("#0", width=230)
        self.goods.column("quantity", width=100)
        self.goods.grid(row=1, column=0, sticky="nsew")
        goods_scroll = ttk.Scrollbar(preview, command=self.goods.yview)
        goods_scroll.grid(row=1, column=1, sticky="ns")
        self.goods.configure(yscrollcommand=goods_scroll.set)
        quantity_row = ttk.Frame(preview)
        quantity_row.grid(row=2, column=0, sticky="ew", pady=6)
        ttk.Label(quantity_row, text="Quantity (Ctrl/Shift selection)").pack(side="left")
        self.quantity = tk.StringVar(self)
        ttk.Entry(quantity_row, textvariable=self.quantity, width=7).pack(side="left", padx=8)
        action_button(quantity_row, text="Set", command=self.set_quantity).pack(side="left")
        self.goods.bind("<<TreeviewSelect>>", self.selected)
        ttk.Label(
            self.card,
            text="Set station bookmarks before starting. Import does not save/start.\n[unchecked] = unverified name.",
            wraplength=450,
        ).grid(row=2, column=0, sticky="ew", pady=6)
        buttons = ttk.Frame(self.card)
        buttons.grid(row=3, column=0, sticky="ew")
        self.legacy_button = action_button(buttons, text="Legacy JSON...", command=on_legacy)
        self.legacy_button.pack(side="left")
        action_button(buttons, text="Import draft", command=self.apply).pack(side="right")
        action_button(buttons, text="Cancel", command=on_cancel).pack(side="right", padx=8)
        self.text.bind("<<Modified>>", self.invalidate)
        self.language.trace_add("write", self.invalidate)

    def set_game_language(self, code):
        if code in self.language_picker["values"]:
            self.language.set(code)

    def invalidate(self, *_args):
        if _args and isinstance(_args[0], tk.Event) and not self.text.edit_modified():
            return
        self.route = None
        if self.text.edit_modified():
            self.text.edit_modified(False)

    def preview(self):
        self.route = None
        self.text.edit_modified(False)
        try:
            route = parse_trade_route(self.text.get("1.0", "end-1c"))
            rows, verified = load_catalogue()
            resolved = resolve_commodities(route, rows, self.language.get())
        except (OSError, ValueError, KeyError) as error:
            logger.warning("Trade route import preview failed: %s", error)
            messagebox.showerror("Route import", str(error), parent=self)
            return
        self.route, self.resolved = route, resolved
        self.selected_good = None
        self.quantity.set("")
        self.goods.delete(*self.goods.get_children())
        for commodity_id, name in sorted(set(resolved.values()), key=lambda pair: pair[1].casefold()):
            label = name + ("" if int(commodity_id) in verified.get(self.language.get(), set()) else " [unchecked]")
            self.goods.insert("", "end", iid=commodity_id, text=label, values=(self.quantities.get(commodity_id, ""),))
        descriptions = []
        for index, (station, system) in enumerate((route.origin, route.destination)):
            actions = [
                f"{'Buy' if direction == 'BuyCommodities' else 'Sell'} {resolved[name][1]}"
                for position, direction, name in route.trades
                if position == index
            ]
            descriptions.append(f"{index + 1}. {station} | {system}: " + "; ".join(actions))
        self.description.configure(text="\n".join(descriptions))
        self.notebook.select(1)

    def selected(self, _event=None):
        selection = self.goods.selection()
        if selection != self.selected_good:
            self.selected_good = selection
            values = {self.quantities.get(item, "") for item in selection}
            self.quantity.set(str(values.pop()) if len(values) == 1 else "")

    def set_quantity(self):
        try:
            selection = self.goods.selection()
            if not selection:
                raise ValueError("Select a commodity first.")
            quantity = int(self.quantity.get())
            if not 1 <= quantity < 9999:
                raise ValueError("Choose a quantity from 1 to 9998.")
        except ValueError as error:
            messagebox.showerror("Route import", str(error), parent=self)
            return
        for item in selection:
            self.quantities[item] = quantity
            self.goods.item(item, values=(quantity,))

    def apply(self):
        try:
            if self.route is None:
                raise ValueError("Preview the current text and game language before importing.")
            selection = self.goods.selection()
            if (
                selection
                and self.quantity.get()
                and any(self.quantity.get() != str(self.quantities.get(item, "")) for item in selection)
            ):
                raise ValueError("Press Set to apply the pending quantity.")
            entries = imported_waypoints(self.route, self.resolved, self.quantities)
        except ValueError as error:
            messagebox.showerror("Route import", str(error), parent=self)
            return
        self.on_apply(entries, self.target.get() == "Append to current", self.repeat.get())

    def snapshot(self):
        return {
            "import": True,
            "text": self.text.get("1.0", "end-1c"),
            "language": self.language.get(),
            "target": self.target.get(),
            "repeat": self.repeat.get(),
            "quantities": dict(self.quantities),
            "quantity": self.quantity.get(),
            "selection": self.goods.selection(),
            "preview": self.route is not None,
        }

    def restore(self, state):
        self.text.insert("1.0", state["text"])
        self.text.edit_modified(False)
        self.language.set(state["language"])
        self.target.set(state["target"])
        self.repeat.set(state["repeat"])
        self.quantities = dict(state["quantities"])
        if state["preview"]:
            self.preview()
            if state["selection"]:
                self.selected_good = tuple(state["selection"])
                self.goods.selection_set(state["selection"])
        self.quantity.set(state["quantity"])


class WaypointEditor(ttk.Frame):
    @property
    def document(self):
        return self.app.waypoint_document

    @document.setter
    def document(self, value):
        self.app.waypoint_document = value

    def __init__(self, app, page):
        super().__init__(page)
        self.app = app
        existing_document = getattr(app, "waypoint_document", None)
        self.document = existing_document if existing_document is not None else RouteDocument()
        self.buttons = []
        self.dialog_open = False
        self.form = None
        self.form_index = None
        self.form_insert = False
        self.pack(fill="both", expand=True)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.list_view = list_view = ttk.Frame(self)
        list_view.grid(row=0, column=0, sticky="nsew")
        list_view.columnconfigure(0, weight=1)
        self.route_card = section_card(app, list_view, "Route")
        route_row = ttk.Frame(self.route_card)
        route_row.grid(row=0, column=0, sticky="ew", pady=(0, app.metrics.u(6)))
        route_row.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(self.route_card)
        toolbar.grid(row=1, column=0, sticky="ew")
        for label, command in (
            ("New", self.new),
            ("Browse...", self.open),
            ("Save", self.save),
            ("Save as", lambda: self.save(save_as=True)),
            ("Import...", self.import_route),
        ):
            button = action_button(toolbar, text=label, command=command)
            button.pack(side="left", padx=app.metrics.u(2))
            self.buttons.append(button)
        self.repeat = tk.BooleanVar(value=self.document.data["Repeat"])
        self.repeat_button = ttk.Checkbutton(
            route_row, text="Repeat route", variable=self.repeat, command=self.change_repeat
        )
        self.repeat_button.grid(row=0, column=1, sticky="w", padx=(app.metrics.u(8), 0))
        self.route_checks = self.nametowidget(str(self.route_card.cget("labelwidget")))
        self.route_checks.configure(cursor="hand2")
        self.route_checks.bind("<Button-1>", self.show_route_checks)
        self.route_choice = tk.StringVar()
        self.route_paths = {}
        self.route_picker = ttk.Combobox(
            route_row, textvariable=self.route_choice, state="readonly", postcommand=self.refresh_routes
        )
        self.route_picker.grid(row=0, column=0, sticky="ew")
        self.route_picker.bind("<<ComboboxSelected>>", self.select_route)
        self.waypoints_card = section_card(app, list_view, "Waypoints")
        self.waypoints_card.pack_configure(fill="both", expand=True, pady=0)
        self.waypoints_card.rowconfigure(0, weight=1)
        list_frame = ttk.Frame(self.waypoints_card)
        list_frame.grid(row=0, column=0, sticky="nsew", pady=(0, app.metrics.u(6)))
        self.tree = ActiveWaypointTable(
            list_frame,
            on_toggle=self.toggle_row,
            columns=("enabled", "station", "progress"),
            show="tree headings",
            selectmode="browse",
            height=8,
            style="Waypoint.Treeview",
        )
        self.tree.heading("#0", text="System")
        self.tree.heading("enabled", text="Active")
        active_width = tkfont.nametofont("TkDefaultFont", root=self).measure("Active") + app.metrics.px(28)
        self.tree.column("enabled", width=active_width, minwidth=active_width, stretch=False, anchor="center")
        self.tree.heading("station", text="Station")
        self.tree.heading("progress", text="Progress")
        self.tree.column("#0", width=130)
        self.tree.column("station", width=130)
        self.tree.column("progress", width=130)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")

        def update_scroll(first, last):
            scrollbar.set(first, last)
            self.tree.schedule_column_separators()

        self.tree.configure(yscrollcommand=update_scroll)
        self.tree.bind("<Button-1>", self.toggle_enabled)
        self.tree.bind("<Double-1>", self.double_click)
        self.tree.bind("<space>", self.toggle_selected)
        self.tree.bind("<<TreeviewSelect>>", self.show_selected_checks)
        controls = ttk.Frame(self.waypoints_card)
        controls.grid(row=1, column=0, sticky="ew")
        self.action_groups = {}
        for name in ("Create", "Edit", "Reorder"):
            if self.action_groups:
                ttk.Separator(controls, orient="vertical").pack(
                    side="left", fill="y", padx=app.metrics.u(3), pady=app.metrics.u(4)
                )
            group = ttk.Frame(controls)
            group.pack(side="left")
            self.action_groups[name] = group
        self.action_tooltips = []
        for icon, label, command in (
            ("add", "Add waypoint at end", self.add),
            ("edit", "Edit selected waypoint", self.edit),
            ("delete", "Delete selected waypoint", self.delete),
            ("up", "Move selected waypoint up", lambda: self.move(-1)),
            ("down", "Move selected waypoint down", lambda: self.move(1)),
            ("duplicate", "Duplicate selected waypoint", self.duplicate),
        ):
            group = "Create" if icon in ("add", "duplicate") else "Reorder" if icon in ("up", "down") else "Edit"
            button = action_button(self.action_groups[group], icon=icon, command=command)
            button.pack(side="left", padx=app.metrics.u(2))
            self.action_tooltips.append(add_tooltip(button, label))
            self.buttons.append(button)
        for label, command in (
            ("Before", lambda: self.insert(False)),
            ("After", lambda: self.insert(True)),
        ):
            button = action_button(self.action_groups["Create"], icon=label.lower(), command=command)
            button.pack(side="left", padx=app.metrics.u(2))
            self.action_tooltips.append(add_tooltip(button, f"Insert waypoint {label.lower()} selection"))
            self.buttons.append(button)
        extra = ttk.Frame(self.waypoints_card)
        extra.grid(row=2, column=0, sticky="ew", pady=(app.metrics.u(6), 0))
        for label, command in (("Global shopping list", self.edit_global), ("Reset progress", self.reset)):
            button = action_button(extra, text=label, command=command)
            button.pack(side="left", padx=app.metrics.u(2))
            self.buttons.append(button)
        waypoint = app.ed_ap.waypoint
        if existing_document is None and waypoint.route_loaded:
            try:
                self.document = RouteDocument.load(waypoint.filename)
            except ValueError as error:
                messagebox.showerror("Waypoint editor", str(error), parent=self)
        self.refresh()
        self.refresh_routes()
        form_state = getattr(app, "waypoint_form_state", None)
        if form_state is not None:
            if form_state.get("import"):
                self.import_route()
            else:
                self.begin_form(
                    form_state["entry"],
                    form_state["index"],
                    form_state["global_list"],
                    insert=form_state.get("insert", False),
                )
            self.form.restore(form_state)
            app.waypoint_form_state = None
        self._poll_id = self.after(500, self.poll)
        self.bind("<Destroy>", self.destroyed, add="+")

    def locked(self):
        return self.dialog_open or self.execution_locked()

    def set_game_language(self, code):
        if self.form is not None:
            self.form.set_game_language(code)
        self.app.waypoint_commodity_language = code

    def execution_locked(self):
        return (
            self.app.WP_A_running
            or self.app.ed_ap.waypoint_assist_enabled
            or getattr(self.app.ed_ap.waypoint, "executing", False)
            or self.app.SWP_A_running
        )

    def poll(self):
        self.set_running()
        self._poll_id = self.after(500, self.poll)

    def destroyed(self, event):
        if event.widget is self:
            self.after_cancel(self._poll_id)

    def refresh_label(self):
        filename = self.document.filename
        self.app.wp_filelabel.set(
            ("* " if self.document.dirty else "") + (filename.name if filename else "<new unsaved route>")
        )
        self.sync_route_choice()

    def sync_route_choice(self):
        filename = self.document.filename
        label = next((label for label, path in self.route_paths.items() if path == filename), None)
        self.route_choice.set(
            ("* " if self.document.dirty else "") + (label or (str(filename) if filename else "<new unsaved route>"))
        )

    def refresh_routes(self):
        try:
            filenames = {path.resolve() for path in paths.WAYPOINTS_DIR.glob("*.json") if path.is_file()}
        except OSError as error:
            logger.error("Could not list waypoint routes: %s", error)
            messagebox.showerror("Waypoint routes", str(error), parent=self)
            return
        if self.document.filename is not None:
            filenames.add(self.document.filename)
        self.route_paths = {
            path.name if path.parent == paths.WAYPOINTS_DIR.resolve() else str(path): path
            for path in sorted(filenames, key=lambda path: (path.name.casefold(), str(path)))
        }
        self.route_picker.configure(values=tuple(self.route_paths))
        self.sync_route_choice()

    def select_route(self, _event=None):
        filename = self.route_paths.get(self.route_choice.get())
        if filename is not None and filename != self.document.filename and not self.locked():
            if self.discard():
                self.load_route(filename)
        self.sync_route_choice()

    def refresh(self):
        selection = self.tree.selection()
        scroll = self.tree.yview()
        self.tree.delete(*self.tree.get_children())
        runtime = self.app.ed_ap.waypoint
        issues = self.document.issues()
        self.tree.tag_configure("error", foreground=RED)
        self.tree.tag_configure("warning", foreground=ORANGE)
        same_route = (
            self.document.filename is not None
            and Path(runtime.filename).resolve() == self.document.filename
            and not self.document.dirty
        )
        for index, entry in enumerate(self.document.data["waypoints"]):
            entry_problems = [issue for issue in issues if issue.index == index]
            role = (
                "error" if any(i.severity == "error" for i in entry_problems) else "warning" if entry_problems else ""
            )
            state = runtime.waypoints.get(entry["Id"], {}) if same_route else {}
            progress = "Disabled" if not entry["Enabled"] else "Done" if state.get("Completed") else "Pending"
            remaining = state.get("BuyCommodities", entry["BuyCommodities"])
            sells = state.get("SellCommodities", entry["SellCommodities"])
            self.tree.insert(
                "",
                "end",
                iid=entry["Id"],
                text=entry["SystemName"],
                tags=((role,) if role else ()) + ("odd" if index % 2 else "even",),
                values=(
                    "",
                    entry["StationName"],
                    (f"[{role.upper()}] " if role else "")
                    + progress
                    + (f" | buy {trade_quantity_summary(remaining)}" if remaining else "")
                    + (f" | sell {trade_quantity_summary(sells)}" if sells else ""),
                ),
            )
        self.tree.update_active(self.document.data["waypoints"], self.locked())
        if selection and self.tree.exists(selection[0]):
            self.tree.selection_set(selection[0])
        if scroll:
            self.tree.yview_moveto(scroll[0])
        self.refresh_label()
        self.repeat.set(self.document.data["Repeat"])
        self.update_route_checks()

    def update_route_checks(self):
        issues = self.document.issues()
        errors = sum(issue.severity == "error" for issue in issues)
        warnings = len(issues) - errors + len(self.document.load_notes)
        text = (
            f"Route | {errors} error(s), {warnings} warning(s) (details)" if issues or warnings else "Route | no issues"
        )
        self.route_checks.configure(text=text, foreground=RED if errors else ORANGE if warnings else TEXT)

    def show_selected_checks(self, _event=None):
        self.update_route_checks()

    def show_route_checks(self, _event=None):
        lines = [issue.describe() for issue in self.document.issues()] + self.document.load_notes
        messagebox.showinfo("Route checks", "\n".join(lines) or "No issues found.", parent=self)

    def set_running(self):
        state = "disabled" if self.locked() else "normal"
        for button in self.buttons:
            button.set_disabled(state == "disabled")
        self.route_picker.configure(state="disabled" if self.locked() else "readonly")
        self.repeat_button.configure(state=state)
        if isinstance(self.form, WaypointForm):
            for button in self.form.plot_buttons:
                button.set_disabled(self.app.active_mode is not None or self.app.SWP_A_running)
            self.form.cancel_button.set_disabled(self.app.SWP_A_running)
            if self.app.SWP_A_running:
                self.form.apply_button.set_disabled(True)
            else:
                self.form.validate_live()
        if not self.dialog_open:
            self.refresh()

    def discard(self):
        if self.dialog_open:
            if not messagebox.askokcancel("Unapplied edits", "Discard the open form's edits?", parent=self):
                return False
            self.cancel_form()
        if not self.document.dirty:
            return True
        choice = messagebox.askyesnocancel("Unsaved route", "Save route changes before continuing?", parent=self)
        if choice is None:
            return False
        return self.save() if choice else True

    def new(self):
        if self.locked() or not self.discard():
            return
        self.document = RouteDocument()
        self.refresh()
        self.refresh_routes()

    def open(self):
        if self.locked() or not self.discard():
            return
        filename = filedialog.askopenfilename(
            parent=self, title="Waypoint route", initialdir=paths.WAYPOINTS_DIR, filetypes=(("JSON routes", "*.json"),)
        )
        if not filename:
            return
        self.load_route(filename)

    def change_repeat(self):
        if not self.locked():
            self.document.data["Repeat"] = self.repeat.get()
            self.refresh()

    def toggle_enabled(self, event):
        if self.tree.identify_column(event.x) != "#1" or self.tree.identify_region(event.x, event.y) != "cell":
            return
        row = self.tree.identify_row(event.y)
        if row and not self.locked():
            self.tree.selection_set(row)
            self.toggle_selected()
        if row:
            return "break"

    def toggle_selected(self, _event=None):
        if not self.locked():
            index = self.selected_index()
            if index is not None:
                entry = self.document.data["waypoints"][index]
                entry["Enabled"] = not entry["Enabled"]
                self.refresh()
        return "break"

    def toggle_row(self, row):
        self.tree.selection_set(row)
        self.toggle_selected()

    def double_click(self, event):
        if self.tree.identify_column(event.x) != "#1":
            self.edit()
        return "break"

    def import_legacy(self):
        if self.execution_locked() or (self.dialog_open and not isinstance(self.form, RouteImportForm)):
            return
        if not self.discard():
            return
        filename = filedialog.askopenfilename(
            parent=self,
            title="Import legacy waypoint JSON",
            initialdir=paths.WAYPOINTS_DIR,
            filetypes=(("JSON routes", "*.json"),),
        )
        if not filename:
            return
        try:
            document = RouteDocument.import_legacy(filename)
        except ValueError as error:
            logger.warning("Legacy waypoint import failed: %s", error)
            messagebox.showerror("Legacy import", str(error), parent=self)
            return
        self.document = document
        self.refresh()
        self.refresh_routes()
        messagebox.showinfo("Legacy import", "\n".join(document.load_notes), parent=self)

    def load_route(self, filename):
        try:
            document = RouteDocument.load(filename)
            if not document.load_notes and not any(issue.severity == "error" for issue in document.issues()):
                if not self.app.ed_ap.waypoint.load_waypoint_file(str(filename)):
                    document.load_notes.append(
                        "Opened for editing only: runtime activation failed. Check the technical log and progress file."
                    )
        except ValueError as error:
            messagebox.showerror("Waypoint editor", str(error), parent=self)
            return
        self.document = document
        self.refresh()
        self.refresh_routes()

    def save(self, save_as=False):
        if self.locked():
            return False
        try:
            self.document.validate()
        except ValueError as error:
            messagebox.showerror("Route checks", str(error), parent=self)
            self.refresh()
            return False
        filename = self.document.filename
        if not save_as and filename is not None and not self.document.dirty and self.document.source_version == 2:
            return True
        warnings = [issue.describe() for issue in self.document.issues() if issue.severity == "warning"]
        warnings.extend(self.document.load_notes)
        if warnings and not messagebox.askokcancel(
            "Route warnings", "\n".join(warnings) + "\n\nSave anyway?", parent=self
        ):
            return False
        if filename is not None and filename.is_relative_to(paths.WAYPOINT_EXAMPLES_DIR.resolve()):
            save_as = True
        if save_as or filename is None:
            filename = filedialog.asksaveasfilename(
                parent=self,
                title="Save waypoint route",
                initialdir=paths.WAYPOINTS_DIR,
                defaultextension=".json",
                filetypes=(("JSON routes", "*.json"),),
            )
            if not filename:
                return False
        if Path(filename).exists() and not messagebox.askokcancel(
            "Reset route progress",
            "Saving replaces this route definition and resets all its progress and remaining quantities. Continue?",
            parent=self,
        ):
            return False
        try:
            self.document.save(filename)
            if not self.app.ed_ap.waypoint.load_waypoint_file(str(filename)):
                raise ValueError("Route saved, but activation failed. Check the log before starting.")
        except (OSError, ValueError) as error:
            logger.error("Waypoint editor save failed: %s", error)
            messagebox.showerror("Waypoint editor", str(error), parent=self)
            return False
        self.refresh()
        self.refresh_routes()
        return True

    def prepare_start(self):
        if self.locked():
            return False
        try:
            self.document.validate()
        except ValueError as error:
            messagebox.showerror("Route checks", str(error), parent=self)
            return False
        if self.document.dirty or self.document.filename is None:
            if not self.save():
                return False
        if not any(entry["Enabled"] for entry in self.document.data["waypoints"]):
            messagebox.showerror("Waypoint editor", "Enable at least one waypoint before starting.", parent=self)
            return False
        runtime = self.app.ed_ap.waypoint
        if not runtime.route_loaded or Path(runtime.filename).resolve() != self.document.filename:
            if not runtime.load_waypoint_file(str(self.document.filename)):
                messagebox.showerror("Waypoint editor", "Route activation failed. Check the log.", parent=self)
                return False
        return True

    def selected_index(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return next(i for i, entry in enumerate(self.document.data["waypoints"]) if entry["Id"] == selection[0])

    def form_state(self):
        if self.form is None:
            return None
        return {**self.form.snapshot(), "index": self.form_index, "insert": self.form_insert}

    def import_route(self):
        if self.locked():
            return
        self.dialog_open = True
        self.list_view.grid_remove()
        self.form = RouteImportForm(self, self.app, self.apply_import, self.cancel_form, self.import_legacy)
        self.form.grid(row=0, column=0, sticky="nsew")

    def apply_import(self, entries, append, repeat=False):
        if (
            self.app.WP_A_running
            or self.app.SWP_A_running
            or self.app.ed_ap.waypoint_assist_enabled
            or getattr(self.app.ed_ap.waypoint, "executing", False)
        ):
            messagebox.showerror("Route import", "Stop Waypoint Assist before importing.", parent=self)
            return
        document = copy.deepcopy(self.document) if append else RouteDocument()
        document.data["waypoints"].extend(copy.deepcopy(entries))
        if repeat:
            document.data["Repeat"] = True
        try:
            document.validate()
        except ValueError as error:
            messagebox.showerror("Route import", str(error), parent=self)
            return
        if not append and self.document.dirty:
            choice = messagebox.askyesnocancel(
                "Unsaved route", "Save the current route before replacing its draft?", parent=self
            )
            if choice is None:
                return
            if choice:
                self.dialog_open = False
                try:
                    if not self.save():
                        return
                finally:
                    self.dialog_open = True
        self.document = document
        self.cancel_form()
        self.refresh_routes()

    def begin_form(self, entry, index=None, global_list=False, insert=False):
        self.form_index = index
        self.form_insert = insert
        self.dialog_open = True
        self.list_view.grid_remove()
        self.form = WaypointForm(self, entry, self.apply_form, self.cancel_form, self.app, global_list)
        self.form.grid(row=0, column=0, sticky="nsew")

    def cancel_form(self):
        if self.form is not None:
            self.app.waypoint_commodity_language = self.form.language.get()
            self.form.destroy()
        self.form = None
        self.dialog_open = False
        self.list_view.grid()
        self.set_running()

    def apply_form(self, entry):
        if (
            self.app.WP_A_running
            or self.app.SWP_A_running
            or self.app.ed_ap.waypoint_assist_enabled
            or getattr(self.app.ed_ap.waypoint, "executing", False)
        ):
            messagebox.showerror("Waypoint editor", "Stop Waypoint Assist before applying edits.", parent=self)
            return
        if self.form.global_list:
            self.document.data["GlobalShoppingList"] = entry
        elif self.form_insert:
            self.document.data["waypoints"].insert(self.form_index, entry)
        elif self.form_index is None:
            self.document.data["waypoints"].append(entry)
        else:
            self.document.data["waypoints"][self.form_index] = entry
        self.cancel_form()
        if "Id" in entry:
            self.tree.selection_set(entry["Id"])
            self.tree.see(entry["Id"])

    def add(self):
        if self.locked():
            return
        self.begin_form(new_waypoint())

    def insert(self, after):
        if self.locked():
            return
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("Waypoint editor", "Select a waypoint to insert before or after.", parent=self)
            return
        self.begin_form(new_waypoint(), index + int(after), insert=True)

    def duplicate(self):
        if self.locked():
            return
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("Waypoint editor", "Select a waypoint to duplicate.", parent=self)
            return
        entry = copy.deepcopy(self.document.data["waypoints"][index])
        entry["Id"] = new_waypoint()["Id"]
        self.begin_form(entry, index + 1, insert=True)

    def edit(self):
        index = self.selected_index()
        if self.locked() or index is None:
            return
        self.begin_form(self.document.data["waypoints"][index], index)

    def edit_global(self):
        if self.locked():
            return
        self.begin_form(self.document.data["GlobalShoppingList"], global_list=True)

    def delete(self):
        index = self.selected_index()
        if self.locked() or index is None:
            return
        if messagebox.askokcancel("Delete waypoint", "Delete the selected waypoint?", parent=self):
            del self.document.data["waypoints"][index]
            self.refresh()

    def move(self, offset):
        index = self.selected_index()
        if not self.locked() and index is not None:
            self.document.move(index, offset)
            self.refresh()

    def reset(self):
        if self.locked():
            return
        if self.document.dirty or self.document.filename is None:
            messagebox.showerror("Waypoint editor", "Save this route before resetting its progress.", parent=self)
            return
        self.app.reset_wp_file()
        self.refresh()
