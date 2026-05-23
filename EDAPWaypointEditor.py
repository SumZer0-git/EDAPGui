from __future__ import annotations

import ast
import tkinter as tk
import tkinter.ttk
from builtins import enumerate
from pathlib import Path
from tkinter import ttk, messagebox
import json
import threading
import os
import time
import csv

from tktooltip import ToolTip

import EDAP_data
from EDAPColonizeEditor import CommodityDict, get_resources_required_dict
from EDAP_EDMesg_Interface import (create_edap_client, LoadWaypointFileAction, GalaxyMapTargetSystemByNameAction)
from EDJournal import read_construction
from FleetCarrierMonitorDataParser import FleetCarrierMonitorDataParser, FleetCarrierCargo


def select_treeview_items_by_idx(tree: tkinter.ttk.Treeview, indexes: list[int]):
    """ Select items in a Treeview using a list of indexes. """
    if not tree:
        return

    if len(indexes) == 0:
        return

    # Function to select an item by index
    children = tree.get_children()  # Get all item IDs
    selected_children = []
    for i in indexes:
        if 0 <= i < len(children):  # Check if index is valid
            selected_children.append(children[i])

    # Select the items
    tree.selection_set(selected_children)
    if len(selected_children) > 0:
        tree.see(selected_children[len(selected_children) - 1])  # Scroll to the item (optional)


def remove_non_ascii(text):
    return text.encode('ascii', 'ignore').decode('ascii')


class SearchableCombobox(ttk.Frame):
    def __init__(self, parent, options, on_select_callback, on_cancel_callback):
        super().__init__(parent)
        self.root = self.winfo_toplevel()

        self.options = options
        self.on_select_callback = on_select_callback
        self.on_cancel_callback = on_cancel_callback
        self.dropdown_id = None

        self.entry = ttk.Entry(self, width=24)
        self.entry.bind("<KeyRelease>", self.on_entry_key)
        self.entry.pack(fill="both", expand=True)

        # Use a Toplevel for the dropdown to appear over other widgets
        self.dropdown_toplevel = tk.Toplevel(self)
        self.dropdown_toplevel.withdraw()
        self.dropdown_toplevel.overrideredirect(True)

        # Container for the tree and scrollbar
        container = ttk.Frame(self.dropdown_toplevel)
        container.pack(fill="both", expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(container, orient="vertical")
        self.treeview = ttk.Treeview(container, columns=("name",), show="headings", height=5, yscrollcommand=scrollbar.set)
        self.treeview.heading("name", text="Name", anchor="w")
        self.treeview.column("name", anchor="w")
        self.treeview.column("#0", width=0, stretch=False)

        scrollbar.config(command=self.treeview.yview)

        # Pack them into the container
        scrollbar.pack(side="right", fill="y")
        self.treeview.pack(side="left", fill="both", expand=True)

        self.treeview.bind("<<TreeviewSelect>>", self.on_select)
        for option in self.options:
            self.treeview.insert("", "end", values=(option,))

    def get(self):
        return self.entry.get()

    def set(self, value):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, value)

    def on_entry_key(self, event):
        typed_value = self.entry.get().strip().lower()

        # Clear the treeview
        for item in self.treeview.get_children():
            self.treeview.delete(item)

        # Repopulate with filtered options
        if not typed_value:
            for option in self.options:
                self.treeview.insert("", "end", values=(option,))
        else:
            filtered_options = [option for option in self.options if option.lower().startswith(typed_value)]
            for option in filtered_options:
                self.treeview.insert("", "end", values=(option,))
        self.show_dropdown()

    def on_select(self, event):
        selected_item = self.treeview.selection()
        if selected_item:
            selected_option = self.treeview.item(selected_item[0], "values")[0]
            self.set(selected_option)
            self.hide_dropdown()
            if self.on_select_callback:
                self.on_select_callback(selected_option)

    def on_root_click(self, event):
        # Check if the click was inside the entry or the dropdown
        x, y = event.x_root, event.y_root

        # Check entry widget
        entry_x, entry_y = self.entry.winfo_rootx(), self.entry.winfo_rooty()
        entry_w, entry_h = self.entry.winfo_width(), self.entry.winfo_height()
        in_entry = (entry_x <= x < entry_x + entry_w) and (entry_y <= y < entry_y + entry_h)

        # Check dropdown toplevel (only if it's visible)
        in_dropdown = False
        if self.dropdown_toplevel.winfo_viewable():
            dd_x, dd_y = self.dropdown_toplevel.winfo_rootx(), self.dropdown_toplevel.winfo_rooty()
            dd_w, dd_h = self.dropdown_toplevel.winfo_width(), self.dropdown_toplevel.winfo_height()
            in_dropdown = (dd_x <= x < dd_x + dd_w) and (dd_y <= y < dd_y + dd_h)

        if not in_entry and not in_dropdown:
            self.hide_dropdown()
            if self.on_cancel_callback:
                self.on_cancel_callback()

    def show_dropdown(self, event=None):
        self.update_idletasks() # Ensure widget dimensions are up-to-date
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        width = self.winfo_width()

        self.dropdown_toplevel.geometry(f"{width}x{self.treeview.winfo_reqheight()}+{x}+{y}")
        self.dropdown_toplevel.deiconify()
        self.dropdown_toplevel.lift()
        self.root.bind("<Button-1>", self.on_root_click, add="+")

    def hide_dropdown(self):
        self.root.unbind("<Button-1>")
        self.dropdown_toplevel.withdraw()
        self.entry.selection_clear()


class ShoppingItem:
    def __init__(self, name="", quantity=0):
        self.name = tk.StringVar(value=name)
        self.quantity = tk.IntVar(value=quantity)


class InternalWaypoint:
    def __init__(self, name="", system_name="", station_name=""):
        self.name = tk.StringVar(value=name)
        self.system_name = tk.StringVar(value=system_name)
        self.station_name = tk.StringVar(value=station_name)
        self.galaxy_bookmark_type = tk.StringVar()
        self.galaxy_bookmark_number = tk.IntVar()
        self.system_bookmark_type = tk.StringVar()
        self.system_bookmark_number = tk.IntVar()
        self.sell_commodities = []
        self.buy_commodities = []
        self.update_commodity_count = tk.BooleanVar()
        self.fleet_carrier_transfer = tk.BooleanVar()
        self.skip = tk.BooleanVar()
        self.completed = tk.BooleanVar()
        self.comment = tk.StringVar()


class InternalWaypoints:
    def __init__(self):
        self.waypoints = []


