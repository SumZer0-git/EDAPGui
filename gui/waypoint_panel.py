import tkinter as tk
from tkinter import (
    BooleanVar, Button, Entry, Frame, IntVar, Label, LabelFrame, 
    StringVar, LEFT, Toplevel, END
)
from tkinter import Checkbutton, messagebox
from tkinter import ttk
from pathlib import Path


class WaypointPanel:
    """Panel for single waypoint assist and TCE integration"""
    
    def __init__(self, parent_frame, ed_ap, entry_callback, check_callback):
        self.parent = parent_frame
        self.ed_ap = ed_ap
        self.entry_callback = entry_callback
        self.check_callback = check_callback
        
        # String variables for waypoint fields
        self.single_waypoint_system = StringVar()
        self.single_waypoint_station = StringVar()
        self.TCE_Destination_Filepath = StringVar()
        
        # Checkbox variable
        self.checkboxvar = {}
        
        self._create_waypoint_gui()
    
    def _create_waypoint_gui(self):
        """Create the waypoint panel GUI"""
        # Single waypoint assist block
        blk_single_waypoint_asst = LabelFrame(self.parent, text="SINGLE WAYPOINT ASSIST")
        blk_single_waypoint_asst.grid(row=0, column=0, padx=10, pady=5, columnspan=2, sticky="nsew")
        blk_single_waypoint_asst.columnconfigure(0, weight=1, minsize=10, uniform="group1")
        blk_single_waypoint_asst.columnconfigure(1, weight=3, minsize=10, uniform="group1")

        # System field
        lbl_system = tk.Label(blk_single_waypoint_asst, text='System:')
        lbl_system.grid(row=0, column=0, padx=2, pady=2, columnspan=1, sticky="news")
        txt_system = Entry(blk_single_waypoint_asst, textvariable=self.single_waypoint_system)
        txt_system.grid(row=0, column=1, padx=2, pady=2, columnspan=1, sticky="news")
        
        # Station field
        lbl_station = tk.Label(blk_single_waypoint_asst, text='Station:')
        lbl_station.grid(row=1, column=0, padx=2, pady=2, columnspan=1, sticky="news")
        txt_station = Entry(blk_single_waypoint_asst, textvariable=self.single_waypoint_station)
        txt_station.grid(row=1, column=1, padx=2, pady=2, columnspan=1, sticky="news")
        
        # Single waypoint assist checkbox
        self.checkboxvar['Single Waypoint Assist'] = BooleanVar()
        cb_single_waypoint = Checkbutton(blk_single_waypoint_asst, text='Single Waypoint Assist', 
                                        onvalue=1, offvalue=0, anchor='w', pady=3, justify=LEFT, 
                                        variable=self.checkboxvar['Single Waypoint Assist'], 
                                        command=lambda: self.check_callback('Single Waypoint Assist'))
        cb_single_waypoint.grid(row=2, column=0, padx=2, pady=2, columnspan=2, sticky="news")

        # TCE (Trade Computer Extension) section
        lbl_tce = tk.Label(blk_single_waypoint_asst, text='Trade Computer Extension (TCE)', 
                          fg="blue", cursor="hand2")
        lbl_tce.bind("<Button-1>", lambda e: self._hyperlink_callback("https://forums.frontier.co.uk/threads/trade-computer-extension-mk-ii.223056/"))
        lbl_tce.grid(row=3, column=0, padx=2, pady=2, columnspan=2, sticky="news")
        
        lbl_tce_dest = tk.Label(blk_single_waypoint_asst, text='TCE Dest json:')
        lbl_tce_dest.grid(row=4, column=0, padx=2, pady=2, columnspan=1, sticky="news")
        txt_tce_dest = Entry(blk_single_waypoint_asst, textvariable=self.TCE_Destination_Filepath)
        txt_tce_dest.bind('<FocusOut>', self.entry_callback)
        txt_tce_dest.grid(row=4, column=1, padx=2, pady=2, columnspan=1, sticky="news")

        btn_load_tce = Button(blk_single_waypoint_asst, text='Load TCE Destination', 
                             command=self._load_tce_dest)
        btn_load_tce.grid(row=5, column=0, padx=2, pady=2, columnspan=2, sticky="news")
        
        # Waypoint Editor section
        self._create_waypoint_editor()
    
    def _hyperlink_callback(self, url):
        """Open hyperlink in browser"""
        import webbrowser
        webbrowser.open_new(url)
    
    def _load_tce_dest(self):
        """Load TCE destination file"""
        import os
        from file_utils import read_json_file
        
        filename = self.ed_ap.config['TCEDestinationFilepath']
        if os.path.exists(filename):
            f_details = read_json_file(filename)
            self.single_waypoint_system.set(f_details['StarSystem'])
            self.single_waypoint_station.set(f_details['Station'])
    
    def initialize_values(self):
        """Initialize field values from configuration"""
        self.TCE_Destination_Filepath.set(self.ed_ap.config['TCEDestinationFilepath'])
    
    def get_single_waypoint_system(self):
        """Get single waypoint system name"""
        return self.single_waypoint_system.get()
    
    def get_single_waypoint_station(self):
        """Get single waypoint station name"""
        return self.single_waypoint_station.get()
    
    def get_checkbox_state(self, field):
        """Get checkbox state"""
        if field in self.checkboxvar:
            return self.checkboxvar[field].get()
        return 0
    
    def set_checkbox_state(self, field, value):
        """Set checkbox state"""
        if field in self.checkboxvar:
            self.checkboxvar[field].set(value)
    
    def _create_waypoint_editor(self):
        """Create waypoint editor section"""
        # Waypoint Editor block
        blk_waypoint_editor = LabelFrame(self.parent, text="WAYPOINT EDITOR")
        blk_waypoint_editor.grid(row=1, column=0, padx=10, pady=5, columnspan=2, sticky="nsew")
        blk_waypoint_editor.columnconfigure(0, weight=1)
        blk_waypoint_editor.rowconfigure(1, weight=1)
        
        # Waypoint file controls
        file_controls = Frame(blk_waypoint_editor)
        file_controls.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        file_controls.columnconfigure(0, weight=1)
        
        self.wp_filelabel = StringVar()
        self.wp_filelabel.set("<no list loaded>")
        btn_wp_file = Button(file_controls, textvariable=self.wp_filelabel, command=self._open_wp_file)
        btn_wp_file.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        
        btn_wp_reset = Button(file_controls, text='Reset Waypoint List', command=self._reset_wp_list)
        btn_wp_reset.grid(row=0, column=1, padx=2, pady=2)
        
        # Waypoint list display
        list_frame = Frame(blk_waypoint_editor)
        list_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Create treeview for waypoint list
        columns = ('System', 'Station', 'Sell', 'Buy', 'FC Transfer', 'Skip')
        self.wp_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=10)
        
        # Configure columns
        self.wp_tree.column('#0', width=50, minwidth=50)  # Waypoint number
        self.wp_tree.heading('#0', text='#')
        
        for col in columns:
            self.wp_tree.column(col, width=100, minwidth=80)
            self.wp_tree.heading(col, text=col)
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.wp_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient="horizontal", command=self.wp_tree.xview)
        self.wp_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid treeview and scrollbars
        self.wp_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Configure tags for changed waypoints
        self.wp_tree.tag_configure('changed', background='lightyellow')
        
        # Editor buttons
        editor_buttons = Frame(blk_waypoint_editor)
        editor_buttons.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        
        btn_wp_new = Button(editor_buttons, text='New', command=self._wp_editor_new)
        btn_wp_new.grid(row=0, column=0, padx=2, pady=2)
        
        btn_wp_edit = Button(editor_buttons, text='Edit', command=self._wp_editor_edit)
        btn_wp_edit.grid(row=0, column=1, padx=2, pady=2)
        
        btn_wp_delete = Button(editor_buttons, text='Delete', command=self._wp_editor_delete)
        btn_wp_delete.grid(row=0, column=2, padx=2, pady=2)
        
        self.btn_wp_save = Button(editor_buttons, text='Save File', command=self._wp_editor_save)
        self.btn_wp_save.grid(row=0, column=3, padx=2, pady=2)
        
        btn_wp_refresh = Button(editor_buttons, text='Refresh', command=self._wp_editor_refresh)
        btn_wp_refresh.grid(row=0, column=4, padx=2, pady=2)
        
        # Track changed waypoints
        self.changed_waypoints = set()
    
    def _open_wp_file(self):
        """Open waypoint file"""
        from tkinter import filedialog as fd
        
        filetypes = (
            ('json files', '*.json'),
            ('All files', '*.*')
        )
        filename = fd.askopenfilename(
            title='Open waypoint file',
            initialdir='./waypoints/',
            filetypes=filetypes)
        
        if filename:
            res = self.ed_ap.waypoint.load_waypoint_file(filename)
            if res:
                self.wp_filelabel.set("loaded: " + Path(filename).name)
                self._wp_editor_refresh()
            else:
                self.wp_filelabel.set("<no list loaded>")
    
    def _reset_wp_list(self):
        """Reset waypoint list"""
        if hasattr(self.ed_ap, 'waypoint'):
            if not self.ed_ap.waypoint_assist_enabled:
                self.ed_ap.waypoint.reset_waypoint_list()
                self._wp_editor_refresh()
            else:
                messagebox.showerror("Waypoint List Error", 
                                   "Waypoint Assist must be disabled before you can reset the list.")
    
    def _wp_editor_refresh(self):
        """Refresh the waypoint list display"""
        # Clear existing items
        for item in self.wp_tree.get_children():
            self.wp_tree.delete(item)
        
        # Load current waypoint data
        try:
            if hasattr(self.ed_ap, 'waypoint') and hasattr(self.ed_ap.waypoint, 'waypoints'):
                waypoints = self.ed_ap.waypoint.waypoints
                
                if isinstance(waypoints, dict):
                    # Get all numeric keys and sort them
                    waypoint_keys = [k for k in waypoints.keys() if k.isdigit()]
                    waypoint_keys.sort(key=int)
                    
                    for key in waypoint_keys:
                        waypoint = waypoints[key]
                        if isinstance(waypoint, dict):
                            wp_num = key
                            system = waypoint.get('SystemName', '')
                            station = waypoint.get('StationName', '')
                            
                            # Summarize commodities
                            sell_items = waypoint.get('SellCommodities', {})
                            buy_items = waypoint.get('BuyCommodities', {})
                            
                            if sell_items:
                                sell_list = [f"{k}: {v}" for k, v in list(sell_items.items())[:2]]
                                sell_text = " | ".join(sell_list)
                                if len(sell_items) > 2:
                                    sell_text += f" | (+{len(sell_items)-2})"
                            else:
                                sell_text = ""
                                
                            if buy_items:
                                buy_list = [f"{k}: {v}" for k, v in list(buy_items.items())[:2]]
                                buy_text = " | ".join(buy_list)
                                if len(buy_items) > 2:
                                    buy_text += f" | (+{len(buy_items)-2})"
                            else:
                                buy_text = ""
                            
                            fc_transfer = "Yes" if waypoint.get('FleetCarrierTransfer', False) else "No"
                            skip = "Yes" if waypoint.get('Skip', False) else "No"
                            
                            # Insert into tree with change highlighting
                            tags = ('changed',) if key in self.changed_waypoints else ()
                            self.wp_tree.insert('', 'end', text=wp_num, values=(
                                system, station, sell_text, buy_text, fc_transfer, skip
                            ), tags=tags)
        except Exception as e:
            from EDlogger import logger
            logger.error(f"Error refreshing waypoint editor: {e}")
    
    def _wp_editor_new(self):
        """Create a new waypoint"""
        self._wp_editor_dialog(None)
    
    def _wp_editor_edit(self):
        """Edit selected waypoint"""
        selection = self.wp_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a waypoint to edit.")
            return
        
        item = selection[0]
        wp_key = self.wp_tree.item(item, 'text')
        self._wp_editor_dialog(wp_key)
    
    def _wp_editor_delete(self):
        """Delete selected waypoint"""
        selection = self.wp_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a waypoint to delete.")
            return
        
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this waypoint?"):
            item = selection[0]
            wp_key = self.wp_tree.item(item, 'text')
            
            if hasattr(self.ed_ap, 'waypoint') and hasattr(self.ed_ap.waypoint, 'waypoints'):
                if wp_key in self.ed_ap.waypoint.waypoints:
                    del self.ed_ap.waypoint.waypoints[wp_key]
                    self.changed_waypoints.add(wp_key)
                    self._update_wp_save_button()
                    self._wp_editor_refresh()
    
    def _wp_editor_save(self):
        """Save waypoint file"""
        if hasattr(self.ed_ap, 'waypoint'):
            try:
                self.ed_ap.waypoint.write_waypoints(data=None)
                self.changed_waypoints.clear()
                self._update_wp_save_button()
                self._wp_editor_refresh()
                messagebox.showinfo("Success", "Waypoint file saved successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save waypoint file: {e}")
    
    def _update_wp_save_button(self):
        """Update waypoint save button color based on changes"""
        if self.changed_waypoints:
            self.btn_wp_save.config(bg='orange', text='Save File *')
        else:
            self.btn_wp_save.config(bg='SystemButtonFace', text='Save File')
    
    def _wp_editor_dialog(self, wp_key=None):
        """Open waypoint edit dialog"""
        dialog = Toplevel(self.parent)
        dialog.title("Edit Waypoint" if wp_key is not None else "New Waypoint")
        dialog.geometry("500x400")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Get existing waypoint data
        waypoint_data = {}
        if wp_key is not None and hasattr(self.ed_ap, 'waypoint') and hasattr(self.ed_ap.waypoint, 'waypoints'):
            if wp_key in self.ed_ap.waypoint.waypoints:
                waypoint_data = self.ed_ap.waypoint.waypoints[wp_key].copy()
        
        # Create form fields
        fields = {}
        
        # Basic info frame
        basic_frame = LabelFrame(dialog, text="Basic Information")
        basic_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        dialog.columnconfigure(0, weight=1)
        basic_frame.columnconfigure(1, weight=1)
        
        # System name
        Label(basic_frame, text="System Name:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        fields['SystemName'] = Entry(basic_frame)
        fields['SystemName'].grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        fields['SystemName'].insert(0, waypoint_data.get('SystemName', ''))
        
        # Station name
        Label(basic_frame, text="Station Name:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        fields['StationName'] = Entry(basic_frame)
        fields['StationName'].grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        fields['StationName'].insert(0, waypoint_data.get('StationName', ''))
        
        # Fleet Carrier Transfer checkbox
        fields['FleetCarrierTransfer'] = BooleanVar()
        fields['FleetCarrierTransfer'].set(waypoint_data.get('FleetCarrierTransfer', False))
        cb_fc = Checkbutton(basic_frame, text="Fleet Carrier Transfer", variable=fields['FleetCarrierTransfer'])
        cb_fc.grid(row=2, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        
        # Skip checkbox
        fields['Skip'] = BooleanVar()
        fields['Skip'].set(waypoint_data.get('Skip', False))
        cb_skip = Checkbutton(basic_frame, text="Skip this waypoint", variable=fields['Skip'])
        cb_skip.grid(row=3, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        
        # Commodities frame
        commodities_frame = LabelFrame(dialog, text="Commodities")
        commodities_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        dialog.rowconfigure(1, weight=1)
        commodities_frame.columnconfigure(1, weight=1)
        
        # Sell commodities
        Label(commodities_frame, text="Sell:").grid(row=0, column=0, padx=5, pady=2, sticky="nw")
        fields['SellCommodities'] = tk.Text(commodities_frame, height=4, width=40)
        fields['SellCommodities'].grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        
        # Format sell commodities for display
        sell_text = ""
        sell_commodities = waypoint_data.get('SellCommodities', {})
        for commodity, quantity in sell_commodities.items():
            sell_text += f"{commodity}: {quantity}\n"
        fields['SellCommodities'].insert('1.0', sell_text)
        
        # Buy commodities
        Label(commodities_frame, text="Buy:").grid(row=1, column=0, padx=5, pady=2, sticky="nw")
        fields['BuyCommodities'] = tk.Text(commodities_frame, height=4, width=40)
        fields['BuyCommodities'].grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        
        # Format buy commodities for display
        buy_text = ""
        buy_commodities = waypoint_data.get('BuyCommodities', {})
        for commodity, quantity in buy_commodities.items():
            buy_text += f"{commodity}: {quantity}\n"
        fields['BuyCommodities'].insert('1.0', buy_text)
        
        # Buttons frame
        btn_frame = Frame(dialog)
        btn_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        
        def save_waypoint():
            try:
                # Parse commodities
                def parse_commodities(text_widget):
                    commodities = {}
                    text = text_widget.get('1.0', 'end-1c').strip()
                    
                    for line in text.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                            
                        for item in line.split(','):
                            item = item.strip()
                            if ':' in item:
                                commodity, quantity = item.split(':', 1)
                                commodity = commodity.strip()
                                quantity = quantity.strip()
                                if commodity and quantity:
                                    try:
                                        commodities[commodity] = int(quantity)
                                    except ValueError:
                                        commodities[commodity] = quantity
                    return commodities
                
                # Build waypoint data
                new_waypoint = {
                    'SystemName': fields['SystemName'].get(),
                    'StationName': fields['StationName'].get(),
                    'SellCommodities': parse_commodities(fields['SellCommodities']),
                    'BuyCommodities': parse_commodities(fields['BuyCommodities']),
                    'FleetCarrierTransfer': fields['FleetCarrierTransfer'].get(),
                    'Skip': fields['Skip'].get()
                }
                
                # Save to waypoint list
                if not hasattr(self.ed_ap, 'waypoint'):
                    from EDWayPoint import EDWayPoint
                    self.ed_ap.waypoint = EDWayPoint(self.ed_ap)
                
                if not hasattr(self.ed_ap.waypoint, 'waypoints'):
                    self.ed_ap.waypoint.waypoints = {}
                
                if wp_key is not None:
                    # Update existing
                    self.ed_ap.waypoint.waypoints[wp_key] = new_waypoint
                    self.changed_waypoints.add(wp_key)
                else:
                    # Add new - find next available key
                    if isinstance(self.ed_ap.waypoint.waypoints, dict):
                        numeric_keys = [int(k) for k in self.ed_ap.waypoint.waypoints.keys() if k.isdigit()]
                        next_key = str(max(numeric_keys) + 1) if numeric_keys else "1"
                        self.ed_ap.waypoint.waypoints[next_key] = new_waypoint
                        self.changed_waypoints.add(next_key)
                
                self._update_wp_save_button()
                self._wp_editor_refresh()
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save waypoint: {e}")
        
        def cancel():
            dialog.destroy()
        
        Button(btn_frame, text="Save", command=save_waypoint).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        Button(btn_frame, text="Cancel", command=cancel).grid(row=0, column=1, padx=5, pady=5, sticky="ew")