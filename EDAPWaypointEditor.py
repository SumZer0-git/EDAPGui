import tkinter as tk
from tkinter import ttk, messagebox
import json
import threading
import os
import time
import csv
from EDAP_EDMesg_Interface import (
    create_edap_client, LoadWaypointFileAction,
    GalaxyMapTargetSystemByNameAction, GalaxyMapTargetStationByBookmarkAction,
    SystemMapTargetStationByBookmarkAction
)

class SearchableCombobox(ttk.Frame):
    def __init__(self, parent, options, on_select_callback):
        super().__init__(parent)
        self.root = self.winfo_toplevel()

        self.options = options
        self.on_select_callback = on_select_callback
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

ALL_COMMODITIES = [
    "ALL", "Agronomic Treatment", "Explosives", "Hydrogen Fuel", "Hydrogen Peroxide", "Liquid Oxygen", "Mineral Oil", "Nerve Agents", "Pesticides", "Rockforth Fertiliser", "Surface Stabilisers", "Synthetic Reagents", "Tritium", "Water",
    "Clothing", "Consumer Technology", "Domestic Appliances", "Evacuation Shelter", "Survival Equipment",
    "Algae", "Animal Meat", "Coffee", "Fish", "Food Cartridges", "Fruit and Vegetables", "Grain", "Synthetic Meat", "Tea",
    "Ceramic Composites", "CMM Composite", "Insulating Membrane", "Meta-Alloys", "Micro-Weave Cooling Hoses", "Neofabric Insulation", "Polymers", "Semiconductors", "Superconductors",
    "Beer", "Bootleg Liquor", "Liquor", "Narcotics", "Onionhead Gamma Strain", "Tobacco", "Wine",
    "Articulation Motors", "Atmospheric Processors", "Building Fabricators", "Crop Harvesters", "Emergency Power Cells", "Energy Grid Assembly", "Exhaust Manifold", "Geological Equipment", "Heatsink Interlink", "HN Shock Mount", "Magnetic Emitter Coil", "Marine Equipment", "Microbial Furnaces", "Mineral Extractors", "Modular Terminals", "Power Converter", "Power Generators", "Power Transfer Bus", "Radiation Baffle", "Reinforced Mounting Plate", "Skimmer Components", "Thermal Cooling Units", "Water Purifiers",
    "Advanced Medicines", "Agri-Medicines", "Basic Medicines", "Combat Stabilisers", "Performance Enhancers", "Progenitor Cells",
    "Aluminium", "Beryllium", "Bismuth", "Cobalt", "Copper", "Gallium", "Gold", "Hafnium 178", "Indium", "Lanthanum", "Lithium", "Osmium", "Palladium", "Platinum", "Platinum Alloy", "Praseodymium", "Samarium", "Silver", "Steel", "Tantalum", "Thallium", "Thorium", "Titanium", "Uranium",
    "Alexandrite", "Bauxite", "Benitoite", "Bertrandite", "Bromellite", "Coltan", "Cryolite", "Gallite", "Goslarite", "Grandidierite", "Indite", "Jadeite", "Lepidolite", "Lithium Hydroxide", "Low Temperature Diamonds", "Methane Clathrate", "Methanol Monohydrate Crystals", "Moissanite", "Monazite", "Musgravite", "Painite", "Pyrophyllite", "Rhodplumsite", "Rutile", "Serendibite", "Taaffeite", "Uraninite", "Void Opals",
    "AI Relics", "Ancient Artefact", "Ancient Key", "Anomaly Particles", "Antimatter Containment Unit", "Antique Jewellery", "Antiquities", "Assault Plans", "Black Box", "Commercial Samples", "Damaged Escape Pod", "Data Core", "Diplomatic Bag", "Earth Relics", "Encrypted Correspondence", "Encrypted Data Storage", "Experimental Chemicals", "Fossil Remnants", "Gene Bank", "Geological Samples", "Guardian Casket", "Guardian Orb", "Guardian Relic", "Guardian Tablet", "Guardian Totem", "Guardian Urn", "Hostage", "Large Survey Data Cache", "Military Intelligence", "Military Plans", "Mollusc Brain Tissue", "Mollusc Fluid", "Mollusc Membrane", "Mollusc Mycelium", "Mollusc Soft Tissue", "Mollusc Spores", "Mysterious Idol", "Occupied Escape Pod", "Personal Effects", "Pod Core Tissue", "Pod Dead Tissue", "Pod Mesoglea", "Pod Outer Tissue", "Pod Shell Tissue", "Pod Surface Tissue", "Pod Tissue", "Political Prisoner", "Precious Gems", "Prohibited Research Materials", "Prototype Tech", "Rare Artwork", "Rebel Transmissions", "SAP 8 Core Container", "Scientific Research", "Scientific Samples", "Small Survey Data Cache", "Space Pioneer Relics", "Tactical Data", "Technical Blueprints", "Thargoid Basilisk Tissue Sample", "Thargoid Biological Matter", "Thargoid Bio-Storage Capsule", "Thargoid Cyclops Tissue Sample", "Thargoid Glaive Tissue Sample", "Thargoid Heart", "Thargoid Hydra Tissue Sample", "Thargoid Link", "Thargoid Orthrus Tissue Sample", "Thargoid Probe", "Thargoid Resin", "Thargoid Sensor", "Thargoid Medusa Tissue Sample", "Thargoid Scout Tissue Sample", "Thargoid Technology Samples", "Time Capsule", "Titan Deep Tissue Sample", "Titan Maw Deep Tissue Sample", "Titan Maw Partial Tissue Sample", "Titan Maw Tissue Sample", "Titan Partial Tissue Sample", "Titan Tissue Sample", "Trade Data", "Trinkets of Hidden Fortune", "Unclassified Relic", "Unoccupied Escape Pod", "Unstable Data Core", "Wreckage Components",
    "Imperial Slaves", "Slaves",
    "Advanced Catalysers", "Animal Monitors", "Aquaponic Systems", "Auto Fabricators", "Bioreducing Lichen", "Computer Components", "H.E. Suits", "Hardware Diagnostic Sensor", "Ion Distributor", "Land Enrichment Systems", "Medical Diagnostic Equipment", "Micro Controllers", "Muon Imager", "Nanobreakers", "Resonating Separators", "Robotics", "Structural Regulators", "Telemetry Suite",
    "Conductive Fabrics", "Leather", "Military Grade Fabrics", "Natural Fabrics", "Synthetic Fabrics",
    "Biowaste", "Chemical Waste", "Scrap", "Toxic Waste",
    "Battle Weapons", "Landmines", "Non Lethal Weapons", "Personal Weapons", "Reactive Armour"
]
ALL_COMMODITIES.sort()

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