class WaypointEditorTab:
    def __init__(self, parent, ed_waypoint):
        self.ed_waypoint = ed_waypoint
        self.waypoints = InternalWaypoints()
        self.gbl_shoppinglist = InternalWaypoint()
        self.frame = ttk.Frame(parent)
        self.file_watcher_thread = None
        self.watching_filepath: str = ''
        self.last_modified_time = None
        self.mesg_client = create_edap_client(15570, 15571)
        self.commodities = EDAP_data.sorted_commodities()
        self.commodities_with_all = EDAP_data.sorted_commodities()
        self.commodities_with_all.insert(0, 'ALL')
        self._fleetcarrier_cargo = dict[str, FleetCarrierCargo]

        self.root = self.frame.winfo_toplevel()

        # --- Waypoints Tab ---
        self.create_waypoints_tab()

    def create_waypoints_tab(self):
        # Main container for the waypoints tab
        waypoints_container = ttk.Frame(self.frame)
        waypoints_container.pack(fill="both", expand=True, padx=5, pady=5)

        # File operations buttons
        file_ops_frame = ttk.Frame(waypoints_container)
        file_ops_frame.pack(fill="x", pady=5)
        ttk.Button(file_ops_frame, text="New", command=self.new_file).pack(side="left", padx=2)
        ttk.Button(file_ops_frame, text="Open", command=self.open_file).pack(side="left", padx=2)
        btn_open_last = ttk.Button(file_ops_frame, text="Open Last Saved", command=self.open_last_file)
        btn_open_last.pack(side="left", padx=2)
        tip = ToolTip(btn_open_last, msg=f"Opens the last saved waypoint file", delay=1.0, bg="#808080", fg="#FFFFFF")

        self.save_button = ttk.Button(file_ops_frame, text="Save", command=self.save_file)
        self.save_button.pack(side="left", padx=2)
        self.save_button.config(state="disabled")
        ttk.Button(file_ops_frame, text="Save As", command=self.save_as_file).pack(side="left", padx=2)
        btn_reset_list = ttk.Button(file_ops_frame, text="Reset List", command=self.reset_wp_file)
        btn_reset_list.pack(side="left", padx=5)
        tip = ToolTip(btn_reset_list, msg=f"Resets the Complete flag of all Waypoints and restarts at the first Waypoint", delay=1.0, bg="#808080", fg="#FFFFFF")
        ttk.Button(file_ops_frame, text="Import Spansh CSV", command=self.import_spansh_csv).pack(side="right", padx=2)
        ttk.Button(file_ops_frame, text="Import from Inara", command=self.open_inara_import_window).pack(side="right", padx=2)

        # notebook pages
        nb = ttk.Notebook(waypoints_container)
        nb.pack(fill="both", expand=True, padx=5, pady=5)

        page0 = ttk.Frame(nb)
        nb.add(page0, text="Waypoints")  # main page

        page1 = ttk.Frame(nb)
        nb.add(page1, text="Global Shopping List")  # options page

        # === WAYPOINT TAB ===
        # Top frame for waypoints list and buttons
        top_frame = ttk.Frame(page0)
        top_frame.pack(fill="x", expand=False, pady=5)

        # Waypoints list (Treeview)
        columns = ("system_name", "station_name", "skip", "completed", "comment")
        self.waypoints_tree = ttk.Treeview(top_frame, columns=columns, show="headings")

        self.waypoints_tree.heading("system_name", text="System Name")
        self.waypoints_tree.heading("station_name", text="Station Name")
        self.waypoints_tree.heading("skip", text="Skip")
        self.waypoints_tree.heading("completed", text="Completed")
        self.waypoints_tree.heading("comment", text="Comment")

        self.waypoints_tree.column("system_name", width=200)
        self.waypoints_tree.column("station_name", width=200)
        self.waypoints_tree.column("skip", width=50, anchor=tk.CENTER)
        self.waypoints_tree.column("completed", width=70, anchor=tk.CENTER)
        self.waypoints_tree.column("comment", width=70, anchor=tk.W)

        self.waypoints_tree.pack(side="left", fill="both", expand=True)

        self.waypoints_tree.bind("<<TreeviewSelect>>", self.on_waypoint_select)
        self.waypoints_tree.bind("<Double-1>", self.on_cell_double_click)
        self.waypoints_tree.bind("<Button-1>", self.on_tree_click)

        # Waypoint buttons
        waypoint_buttons_frame = ttk.Frame(top_frame)
        waypoint_buttons_frame.pack(side="right", fill="y", padx=(5, 0))

        ttk.Button(waypoint_buttons_frame, text="Up", command=self.move_waypoint_up).pack(padx=5, pady=2, fill="x")
        ttk.Button(waypoint_buttons_frame, text="Down", command=self.move_waypoint_down).pack(padx=5, pady=2, fill="x")
        ttk.Button(waypoint_buttons_frame, text="Add", command=self.add_waypoint).pack(padx=5, pady=2, fill="x")
        ttk.Button(waypoint_buttons_frame, text="Del", command=self.delete_waypoint).pack(padx=5, pady=2, fill="x")
        ttk.Button(waypoint_buttons_frame, text="Add REPEAT", command=self.add_repeat_waypoint).pack(padx=5, pady=2, fill="x")
        ttk.Button(waypoint_buttons_frame, text="Plot to System", command=self.plot_waypoint_system).pack(padx=5, pady=20, fill="x")
        ttk.Button(waypoint_buttons_frame, text="Plot to Station", command=self.plot_waypoint_station).pack(padx=5, pady=2, fill="x")

        # Bottom frame for waypoint options and commodity lists
        bottom_frame = ttk.Frame(page0)
        bottom_frame.pack(fill="both", expand=True, pady=5)

        # Waypoint Options
        waypoint_options_frame = ttk.LabelFrame(bottom_frame, text="Waypoint Options")
        waypoint_options_frame.pack(side="top", fill="x", expand=False, padx=0, pady=0)

        # Station Options
        station_options_frame = ttk.LabelFrame(waypoint_options_frame, text="Station Options")
        station_options_frame.pack(fill="x", padx=5, pady=5)

        # Galaxy Bookmark
        ttk.Label(station_options_frame, text="Galaxy Bookmark Type:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.galaxy_bookmark_type_combo = ttk.Combobox(station_options_frame, values=["", "Favorite", "System", "Body", "Station", "Settlement"])
        self.galaxy_bookmark_type_combo.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(station_options_frame, text="Galaxy Bookmark Number:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.galaxy_bookmark_number_entry = ttk.Entry(station_options_frame)
        self.galaxy_bookmark_number_entry.grid(row=0, column=3, padx=5, pady=2, sticky="ew")

        # System Bookmark
        ttk.Label(station_options_frame, text="System Bookmark Type:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.system_bookmark_type_combo = ttk.Combobox(station_options_frame, values=["", "Favorite", "Body", "Station", "Settlement", "Navigation Panel", "Nav Panel OCR"])
        self.system_bookmark_type_combo.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(station_options_frame, text="System Bookmark Number:").grid(row=1, column=2, padx=5, pady=2, sticky="w")
        self.system_bookmark_number_entry = ttk.Entry(station_options_frame)
        self.system_bookmark_number_entry.grid(row=1, column=3, padx=5, pady=2, sticky="ew")

        # Checkboxes
        self.update_commodity_count_check = ttk.Checkbutton(station_options_frame, text="Update Commodity Count")
        self.update_commodity_count_check.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        self.fleet_carrier_transfer_check = ttk.Checkbutton(station_options_frame, text="Fleet Carrier Transfer")
        self.fleet_carrier_transfer_check.grid(row=2, column=2, columnspan=2, padx=5, pady=5, sticky="w")

        # --- Buy/Sell Commodities ---
        buy_sell_frame = ttk.Frame(bottom_frame)
        buy_sell_frame.pack(side="top", fill="both", expand=True, pady=(5,0))

        # Buy Commodities
        buy_commodities_frame = ttk.LabelFrame(buy_sell_frame, text="Buy Commodities")
        buy_commodities_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.buy_commodities_list = self.create_commodity_list(buy_commodities_frame, "buy")

        # Sell Commodities
        sell_commodities_frame = ttk.LabelFrame(buy_sell_frame, text="Sell Commodities")
        sell_commodities_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        self.sell_commodities_list = self.create_commodity_list(sell_commodities_frame, "sell")

        # === GLOBAL SHOPPING LIST TAB ===
        # Top frame for waypoints list and buttons
        top_frame1 = ttk.Frame(page1)
        top_frame1.pack(fill="both", expand=False, pady=5)

        # Options
        gbl_waypoint_options_frame = ttk.LabelFrame(top_frame1, text="Options")
        gbl_waypoint_options_frame.pack(side="top", fill="x", expand=False, padx=5, pady=0)

        # Checkboxes
        self._gbl_update_commodity_count_check = ttk.Checkbutton(gbl_waypoint_options_frame, text="Update Commodity Count")
        self._gbl_update_commodity_count_check.grid(row=2, column=0, columnspan=1, padx=5, pady=5, sticky="w")

        load_const_btn = ttk.Button(gbl_waypoint_options_frame, text="Load Construction Commodities", command=self.load_const_comm)
        load_const_btn.grid(row=2, column=1, columnspan=1, padx=5, pady=5, sticky="w")

        # Global Buy Commodities
        gbl_buy_commodities_frame = ttk.LabelFrame(top_frame1, text="Global Buy Commodities")
        gbl_buy_commodities_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.gbl_buy_commodities_list = self.create_commodity_list(gbl_buy_commodities_frame, "gbl_buy")

    def open_inara_import_window(self):
        inara_window = tk.Toplevel(self.frame)
        inara_window.title("Import from Inara")
        inara_window.transient(self.root)
        inara_window.grab_set()

        frame = ttk.Frame(inara_window)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Paste Inara trade route data here:").pack(anchor="w")
        inara_text = tk.Text(frame, height=10)
        inara_text.pack(fill="x", pady=5)
        inara_text.focus_set()

        def on_add():
            self.add_inara_route(inara_text.get("1.0", "end-1c"))
            inara_window.destroy()

        ttk.Button(frame, text="Add to Waypoints", command=on_add).pack(pady=5)

    def create_commodity_list(self, parent, list_type):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)

        columns = ("name", "quantity", "add_sub")
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        tree.heading("name", text="Name")
        tree.column("name", width=150)
        tree.heading("quantity", text="Quantity")
        tree.column("quantity", width=70, anchor=tk.W)
        tree.heading("add_sub", text="Add/Sub")
        tree.column("add_sub", width=70, anchor=tk.W)
        tree.pack(side="left", fill="both", expand=True)

        tree.bind("<Double-1>", lambda event, lt=list_type: self.on_commodity_cell_double_click(event, lt))

        buttons_frame = ttk.Frame(frame)
        buttons_frame.pack(side="right", fill="y", padx=(5,0))

        if list_type == "buy":
            ttk.Button(buttons_frame, text="Up", command=self.move_buy_commodity_up).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Down", command=self.move_buy_commodity_down).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Add", command=self.add_buy_commodity).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Del", command=self.delete_buy_commodity).pack(padx=5, pady=2, fill="x")
        elif list_type == "sell":
            ttk.Button(buttons_frame, text="Up", command=self.move_sell_commodity_up).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Down", command=self.move_sell_commodity_down).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Add", command=self.add_sell_commodity).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Del", command=self.delete_sell_commodity).pack(padx=5, pady=2, fill="x")
        if list_type == "gbl_buy":
            ttk.Button(buttons_frame, text="Up", command=self.move_gbl_buy_commodity_up).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Down", command=self.move_gbl_buy_commodity_down).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Add", command=self.add_gbl_buy_commodity).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Del", command=self.delete_gbl_buy_commodity).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Del All", command=self.delete_all_gbl_buy_commodity).pack(padx=5, pady=2, fill="x")

        return tree

    def new_file(self):
        self.waypoints = InternalWaypoints()
        self.ed_waypoint.waypoints = {}
        self.ed_waypoint.filename = None
        self.update_ui()
        self.save_button.config(state="disabled")

    def open_file(self):
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            title="Open Waypoint File",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
            initialdir="./waypoints"
        )
        if filepath:
            self.editor_load_waypoint_file(filepath)

    def open_last_file(self):
        if self.ed_waypoint.filename:
            self.editor_load_waypoint_file(self.ed_waypoint.filename)

    def reset_wp_file(self):
        if self.ed_waypoint.waypoints:
            if self.ed_waypoint.ap.waypoint_assist_enabled:
                mb = messagebox.showwarning("Waypoint List Warning", "Disable Waypoint Assist before resetting the list.")
            else:
                mb = messagebox.askokcancel("Waypoint List Reset", "Resetting Waypoints will clear the Complete flag on all Waypoints and the first Waypoint will be selected as the next waypoint.")
                if mb:
                    self.ed_waypoint.mark_all_waypoints_not_complete()
        else:
            mb = messagebox.showwarning("Waypoint List Warning", "Waypoints list not loaded.")

    def save_file(self):
        if self.ed_waypoint.filename:
            self.save_waypoint_file(self.ed_waypoint.filename)

    def save_as_file(self):
        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(
            title="Save Waypoint File",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
            initialdir="./waypoints",
            defaultextension=".json"
        )
        if filepath:
            self.save_waypoint_file(filepath)
            self.save_button.config(state="normal")

    def import_spansh_csv(self):
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            title="Import Spansh CSV File",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                mb = messagebox.askyesno("Spansh Import","Include Body Name and/or Station Name?")
                include_body = mb

                last_system = ''
                last_station = ''
                for row in reader:
                    if isinstance(row, dict):
                        system_name = row.get("System Name")
                        body_name = row.get("Body Name", "")

                        if system_name:
                            station_name = ''
                            if include_body:
                                station_name = body_name

                            # Check if this is a new system/body
                            if system_name != last_system or station_name != last_station:
                                # Use system name for both waypoint name and system name for simplicity
                                new_waypoint = InternalWaypoint(name=system_name, system_name=system_name, station_name=station_name)
                                self.waypoints.waypoints.append(new_waypoint)

                                last_system = system_name
                                last_station = station_name

            self.update_waypoints_list()
            messagebox.showinfo("Import Successful", f"Imported waypoints from {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import CSV file: {e}")

    def editor_load_waypoint_file(self, filepath):
        filename = './waypoints/' + Path(filepath).name
        if not os.path.exists(filename):
            return False

        try:
            # Load the waypoint file in the Waypoint system, and editor
            if self.ed_waypoint.load_waypoint_file(filename):
                self.populate_internal_waypoints()
                self.update_ui()
                self.start_file_watcher(filename)
                self.save_button.config(state="normal")
        except json.JSONDecodeError:
            messagebox.showerror("Error", f"Invalid JSON file: {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load waypoint file: {e}")

    def save_waypoint_file(self, filepath):

        # Add global shopping list and waypoints
        waypoints_to_save = self.convert_to_raw_waypoints()

        filename = './waypoints/' + Path(filepath).name
        self.ed_waypoint.write_waypoints(data=waypoints_to_save, filename=filename)
        self.ed_waypoint.filename = filename

        # Update the file watcher's last modified time so that the save
        # does not get detected as an external change and trigger a reload.
        if self.watching_filepath:
            try:
                self.last_modified_time = os.path.getmtime(filename)
            except FileNotFoundError:
                pass

    def start_file_watcher(self, filepath):
        if self.file_watcher_thread and self.file_watcher_thread.is_alive():
            # Stop the previous watcher if it's running
            self.watching_filepath = ''  # This will stop the loop in the thread
            self.file_watcher_thread.join()

        self.watching_filepath = filepath
        self.last_modified_time = os.path.getmtime(filepath)

        self.file_watcher_thread = threading.Thread(target=self.watch_file, daemon=True)
        self.file_watcher_thread.start()

    def watch_file(self):
        while self.watching_filepath:
            try:
                modified_time = os.path.getmtime(self.watching_filepath)
                if modified_time != self.last_modified_time:
                    self.last_modified_time = modified_time
                    # File has changed, reload it
                    # We need to schedule the reload on the main thread
                    self.frame.after(0, self.editor_load_waypoint_file, self.watching_filepath)
            except FileNotFoundError:
                # The file might have been deleted
                self.watching_filepath = ''

            time.sleep(1) # Poll every second

    def populate_internal_waypoints(self):
        self.waypoints = InternalWaypoints()
        raw_waypoints = self.ed_waypoint.waypoints

        for key, value in raw_waypoints.items():
            if key == "GlobalShoppingList":
                sl = InternalWaypoint(name=key)
                sl.update_commodity_count.set(value.get('UpdateCommodityCount', False))
                sl.buy_commodities = [ShoppingItem(k, v) for k, v in value.get('BuyCommodities', {}).items()]
                self.gbl_shoppinglist = sl
            else:
                wp = InternalWaypoint(name=key)
                wp.system_name.set(value.get('SystemName', ''))
                wp.station_name.set(value.get('StationName', ''))
                wp.galaxy_bookmark_type.set(value.get('GalaxyBookmarkType', ''))
                wp.galaxy_bookmark_number.set(value.get('GalaxyBookmarkNumber', 0))
                wp.system_bookmark_type.set(value.get('SystemBookmarkType', ''))
                wp.system_bookmark_number.set(value.get('SystemBookmarkNumber', 0))
                wp.update_commodity_count.set(value.get('UpdateCommodityCount', False))
                wp.fleet_carrier_transfer.set(value.get('FleetCarrierTransfer', False))
                wp.skip.set(value.get('Skip', False))
                wp.completed.set(value.get('Completed', False))
                wp.comment.set(value.get('Comment', ''))
                wp.buy_commodities = [ShoppingItem(k, v) for k, v in value.get('BuyCommodities', {}).items()]
                wp.sell_commodities = [ShoppingItem(k, v) for k, v in value.get('SellCommodities', {}).items()]
                self.waypoints.waypoints.append(wp)

    def convert_to_raw_waypoints(self):
        raw_waypoints = {}

        # Shopping list
        if self.gbl_shoppinglist:
            wp = self.gbl_shoppinglist
            raw_wp = {
                'SystemName': wp.system_name.get(),
                'StationName': wp.station_name.get(),
                'GalaxyBookmarkType': wp.galaxy_bookmark_type.get(),
                'GalaxyBookmarkNumber': wp.galaxy_bookmark_number.get(),
                'SystemBookmarkType': wp.system_bookmark_type.get(),
                'SystemBookmarkNumber': wp.system_bookmark_number.get(),
                'UpdateCommodityCount': wp.update_commodity_count.get(),
                'FleetCarrierTransfer': wp.fleet_carrier_transfer.get(),
                'Skip': wp.skip.get(),
                'Completed': wp.completed.get(),
                'Comment': wp.comment.get(),
                'BuyCommodities': {item.name.get(): item.quantity.get() for item in wp.buy_commodities},
                'SellCommodities': {item.name.get(): item.quantity.get() for item in wp.sell_commodities}
            }
            raw_waypoints['GlobalShoppingList'] = raw_wp

        # Waypoints
        for i, wp in enumerate(self.waypoints.waypoints):
            raw_wp = {
                'SystemName': wp.system_name.get(),
                'StationName': wp.station_name.get(),
                'GalaxyBookmarkType': wp.galaxy_bookmark_type.get(),
                'GalaxyBookmarkNumber': wp.galaxy_bookmark_number.get(),
                'SystemBookmarkType': wp.system_bookmark_type.get(),
                'SystemBookmarkNumber': wp.system_bookmark_number.get(),
                'UpdateCommodityCount': wp.update_commodity_count.get(),
                'FleetCarrierTransfer': wp.fleet_carrier_transfer.get(),
                'Skip': wp.skip.get(),
                'Completed': wp.completed.get(),
                'Comment': wp.comment.get(),
                'BuyCommodities': {item.name.get(): item.quantity.get() for item in wp.buy_commodities},
                'SellCommodities': {item.name.get(): item.quantity.get() for item in wp.sell_commodities}
            }
            raw_waypoints[wp.name.get() or str(i)] = raw_wp

        return raw_waypoints

    def update_ui(self):
        self.update_waypoints_list()
        self.update_gbl_shoppinglist_list()
        self.on_waypoint_select(None)

    def update_waypoints_list(self):
        # Clear existing items
        for item in self.waypoints_tree.get_children():
            self.waypoints_tree.delete(item)

        # Add new items
        for i, wp in enumerate(self.waypoints.waypoints):
            self.waypoints_tree.insert('', 'end', values=(
                wp.system_name.get(),
                wp.station_name.get(),
                "✓" if wp.skip.get() else "",
                "✓" if wp.completed.get() else "",
                wp.comment.get()
            ))

    def update_gbl_shoppinglist_list(self):
        # Update commodity lists
        self._gbl_update_commodity_count_check.config(variable=self.gbl_shoppinglist.update_commodity_count)
        self.update_commodity_list(self.gbl_shoppinglist.buy_commodities, self.gbl_buy_commodities_list)

    def on_waypoint_select(self, event):
        selected_item = self.waypoints_tree.selection()
        if selected_item:
            index = self.waypoints_tree.index(selected_item[0])
            wp = self.waypoints.waypoints[index]

            # Bind widgets to the selected waypoint's variables
            self.galaxy_bookmark_type_combo.config(textvariable=wp.galaxy_bookmark_type)
            self.galaxy_bookmark_number_entry.config(textvariable=wp.galaxy_bookmark_number)
            self.system_bookmark_type_combo.config(textvariable=wp.system_bookmark_type)
            self.system_bookmark_number_entry.config(textvariable=wp.system_bookmark_number)
            self.update_commodity_count_check.config(variable=wp.update_commodity_count)
            self.fleet_carrier_transfer_check.config(variable=wp.fleet_carrier_transfer)

            # Update commodity lists
            self.update_commodity_list(wp.buy_commodities, self.buy_commodities_list)
            self.update_commodity_list(wp.sell_commodities, self.sell_commodities_list)
        else:
            # Clear the bindings if no waypoint is selected
            dummy = tk.StringVar()
            self.galaxy_bookmark_type_combo.config(textvariable=dummy)
            self.galaxy_bookmark_number_entry.config(textvariable=dummy)
            self.system_bookmark_type_combo.config(textvariable=dummy)
            self.system_bookmark_number_entry.config(textvariable=dummy)
            self.update_commodity_count_check.config(variable=dummy)
            self.fleet_carrier_transfer_check.config(variable=dummy)

            self.update_commodity_list([], self.buy_commodities_list)
            self.update_commodity_list([], self.sell_commodities_list)

    def on_tree_click(self, event):
        region = self.waypoints_tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.waypoints_tree.identify_column(event.x)
        column_index = int(column.replace('#', '')) - 1

        item_id = self.waypoints_tree.identify_row(event.y)
        if not item_id:
            return

        item_index = self.waypoints_tree.index(item_id)
        wp = self.waypoints.waypoints[item_index]

        if column_index == 2: # Skip column
            wp.skip.set(not wp.skip.get())
            self.update_waypoints_list()
        elif column_index == 3: # Completed column
            wp.completed.set(not wp.completed.get())
            self.update_waypoints_list()

    def on_cell_double_click(self, event):
        region = self.waypoints_tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.waypoints_tree.identify_column(event.x)
        column_index = int(column.replace('#', '')) - 1

        # We only want to edit the system, station and comment columns by index
        system_col = 0
        station_col = 1
        comment_col = 4
        if column_index not in [system_col, station_col, comment_col]:
            return

        item_id = self.waypoints_tree.identify_row(event.y)
        item_index = self.waypoints_tree.index(item_id)

        x, y, width, height = self.waypoints_tree.bbox(item_id, column)

        entry_var = tk.StringVar()
        entry = ttk.Entry(self.waypoints_tree, textvariable=entry_var, font=ttk.Style().lookup('TEntry', 'font'))

        # Ensure the entry is tall enough and centered
        entry_req_height = entry.winfo_reqheight()
        final_height = max(height, entry_req_height)
        y_centered = y + (height - final_height) // 2

        entry.place(x=x, y=y_centered, width=width, height=final_height, anchor='nw')

        current_value = self.waypoints_tree.item(item_id, "values")[column_index]
        entry_var.set(current_value)
        entry.focus_set()
        entry.select_range(0, 'end')
        entry.icursor('end')

        def save_edit(event):
            new_value = entry_var.get()
            wp = self.waypoints.waypoints[item_index]
            if column_index == system_col:
                wp.system_name.set(new_value)
            elif column_index == station_col:
                wp.station_name.set(new_value)
            elif column_index == comment_col:
                wp.comment.set(new_value)

            self.update_waypoints_list()
            entry.destroy()

        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", save_edit)

    def on_commodity_cell_double_click(self, event, list_type):
        # selected_waypoint = self.get_selected_waypoint()
        # if not selected_waypoint:
        #     return

        treeview = event.widget  # Capture the treeview widget
        region = treeview.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = treeview.identify_column(event.x)
        column_index = int(column.replace('#', '')) - 1

        item_id = treeview.identify_row(event.y)
        if not item_id:
            return

        item_index = treeview.index(item_id)

        if list_type == "buy":
            selected_waypoint = self.get_selected_waypoint()
            if not selected_waypoint:
                return
            commodity_list = self.get_selected_waypoint().buy_commodities
        elif list_type == "sell":
            selected_waypoint = self.get_selected_waypoint()
            if not selected_waypoint:
                return
            commodity_list = self.get_selected_waypoint().sell_commodities
        elif list_type == "gbl_buy":
            selected_waypoint = self.get_gbl_shoppinglist_waypoint()
            if not selected_waypoint:
                return
            commodity_list = self.get_gbl_shoppinglist_waypoint().buy_commodities
        else:
            return  # Should not happen

        x, y, width, height = treeview.bbox(item_id, column)

        if column_index == 0:  # Name column
            def on_select_callback(selected_value):
                commodity_list[item_index].name.set(selected_value)
                self.update_commodity_list(commodity_list, treeview)
                entry.hide_dropdown()
                entry.destroy()

            def on_cancel_callback():
                entry.hide_dropdown()
                entry.destroy()

            entry = SearchableCombobox(treeview, self.commodities_with_all, on_select_callback, on_cancel_callback)
            entry.entry.config(font=ttk.Style().lookup('TEntry', 'font'))

            # Ensure the entry is tall enough and centered
            entry_req_height = entry.entry.winfo_reqheight()
            final_height = max(height, entry_req_height)
            y_centered = y + (height - final_height) // 2

            entry.place(x=x, y=y_centered, width=width, height=final_height, anchor='nw')
            current_value = treeview.item(item_id, "values")[column_index]
            entry.set(current_value)
            entry.show_dropdown()
            entry.entry.focus_set()
            entry.entry.select_range(0, 'end')
            entry.entry.icursor('end')

            def _save_and_destroy_if_needed(widget_to_destroy):
                # This check runs after a short delay.
                # If the widget still exists, it means the user clicked away
                # without making a selection. If they made a selection,
                # the on_select_callback would have already destroyed it.
                try:
                    if widget_to_destroy.winfo_exists():
                        new_value = widget_to_destroy.get()
                        commodity_list[item_index].name.set(new_value)
                        self.update_commodity_list(commodity_list, treeview)
                        widget_to_destroy.hide_dropdown()
                        widget_to_destroy.destroy()
                except tk.TclError:
                    # Widget was already destroyed.
                    pass

            def save_edit(event):
                # When focus is lost or Return is pressed, schedule a check.
                # This delay handles the race condition between FocusOut and TreeviewSelect.
                self.frame.after(50, lambda: _save_and_destroy_if_needed(entry))

            def cancel_edit(cancel_event):
                entry.hide_dropdown()
                entry.destroy()

            entry.entry.bind("<Return>", save_edit)
            entry.entry.bind("<Escape>", cancel_edit)

        elif column_index == 1:  # Quantity column
            entry_var = tk.StringVar()
            entry = ttk.Entry(treeview, textvariable=entry_var, font=ttk.Style().lookup('TEntry', 'font'))

            # Ensure the entry is tall enough and centered
            entry_req_height = entry.winfo_reqheight()
            final_height = max(height, entry_req_height)
            y_centered = y + (height - final_height) // 2

            entry.place(x=x, y=y_centered, width=width, height=final_height, anchor='nw')
            entry_var.set(treeview.item(item_id, "values")[column_index])
            entry.focus_set()
            entry.select_range(0, 'end')
            entry.icursor('end')

            def save_edit(save_event):
                try:
                    new_value = entry_var.get()
                    commodity_list[item_index].quantity.set(int(new_value))
                except ValueError:
                    pass # Ignore invalid input
                finally:
                    self.update_commodity_list(commodity_list, treeview)
                    entry.destroy()

            def cancel_edit(cancel_event):
                entry.destroy()

            entry.bind("<Return>", save_edit)
            entry.bind("<FocusOut>", save_edit)
            entry.bind("<Escape>", cancel_edit)

        elif column_index == 2:  # Add/Sub qty column
            entry_var = tk.StringVar()
            entry = ttk.Entry(treeview, textvariable=entry_var, font=ttk.Style().lookup('TEntry', 'font'))

            # Ensure the entry is tall enough and centered
            entry_req_height = entry.winfo_reqheight()
            final_height = max(height, entry_req_height)
            y_centered = y + (height - final_height) // 2

            entry.place(x=x, y=y_centered, width=width, height=final_height, anchor='nw')
            entry_var.set(treeview.item(item_id, "values")[column_index])
            entry.focus_set()
            entry.select_range(0, 'end')
            entry.icursor('end')

            def save_edit(save_event):
                try:
                    new_value = entry_var.get()
                    cur = commodity_list[item_index].quantity.get()
                    commodity_list[item_index].quantity.set(cur + int(new_value))
                except ValueError:
                    pass # Ignore invalid input
                finally:
                    self.update_commodity_list(commodity_list, treeview)
                    entry.destroy()

            def cancel_edit(cancel_event):
                entry.destroy()

            entry.bind("<Return>", save_edit)
            entry.bind("<FocusOut>", save_edit)
            entry.bind("<Escape>", cancel_edit)

    def update_commodity_list(self, commodity_list, treeview):
        for item in treeview.get_children():
            treeview.delete(item)

        for i, item in enumerate(commodity_list):
            treeview.insert('', 'end', values=(item.name.get(), item.quantity.get(), ''))

    def add_waypoint(self):
        new_waypoint = InternalWaypoint(system_name="New System")
        self.waypoints.waypoints.append(new_waypoint)
        self.update_waypoints_list()

        # Select the new item at the bottom of the list
        selected_indexes = [len(self.waypoints.waypoints) - 1]
        select_treeview_items_by_idx(self.waypoints_tree, selected_indexes)

    def add_repeat_waypoint(self):
        new_waypoint = InternalWaypoint(system_name="REPEAT")
        self.waypoints.waypoints.append(new_waypoint)
        self.update_waypoints_list()

        # Select the new item at the bottom of the list
        selected_indexes = [len(self.waypoints.waypoints) - 1]
        select_treeview_items_by_idx(self.waypoints_tree, selected_indexes)

    def plot_waypoint_system(self):
        selected_item = self.waypoints_tree.selection()
        if selected_item:
            index = self.waypoints_tree.index(selected_item[0])
            wp = self.waypoints.waypoints[index]
            sys_name = wp.system_name.get()
            # TODO - replace this with direct EDAP control in case client comms not working?
            # self.mesg_client.publish(GalaxyMapTargetSystemByNameAction(name=sys_name))
            res = self.ed_waypoint.ap.galaxy_map.goto_galaxy_map()
            if res:
                self.ed_waypoint.ap.galaxy_map.set_gal_map_destination_text(self.ed_waypoint.ap, sys_name, target_select_cb=None)

    def plot_waypoint_station(self):
        selected_item = self.waypoints_tree.selection()
        if selected_item:
            index = self.waypoints_tree.index(selected_item[0])
            wp = self.waypoints.waypoints[index]
            sys_name = wp.system_name.get()
            sys_name = wp.station_name.get()
            galaxy_bookmark_type = wp.galaxy_bookmark_type.get()
            galaxy_bookmark_number = wp.galaxy_bookmark_number.get()
            system_bookmark_type = wp.system_bookmark_type.get()
            system_bookmark_number = wp.system_bookmark_number.get()

            if galaxy_bookmark_number > 0:
                res = self.ed_waypoint.ap.galaxy_map.goto_galaxy_map()
                if res:
                    self.ed_waypoint.ap.galaxy_map.set_gal_map_dest_bookmark(self.ed_waypoint.ap, galaxy_bookmark_type, galaxy_bookmark_number)
            elif system_bookmark_number > 0:
                res = self.ed_waypoint.ap.system_map.goto_system_map()
                if res:
                    self.ed_waypoint.ap.system_map.set_sys_map_dest_bookmark(self.ed_waypoint.ap, system_bookmark_type, system_bookmark_number)

    def delete_waypoint(self):
        selected_item = self.waypoints_tree.selection()
        if selected_item:
            for item in selected_item:
                index = self.waypoints_tree.index(item)
                del self.waypoints.waypoints[index]
            self.update_waypoints_list()

    def move_waypoint_up(self):
        selected_item = self.waypoints_tree.selection()
        selected_indexes = []
        if selected_item:
            for item in selected_item:
                index = self.waypoints_tree.index(item)
                if index > 0:
                    selected_indexes.append(index - 1)
                    self.waypoints.waypoints.insert(index - 1, self.waypoints.waypoints.pop(index))
            self.update_waypoints_list()
            # Reselect previous selection
            select_treeview_items_by_idx(self.waypoints_tree, selected_indexes)

    def move_waypoint_down(self):
        selected_item = self.waypoints_tree.selection()
        selected_indexes = []
        if selected_item:
            for item in reversed(selected_item):
                index = self.waypoints_tree.index(item)
                if index < len(self.waypoints.waypoints) - 1:
                    selected_indexes.append(index + 1)
                    self.waypoints.waypoints.insert(index + 1, self.waypoints.waypoints.pop(index))
            self.update_waypoints_list()
            # Reselect previous selection
            select_treeview_items_by_idx(self.waypoints_tree, selected_indexes)

    def get_selected_waypoint(self):
        selected_item = self.waypoints_tree.selection()
        if selected_item:
            index = self.waypoints_tree.index(selected_item[0])
            return self.waypoints.waypoints[index]
        return None

    def get_gbl_shoppinglist_waypoint(self):
        if self.gbl_shoppinglist:
            return self.gbl_shoppinglist
        return None

    def add_buy_commodity(self):
        wp = self.get_selected_waypoint()
        if wp:
            wp.buy_commodities.append(ShoppingItem("New Commodity", 1))
            self.update_commodity_list(wp.buy_commodities, self.buy_commodities_list)

            # Select the new item at the bottom of the list
            selected_indexes = [len(wp.buy_commodities) - 1]
            select_treeview_items_by_idx(self.buy_commodities_list, selected_indexes)

    def delete_buy_commodity(self):
        wp = self.get_selected_waypoint()
        if wp:
            selected_item = self.buy_commodities_list.selection()
            if selected_item:
                for item in selected_item:
                    index = self.buy_commodities_list.index(item)
                    del wp.buy_commodities[index]
                self.update_commodity_list(wp.buy_commodities, self.buy_commodities_list)

    def move_buy_commodity_up(self):
        wp = self.get_selected_waypoint()
        if wp:
            selected_item = self.buy_commodities_list.selection()
            selected_indexes = []
            if selected_item:
                for item in selected_item:
                    index = self.buy_commodities_list.index(item)
                    if index > 0:
                        selected_indexes.append(index - 1)
                        wp.buy_commodities.insert(index - 1, wp.buy_commodities.pop(index))
                self.update_commodity_list(wp.buy_commodities, self.buy_commodities_list)
                # Reselect previous selection
                select_treeview_items_by_idx(wp.buy_commodities, selected_indexes)

    def move_buy_commodity_down(self):
        wp = self.get_selected_waypoint()
        if wp:
            selected_item = self.buy_commodities_list.selection()
            selected_indexes = []
            if selected_item:
                for item in reversed(selected_item):
                    index = self.buy_commodities_list.index(item)
                    if index < len(wp.buy_commodities) - 1:
                        selected_indexes.append(index + 1)
                        wp.buy_commodities.insert(index + 1, wp.buy_commodities.pop(index))
                self.update_commodity_list(wp.buy_commodities, self.buy_commodities_list)
                # Reselect previous selection
                select_treeview_items_by_idx(wp.buy_commodities, selected_indexes)

    def add_gbl_buy_commodity(self):
        wp = self.get_gbl_shoppinglist_waypoint()
        if wp:
            wp.buy_commodities.append(ShoppingItem("New Commodity", 1))
            self.update_commodity_list(wp.buy_commodities, self.gbl_buy_commodities_list)

            # Select the new item at the bottom of the list
            selected_indexes = [len(wp.buy_commodities) - 1]
            select_treeview_items_by_idx(self.gbl_buy_commodities_list, selected_indexes)

    def delete_gbl_buy_commodity(self):
        wp = self.get_gbl_shoppinglist_waypoint()
        if wp:
            selected_item = self.gbl_buy_commodities_list.selection()
            if selected_item:
                for item in selected_item:
                    index = self.gbl_buy_commodities_list.index(item)
                    del wp.buy_commodities[index]
                self.update_commodity_list(wp.buy_commodities, self.gbl_buy_commodities_list)

    def delete_all_gbl_buy_commodity(self):
        wp = self.get_gbl_shoppinglist_waypoint()
        if wp:
            wp.buy_commodities.clear()
            self.update_commodity_list(wp.buy_commodities, self.gbl_buy_commodities_list)

    def load_fleetcarrier_file(self):
        """ Load the fleet carrier commodity data. """
        parser = FleetCarrierMonitorDataParser()
        parser.file_path = r"C:\Users\shuttle\AppData\Local\EDMarketConnector\plugins\fleetcarriermonitor\FleetCarrier.V2V-65W.json"
        parser.get_fleetcarrier_data()
        if parser.current_data:
            self._fleetcarrier_cargo = parser.get_consolidated_cargo_dict()

    def load_const_comm(self):
        self.commodities: dict[str, CommodityDict] = {}

        # Load Fleet Carrier data
        self.load_fleetcarrier_file()

        # Load Global Shopping List waypoint
        wp = self.get_gbl_shoppinglist_waypoint()
        if wp:
            # Load construction dict
            filepath = './configs/construction.json'
            if os.path.exists(filepath):
                const_sites = read_construction(filepath)
                if const_sites:
                    for key, value in const_sites.items():
                        if value.get('Include', True):
                            res_required = get_resources_required_dict(const_sites, key)
                            for name_loc, item in res_required.items():
                                # Find if the item is in the Fleet Carrier
                                fc_qty = 0
                                if self._fleetcarrier_cargo:
                                    if name_loc in self._fleetcarrier_cargo:
                                        fc_qty = self._fleetcarrier_cargo[name_loc]['qty']

                                if name_loc in self.commodities:
                                    com = self.commodities[name_loc]
                                    com['required_amount'] = com['required_amount'] + item['required_amount']
                                    com['provided_amount'] = com['provided_amount'] + item['provided_amount']
                                    com['need'] = com['required_amount'] - com['provided_amount']
                                    com['to_buy'] = com['need'] - com['on_fleet_carrier']
                                else:
                                    self.commodities[name_loc] = CommodityDict(name=item["name"],
                                                                               name_localised=item["name_localised"],
                                                                               required_amount=item["required_amount"],
                                                                               provided_amount=item["provided_amount"],
                                                                               payment=item["payment"],
                                                                               need=item['required_amount'] - item['provided_amount'],
                                                                               on_fleet_carrier=fc_qty,
                                                                               to_buy=item['required_amount'] - item['provided_amount'] - fc_qty)

                    # Process each commodity
                    for key, com in self.commodities.items():
                        name_loc = com['name_localised']
                        to_buy = com['to_buy']

                        if to_buy > 0:
                            found = False
                            for comm in wp.buy_commodities:
                                if comm.name.get() == name_loc:
                                    comm.quantity.set(comm.quantity.get() + to_buy)
                                    found = True
                                    break

                            if not found:
                                wp.buy_commodities.append(ShoppingItem(name_loc, to_buy))

            self.update_commodity_list(wp.buy_commodities, self.gbl_buy_commodities_list)

    def move_gbl_buy_commodity_up(self):
        wp = self.get_gbl_shoppinglist_waypoint()
        if wp:
            selected_item = self.gbl_buy_commodities_list.selection()
            selected_indexes = []
            if selected_item:
                for item in selected_item:
                    index = self.gbl_buy_commodities_list.index(item)
                    if index > 0:
                        selected_indexes.append(index - 1)
                        wp.buy_commodities.insert(index - 1, wp.buy_commodities.pop(index))
                self.update_commodity_list(wp.buy_commodities, self.gbl_buy_commodities_list)
                # Reselect previous selection
                select_treeview_items_by_idx(self.gbl_buy_commodities_list, selected_indexes)

    def move_gbl_buy_commodity_down(self):
        wp = self.get_gbl_shoppinglist_waypoint()
        if wp:
            selected_item = self.gbl_buy_commodities_list.selection()
            selected_indexes = []
            if selected_item:
                for item in reversed(selected_item):
                    index = self.gbl_buy_commodities_list.index(item)
                    if index < len(wp.buy_commodities) - 1:
                        selected_indexes.append(index + 1)
                        wp.buy_commodities.insert(index + 1, wp.buy_commodities.pop(index))
                self.update_commodity_list(wp.buy_commodities, self.gbl_buy_commodities_list)
                # Reselect previous selection
                select_treeview_items_by_idx(self.gbl_buy_commodities_list, selected_indexes)

    def add_sell_commodity(self):
        wp = self.get_selected_waypoint()
        if wp:
            wp.sell_commodities.append(ShoppingItem("New Commodity", 1))
            self.update_commodity_list(wp.sell_commodities, self.sell_commodities_list)

            # Select the new item at the bottom of the list
            selected_indexes = [len(wp.sell_commodities) - 1]
            select_treeview_items_by_idx(self.sell_commodities_list, selected_indexes)

    def delete_sell_commodity(self):
        wp = self.get_selected_waypoint()
        if wp:
            selected_item = self.sell_commodities_list.selection()
            if selected_item:
                for item in selected_item:
                    index = self.sell_commodities_list.index(item)
                    del wp.sell_commodities[index]
                self.update_commodity_list(wp.sell_commodities, self.sell_commodities_list)

    def move_sell_commodity_up(self):
        wp = self.get_selected_waypoint()
        if wp:
            selected_item = self.sell_commodities_list.selection()
            selected_indexes = []
            if selected_item:
                for item in selected_item:
                    index = self.sell_commodities_list.index(item)
                    if index > 0:
                        selected_indexes.append(index - 1)
                        wp.sell_commodities.insert(index - 1, wp.sell_commodities.pop(index))
                self.update_commodity_list(wp.sell_commodities, self.sell_commodities_list)
                # Reselect previous selection
                select_treeview_items_by_idx(wp.sell_commodities, selected_indexes)

    def move_sell_commodity_down(self):
        wp = self.get_selected_waypoint()
        if wp:
            selected_item = self.sell_commodities_list.selection()
            selected_indexes = []
            if selected_item:
                for item in reversed(selected_item):
                    index = self.sell_commodities_list.index(item)
                    if index < len(wp.sell_commodities) - 1:
                        selected_indexes.append(index + 1)
                        wp.sell_commodities.insert(index + 1, wp.sell_commodities.pop(index))
                self.update_commodity_list(wp.sell_commodities, self.sell_commodities_list)
                # Reselect previous selection
                select_treeview_items_by_idx(wp.sell_commodities, selected_indexes)

    def add_inara_route(self, text):
        lines = text.splitlines()

        from_waypoint = InternalWaypoint()
        to_waypoint = InternalWaypoint()

        from_buy = True
        from_sell = True

        for line in lines:
            if line.startswith("From"):
                parts = line.replace("From", "").split('|')
                if len(parts) >= 2:
                    station = remove_non_ascii(parts[0]).strip()
                    system = remove_non_ascii(parts[1]).strip()
                    from_waypoint.station_name.set(station)
                    from_waypoint.system_name.set(system)

            elif line.startswith("To"):
                parts = line.replace("To", "").split('|')
                if len(parts) >= 2:
                    station = remove_non_ascii(parts[0]).strip()
                    system = remove_non_ascii(parts[1]).strip()
                    to_waypoint.station_name.set(station)
                    to_waypoint.system_name.set(system)

            elif line.startswith("Buy") and not line.startswith("Buy price"):
                commodity = line.replace("Buy", "").strip()
                if from_buy:
                    from_waypoint.buy_commodities.append(ShoppingItem(commodity, 9999))
                else:
                    to_waypoint.buy_commodities.append(ShoppingItem(commodity, 9999))
                from_buy = False

            elif line.startswith("Sell") and not line.startswith("Sell price"):
                commodity = line.replace("Sell", "").strip()
                if from_sell:
                    from_waypoint.sell_commodities.append(ShoppingItem(commodity, 9999))
                else:
                    to_waypoint.sell_commodities.append(ShoppingItem(commodity, 9999))
                from_sell = False

        self.waypoints.waypoints.append(from_waypoint)
        self.waypoints.waypoints.append(to_waypoint)
        self.update_waypoints_list()
        messagebox.showinfo("Inara Route Added", "The trade route has been added to your waypoints.")