class InternaGlobalshoppinglist:
    def __init__(self):
        self.buy_commodities = []
        self.update_commodity_count = tk.BooleanVar()
        self.skip = tk.BooleanVar()
        self.completed = tk.BooleanVar()

class InternalWaypoints:
    def __init__(self):
        self.waypoints = []
        self.global_shopping_list = InternaGlobalshoppinglist()


class WaypointEditorTab:
    def __init__(self, parent, ed_waypoint):
        self.ed_waypoint = ed_waypoint
        self.waypoints = InternalWaypoints()
        self.frame = ttk.Frame(parent)
        self.file_watcher_thread = None
        self.watching_filepath = None
        self.last_modified_time = None
        self.mesg_client = create_edap_client(15570, 15571)

        self.root = self.frame.winfo_toplevel()

        # Create the main notebook
        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Create the tabs
        self.waypoints_tab = ttk.Frame(self.notebook)
        self.global_shopping_list_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.waypoints_tab, text="Waypoints")
        self.notebook.add(self.global_shopping_list_tab, text="Global Shopping List")

        # --- Waypoints Tab ---
        self.create_waypoints_tab()

        # --- Global Shopping List Tab ---
        self.create_global_shopping_list_tab()

    def create_waypoints_tab(self):
        # Main container for the waypoints tab
        waypoints_container = ttk.Frame(self.waypoints_tab)
        waypoints_container.pack(fill="both", expand=True, padx=5, pady=5)

        # File operations buttons
        file_ops_frame = ttk.Frame(waypoints_container)
        file_ops_frame.pack(fill="x", pady=5)
        ttk.Button(file_ops_frame, text="New", command=self.new_file).pack(side="left", padx=2)
        ttk.Button(file_ops_frame, text="Open", command=self.open_file).pack(side="left", padx=2)
        self.save_button = ttk.Button(file_ops_frame, text="Save", command=self.save_file)
        self.save_button.pack(side="left", padx=2)
        self.save_button.config(state="disabled")
        ttk.Button(file_ops_frame, text="Save As", command=self.save_as_file).pack(side="left", padx=2)
        ttk.Button(file_ops_frame, text="Import Spansh CSV", command=self.import_spansh_csv).pack(side="left", padx=2)
        ttk.Button(file_ops_frame, text="Import from Inara", command=self.open_inara_import_window).pack(side="left", padx=2)

        # Top frame for waypoints list and buttons
        top_frame = ttk.Frame(waypoints_container)
        top_frame.pack(fill="x", expand=False, pady=5)

        # Waypoints list (Treeview)
        columns = ("system_name", "station_name", "skip", "completed")
        self.waypoints_tree = ttk.Treeview(top_frame, columns=columns, show="headings")

        self.waypoints_tree.heading("system_name", text="System Name")
        self.waypoints_tree.heading("station_name", text="Station Name")
        self.waypoints_tree.heading("skip", text="Skip")
        self.waypoints_tree.heading("completed", text="Completed")

        self.waypoints_tree.column("system_name", width=200)
        self.waypoints_tree.column("station_name", width=200)
        self.waypoints_tree.column("skip", width=50, anchor=tk.CENTER)
        self.waypoints_tree.column("completed", width=70, anchor=tk.CENTER)

        self.waypoints_tree.pack(side="left", fill="both", expand=True)

        self.waypoints_tree.bind("<<TreeviewSelect>>", self.on_waypoint_select)
        self.waypoints_tree.bind("<Double-1>", self.on_cell_double_click)
        self.waypoints_tree.bind("<Button-1>", self.on_tree_click)

        # Waypoint buttons
        waypoint_buttons_frame = ttk.Frame(top_frame)
        waypoint_buttons_frame.pack(side="right", fill="y", padx=(5,0))

        ttk.Button(waypoint_buttons_frame, text="Up", command=self.move_waypoint_up).pack(padx=5, pady=2, fill="x")
        ttk.Button(waypoint_buttons_frame, text="Down", command=self.move_waypoint_down).pack(padx=5, pady=2, fill="x")
        ttk.Button(waypoint_buttons_frame, text="Add", command=self.add_waypoint).pack(padx=5, pady=2, fill="x")
        ttk.Button(waypoint_buttons_frame, text="Del", command=self.delete_waypoint).pack(padx=5, pady=2, fill="x")

        # Bottom frame for waypoint options and commodity lists
        bottom_frame = ttk.Frame(waypoints_container)
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
        self.system_bookmark_type_combo = ttk.Combobox(station_options_frame, values=["", "Favorite", "Body", "Station", "Settlement", "Navigation Panel"])
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

    def create_global_shopping_list_tab(self):
        frame = ttk.Frame(self.global_shopping_list_tab)
        frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.global_shopping_list_tree = self.create_commodity_list(frame, "global")

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

        columns = ("name", "quantity")
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        tree.heading("name", text="Name")
        tree.heading("quantity", text="Quantity")
        tree.column("name", width=150)
        tree.column("quantity", width=70, anchor=tk.E)
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
        elif list_type == "global":
            ttk.Button(buttons_frame, text="Up", command=self.move_global_commodity_up).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Down", command=self.move_global_commodity_down).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Add", command=self.add_global_commodity).pack(padx=5, pady=2, fill="x")
            ttk.Button(buttons_frame, text="Del", command=self.delete_global_commodity).pack(padx=5, pady=2, fill="x")

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
            self.load_waypoint_file(filepath)
            self.save_button.config(state="normal")

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
                for row in reader:
                    system_name = row.get("System Name")
                    if system_name:
                        # Use system name for both waypoint name and system name for simplicity
                        new_waypoint = InternalWaypoint(name=system_name, system_name=system_name)
                        self.waypoints.waypoints.append(new_waypoint)
            self.update_waypoints_list()
            messagebox.showinfo("Import Successful", f"Imported waypoints from {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import CSV file: {e}")

    def load_waypoint_file(self, filepath):
        try:
            if self.ed_waypoint.load_waypoint_file(filepath):
                self.populate_internal_waypoints()
                self.update_ui()
                self.start_file_watcher(filepath)
        except json.JSONDecodeError:
            messagebox.showerror("Error", f"Invalid JSON file: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load waypoint file: {e}")

    def save_waypoint_file(self, filepath):
        raw_waypoints = self.convert_to_raw_waypoints()
        self.ed_waypoint.write_waypoints(raw_waypoints, filepath)
        self.ed_waypoint.filename = filepath
        self.mesg_client.publish(LoadWaypointFileAction(filepath=filepath))

    def start_file_watcher(self, filepath):
        if self.file_watcher_thread and self.file_watcher_thread.is_alive():
            # Stop the previous watcher if it's running
            self.watching_filepath = None # This will stop the loop in the thread
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
                    self.frame.after(0, self.load_waypoint_file, self.watching_filepath)
            except FileNotFoundError:
                # The file might have been deleted
                self.watching_filepath = None

            time.sleep(1) # Poll every second

    def populate_internal_waypoints(self):
        self.waypoints = InternalWaypoints()
        raw_waypoints = self.ed_waypoint.waypoints

        for key, value in raw_waypoints.items():
            if key == "GlobalShoppingList":
                gsl = self.waypoints.global_shopping_list
                gsl.update_commodity_count.set(value.get('UpdateCommodityCount', False))
                gsl.skip.set(value.get('Skip', False))
                gsl.completed.set(value.get('Completed', False))
                gsl.buy_commodities = [ShoppingItem(k, v) for k, v in value.get('BuyCommodities', {}).items()]
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

        # Global Shopping List
        gsl = self.waypoints.global_shopping_list
        raw_gsl = {
            'BuyCommodities': {item.name.get(): item.quantity.get() for item in gsl.buy_commodities},
            'UpdateCommodityCount': gsl.update_commodity_count.get(),
            'Skip': gsl.skip.get(),
            'Completed': gsl.completed.get()
        }
        raw_waypoints['GlobalShoppingList'] = raw_gsl

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
                "✓" if wp.completed.get() else ""
            ))

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
            self.galaxy_bookmark_type_combo.config(textvariable=None)
            self.galaxy_bookmark_number_entry.config(textvariable=None)
            self.system_bookmark_type_combo.config(textvariable=None)
            self.system_bookmark_number_entry.config(textvariable=None)
            self.update_commodity_count_check.config(variable=None)
            self.fleet_carrier_transfer_check.config(variable=None)

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

        # We only want to edit the first two columns
        if column_index > 1:
            return

        item_id = self.waypoints_tree.identify_row(event.y)
        item_index = self.waypoints_tree.index(item_id)

        x, y, width, height = self.waypoints_tree.bbox(item_id, column)

        entry_var = tk.StringVar()
        entry = ttk.Entry(self.waypoints_tree, textvariable=entry_var, font=ttk.Style().lookup('TEntry', 'font'))
        entry.place(x=x, y=y, width=width, height=height, anchor='nw')

        current_value = self.waypoints_tree.item(item_id, "values")[column_index]
        entry_var.set(current_value)
        entry.focus_set()
        entry.select_range(0, 'end')
        entry.icursor('end')

        def save_edit(event):
            new_value = entry_var.get()
            wp = self.waypoints.waypoints[item_index]
            if column_index == 0:
                wp.system_name.set(new_value)
            elif column_index == 1:
                wp.station_name.set(new_value)

            self.update_waypoints_list()
            entry.destroy()

        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", save_edit)

    def on_commodity_cell_double_click(self, event, list_type):
        selected_waypoint = self.get_selected_waypoint()
        if not selected_waypoint and list_type != "global":
            return

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
            commodity_list = self.get_selected_waypoint().buy_commodities
        elif list_type == "sell":
            commodity_list = self.get_selected_waypoint().sell_commodities
        elif list_type == "global":
            commodity_list = self.waypoints.global_shopping_list.buy_commodities
        else:
            return # Should not happen

        x, y, width, height = treeview.bbox(item_id, column)

        if column_index == 0: # Name column
            def on_select_callback(selected_value):
                commodity_list[item_index].name.set(selected_value)
                self.update_commodity_list(commodity_list, treeview)
                entry.destroy()

            entry = SearchableCombobox(treeview, ALL_COMMODITIES, on_select_callback)
            entry.entry.config(font=ttk.Style().lookup('TEntry', 'font'))
            entry.place(x=x, y=y, width=width, height=height, anchor='nw')
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
            entry.entry.bind("<FocusOut>", save_edit)
            entry.entry.bind("<Escape>", cancel_edit)

        elif column_index == 1: # Quantity column
            entry_var = tk.StringVar()
            entry = ttk.Entry(treeview, textvariable=entry_var, font=ttk.Style().lookup('TEntry', 'font'))
            entry.place(x=x, y=y, width=width, height=height, anchor='nw')
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

    def update_commodity_list(self, commodity_list, treeview):
        for item in treeview.get_children():
            treeview.delete(item)

        for i, item in enumerate(commodity_list):
            treeview.insert('', 'end', values=(item.name.get(), item.quantity.get()))

    def add_waypoint(self):
        new_waypoint = InternalWaypoint(system_name="New System")
        self.waypoints.waypoints.append(new_waypoint)
        self.update_waypoints_list()

    def delete_waypoint(self):
        selected_item = self.waypoints_tree.selection()
        if selected_item:
            for item in selected_item:
                index = self.waypoints_tree.index(item)
                del self.waypoints.waypoints[index]
            self.update_waypoints_list()

    def move_waypoint_up(self):
        selected_item = self.waypoints_tree.selection()
        if selected_item:
            for item in selected_item:
                index = self.waypoints_tree.index(item)
                if index > 0:
                    self.waypoints.waypoints.insert(index - 1, self.waypoints.waypoints.pop(index))
            self.update_waypoints_list()

    def move_waypoint_down(self):
        selected_item = self.waypoints_tree.selection()
        if selected_item:
            for item in reversed(selected_item):
                index = self.waypoints_tree.index(item)
                if index < len(self.waypoints.waypoints) - 1:
                    self.waypoints.waypoints.insert(index + 1, self.waypoints.waypoints.pop(index))
            self.update_waypoints_list()

    def get_selected_waypoint(self):
        selected_item = self.waypoints_tree.selection()
        if selected_item:
            index = self.waypoints_tree.index(selected_item[0])
            return self.waypoints.waypoints[index]
        return None

    def add_buy_commodity(self):
        wp = self.get_selected_waypoint()
        if wp:
            wp.buy_commodities.append(ShoppingItem("New Commodity", 1))
            self.update_commodity_list(wp.buy_commodities, self.buy_commodities_list)

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
            if selected_item:
                for item in selected_item:
                    index = self.buy_commodities_list.index(item)
                    if index > 0:
                        wp.buy_commodities.insert(index - 1, wp.buy_commodities.pop(index))
                self.update_commodity_list(wp.buy_commodities, self.buy_commodities_list)

    def move_buy_commodity_down(self):
        wp = self.get_selected_waypoint()
        if wp:
            selected_item = self.buy_commodities_list.selection()
            if selected_item:
                for item in reversed(selected_item):
                    index = self.buy_commodities_list.index(item)
                    if index < len(wp.buy_commodities) - 1:
                        wp.buy_commodities.insert(index + 1, wp.buy_commodities.pop(index))
                self.update_commodity_list(wp.buy_commodities, self.buy_commodities_list)

    def add_sell_commodity(self):
        wp = self.get_selected_waypoint()
        if wp:
            wp.sell_commodities.append(ShoppingItem("New Commodity", 1))
            self.update_commodity_list(wp.sell_commodities, self.sell_commodities_list)

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
            if selected_item:
                for item in selected_item:
                    index = self.sell_commodities_list.index(item)
                    if index > 0:
                        wp.sell_commodities.insert(index - 1, wp.sell_commodities.pop(index))
                self.update_commodity_list(wp.sell_commodities, self.sell_commodities_list)

    def move_sell_commodity_down(self):
        wp = self.get_selected_waypoint()
        if wp:
            selected_item = self.sell_commodities_list.selection()
            if selected_item:
                for item in reversed(selected_item):
                    index = self.sell_commodities_list.index(item)
                    if index < len(wp.sell_commodities) - 1:
                        wp.sell_commodities.insert(index + 1, wp.sell_commodities.pop(index))
                self.update_commodity_list(wp.sell_commodities, self.sell_commodities_list)

    def add_global_commodity(self):
        self.waypoints.global_shopping_list.buy_commodities.append(ShoppingItem("New Commodity", 1))
        self.update_commodity_list(self.waypoints.global_shopping_list.buy_commodities, self.global_shopping_list_tree)

    def delete_global_commodity(self):
        selected_item = self.global_shopping_list_tree.selection()
        if selected_item:
            for item in selected_item:
                index = self.global_shopping_list_tree.index(item)
                del self.waypoints.global_shopping_list.buy_commodities[index]
            self.update_commodity_list(self.waypoints.global_shopping_list.buy_commodities, self.global_shopping_list_tree)

    def move_global_commodity_up(self):
        selected_item = self.global_shopping_list_tree.selection()
        if selected_item:
            for item in selected_item:
                index = self.global_shopping_list_tree.index(item)
                if index > 0:
                    self.waypoints.global_shopping_list.buy_commodities.insert(index - 1, self.waypoints.global_shopping_list.buy_commodities.pop(index))
            self.update_commodity_list(self.waypoints.global_shopping_list.buy_commodities, self.global_shopping_list_tree)

    def move_global_commodity_down(self):
        selected_item = self.global_shopping_list_tree.selection()
        if selected_item:
            for item in reversed(selected_item):
                index = self.global_shopping_list_tree.index(item)
                if index < len(self.waypoints.global_shopping_list.buy_commodities) - 1:
                    self.waypoints.global_shopping_list.buy_commodities.insert(index + 1, self.waypoints.global_shopping_list.buy_commodities.pop(index))
            self.update_commodity_list(self.waypoints.global_shopping_list.buy_commodities, self.global_shopping_list_tree)

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
                    from_waypoint.station_name.set(parts[0].strip())
                    from_waypoint.system_name.set(parts[1].strip())
            elif line.startswith("To"):
                parts = line.replace("To", "").split('|')
                if len(parts) >= 2:
                    to_waypoint.station_name.set(parts[0].strip())
                    to_waypoint.system_name.set(parts[1].strip())
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
