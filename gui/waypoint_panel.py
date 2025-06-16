import tkinter as tk
from tkinter import (
    BooleanVar, Button, Entry, Frame, IntVar, Label, LabelFrame, 
    StringVar, LEFT, Toplevel, END, Scrollbar
)
from tkinter import Checkbutton, messagebox
from tkinter import ttk
from pathlib import Path
from datetime import datetime


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
        
        # Re-order sections: Global Shopping List, Waypoint Editor, then Single Waypoint
        # Configure grid weights for the parent to allow expansion
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=0)  # Global shopping list fixed size
        self.parent.rowconfigure(1, weight=1)  # Waypoint editor gets priority
        self.parent.rowconfigure(2, weight=0)  # Single waypoint assist fixed size
        
        # Move Single Waypoint Assist to bottom (change its row to 2)
        blk_single_waypoint_asst.grid_forget()
        blk_single_waypoint_asst.grid(row=2, column=0, padx=10, pady=5, columnspan=2, sticky="nsew")
        
        # Create Waypoint Editor at the top
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
        
        # Load waypoint data into editor
        self._wp_editor_refresh()
        
        # Initialize global shopping state
        self._refresh_global_shopping_summary()
        self._initialize_global_shopping_state()
    
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
        # Global Shopping List Panel (separate from waypoints)
        self._create_global_shopping_panel()
        
        # Waypoint Editor block
        blk_waypoint_editor = LabelFrame(self.parent, text="WAYPOINT EDITOR")
        blk_waypoint_editor.grid(row=1, column=0, padx=10, pady=5, columnspan=2, sticky="nsew")
        blk_waypoint_editor.columnconfigure(0, weight=1)
        blk_waypoint_editor.rowconfigure(1, weight=1)  # Make the list area expandable
        
        # Waypoint editor toolbar
        toolbar_frame = Frame(blk_waypoint_editor)
        toolbar_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        toolbar_frame.columnconfigure(2, weight=1)  # Spacer column
        
        btn_wp_new = Button(toolbar_frame, text='New', command=self._wp_editor_new)
        btn_wp_new.grid(row=0, column=0, padx=2, pady=2)
        
        btn_wp_edit = Button(toolbar_frame, text='Edit', command=self._wp_editor_edit)
        btn_wp_edit.grid(row=0, column=1, padx=2, pady=2)
        
        btn_wp_delete = Button(toolbar_frame, text='Delete', command=self._wp_editor_delete)
        btn_wp_delete.grid(row=0, column=3, padx=2, pady=2)
        
        btn_wp_load = Button(toolbar_frame, text='Load File', command=self._open_wp_file)
        btn_wp_load.grid(row=0, column=4, padx=2, pady=2)
        
        self.btn_wp_save = Button(toolbar_frame, text='Save File', command=self._wp_editor_save)
        self.btn_wp_save.grid(row=0, column=5, padx=2, pady=2)
        
        # Waypoint list with scrollbar
        list_frame = Frame(blk_waypoint_editor)
        list_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Create Treeview for waypoint list
        self.wp_tree = ttk.Treeview(list_frame, columns=('system', 'station', 'sell', 'buy', 'fc_transfer', 'skip'), show='tree headings', height=10)
        self.wp_tree.grid(row=0, column=0, sticky="nsew")
        
        # Configure columns
        self.wp_tree.heading('#0', text='#')
        self.wp_tree.heading('system', text='System')
        self.wp_tree.heading('station', text='Station')
        self.wp_tree.heading('sell', text='Sell')
        self.wp_tree.heading('buy', text='Buy')
        self.wp_tree.heading('fc_transfer', text='FC Transfer')
        self.wp_tree.heading('skip', text='Skip')
        
        self.wp_tree.column('#0', width=30, minwidth=30)
        self.wp_tree.column('system', width=120, minwidth=80)
        self.wp_tree.column('station', width=150, minwidth=100)
        self.wp_tree.column('sell', width=120, minwidth=80)  # Wider for multi-line commodities
        self.wp_tree.column('buy', width=120, minwidth=80)   # Wider for multi-line commodities
        self.wp_tree.column('fc_transfer', width=80, minwidth=60)
        self.wp_tree.column('skip', width=50, minwidth=40)
        
        # Configure row height and styling
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)  # Standard row height
        
        # Configure tags for changed waypoints
        self.wp_tree.tag_configure('changed', background='lightgreen')
        
        # Add scrollbar for waypoint list
        wp_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.wp_tree.yview)
        wp_scrollbar.grid(row=0, column=1, sticky="ns")
        self.wp_tree.configure(yscrollcommand=wp_scrollbar.set)
        
        # Bind double-click to edit
        self.wp_tree.bind('<Double-1>', lambda e: self._wp_editor_edit())
        
        # Track changed waypoints
        self.changed_waypoints = set()
        
        # Initialize waypoint file label (for compatibility with other functions)
        self.wp_filelabel = StringVar()
        self.wp_filelabel.set("<no waypoint list loaded>")
    
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
                self.wp_filelabel.set("<no waypoint list loaded>")
    
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
        
        # Track which waypoints have unsaved changes
        if not hasattr(self, 'changed_waypoints'):
            self.changed_waypoints = set()
        
        # Load current waypoint data
        try:
            if hasattr(self.ed_ap, 'waypoint') and hasattr(self.ed_ap.waypoint, 'waypoints'):
                waypoints = self.ed_ap.waypoint.waypoints
                
                # Debug: Check what type of data we have
                from EDlogger import logger
                logger.debug(f"Waypoints type: {type(waypoints)}")
                
                # Handle dictionary format (keys: 'GlobalShoppingList', '1', '2', '3', etc.)
                if isinstance(waypoints, dict):
                    # Get all numeric keys and sort them (exclude GlobalShoppingList)
                    waypoint_keys = [k for k in waypoints.keys() if k.isdigit()]
                    waypoint_keys.sort(key=int)
                    
                    logger.debug(f"Found waypoint keys: {waypoint_keys}")
                    
                    # Refresh global shopping summary if it exists
                    if hasattr(self, '_refresh_global_shopping_summary'):
                        self._refresh_global_shopping_summary()
                    
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
        commodities_frame.columnconfigure(2, weight=0)  # Help text column
        
        # Sell commodities
        Label(commodities_frame, text="Sell:").grid(row=0, column=0, padx=5, pady=2, sticky="nw")
        fields['SellCommodities'] = tk.Text(commodities_frame, height=4, width=40)
        fields['SellCommodities'].grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        
        # Format sell commodities for display (with cleanup for malformed data)
        sell_text = ""
        sell_commodities = waypoint_data.get('SellCommodities', {})
        
        # Clean up malformed data where commodity names got merged with quantities
        cleaned_sell = {}
        for commodity, quantity in sell_commodities.items():
            if isinstance(quantity, str) and ',' in quantity:
                # This looks like malformed data "Cobalt": "5, Gold: 10"
                # Parse it properly
                temp_text = f"{commodity}: {quantity}"
                for item in temp_text.split(','):
                    item = item.strip()
                    if ':' in item:
                        c, q = item.split(':', 1)
                        c, q = c.strip(), q.strip()
                        if c and q:
                            try:
                                cleaned_sell[c] = int(q)
                            except ValueError:
                                cleaned_sell[c] = q
            else:
                cleaned_sell[commodity] = quantity
        
        for commodity, quantity in cleaned_sell.items():
            sell_text += f"{commodity}: {quantity}\n"
        fields['SellCommodities'].insert('1.0', sell_text)
        
        # Add help text for sell commodities
        Label(commodities_frame, text="Format: CommodityName: Quantity\nExample: Cobalt: 5, Gold: 10\nOr one per line", 
              font=('TkDefaultFont', 8), fg='gray').grid(row=0, column=2, padx=5, pady=2, sticky="nw")
        
        # Buy commodities
        Label(commodities_frame, text="Buy:").grid(row=1, column=0, padx=5, pady=2, sticky="nw")
        fields['BuyCommodities'] = tk.Text(commodities_frame, height=4, width=40)
        fields['BuyCommodities'].grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        
        # Format buy commodities for display (with cleanup for malformed data)
        buy_text = ""
        buy_commodities = waypoint_data.get('BuyCommodities', {})
        
        # Clean up malformed data where commodity names got merged with quantities
        cleaned_buy = {}
        for commodity, quantity in buy_commodities.items():
            if isinstance(quantity, str) and ',' in quantity:
                # This looks like malformed data "Cobalt": "5, Gold: 10"
                # Parse it properly
                temp_text = f"{commodity}: {quantity}"
                for item in temp_text.split(','):
                    item = item.strip()
                    if ':' in item:
                        c, q = item.split(':', 1)
                        c, q = c.strip(), q.strip()
                        if c and q:
                            try:
                                cleaned_buy[c] = int(q)
                            except ValueError:
                                cleaned_buy[c] = q
            else:
                cleaned_buy[commodity] = quantity
        
        for commodity, quantity in cleaned_buy.items():
            buy_text += f"{commodity}: {quantity}\n"
        fields['BuyCommodities'].insert('1.0', buy_text)
        
        # Add help text for buy commodities
        Label(commodities_frame, text="Format: CommodityName: Quantity\nExample: Bertrandite: 100, Silver: 50\nOr one per line", 
              font=('TkDefaultFont', 8), fg='gray').grid(row=1, column=2, padx=5, pady=2, sticky="nw")
        
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
                
                # Build waypoint data with only essential fields
                new_waypoint = {
                    'SystemName': fields['SystemName'].get(),
                    'StationName': fields['StationName'].get(),
                    'SellCommodities': parse_commodities(fields['SellCommodities']),
                    'BuyCommodities': parse_commodities(fields['BuyCommodities']),
                    'FleetCarrierTransfer': fields['FleetCarrierTransfer'].get(),
                    'Skip': fields['Skip'].get()
                }
                
                # Only add optional fields if they already existed (preserving existing data)
                if 'GalaxyBookmarkType' in waypoint_data:
                    new_waypoint['GalaxyBookmarkType'] = waypoint_data['GalaxyBookmarkType']
                if 'GalaxyBookmarkNumber' in waypoint_data:
                    new_waypoint['GalaxyBookmarkNumber'] = waypoint_data['GalaxyBookmarkNumber']
                if 'SystemBookmarkType' in waypoint_data:
                    new_waypoint['SystemBookmarkType'] = waypoint_data['SystemBookmarkType']
                if 'SystemBookmarkNumber' in waypoint_data:
                    new_waypoint['SystemBookmarkNumber'] = waypoint_data['SystemBookmarkNumber']
                if 'Comment' in waypoint_data:
                    new_waypoint['Comment'] = waypoint_data['Comment']
                if 'UpdateCommodityCount' in waypoint_data:
                    new_waypoint['UpdateCommodityCount'] = waypoint_data['UpdateCommodityCount']
                if 'Completed' in waypoint_data:
                    new_waypoint['Completed'] = waypoint_data['Completed']
                
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
    
    def _create_global_shopping_panel(self):
        """Create dedicated panel for global shopping list"""
        # Global Shopping List Panel
        blk_global_shopping = LabelFrame(self.parent, text="GLOBAL SHOPPING LIST")
        blk_global_shopping.grid(row=0, column=0, padx=10, pady=5, columnspan=2, sticky="ew")
        blk_global_shopping.columnconfigure(1, weight=1)
        
        # Control frame (left side)
        control_frame = Frame(blk_global_shopping)
        control_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
        
        # Enable/disable toggle
        self.global_shopping_enabled = BooleanVar()
        cb_enable = Checkbutton(control_frame, text="Enable Global Shopping", 
                               variable=self.global_shopping_enabled,
                               command=self._on_global_shopping_toggle)
        cb_enable.grid(row=0, column=0, columnspan=3, sticky="w", pady=2)
        
        # Main action buttons in a row
        btn_edit_global = Button(control_frame, text="Edit", 
                                command=self._edit_global_shopping)
        btn_edit_global.grid(row=1, column=0, sticky="ew", padx=(0,2), pady=2)
        
        btn_save_template = Button(control_frame, text="Save Template", 
                                  command=self._save_gsl_template)
        btn_save_template.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        
        btn_load_template = Button(control_frame, text="Load Template", 
                                  command=self._load_gsl_template)
        btn_load_template.grid(row=1, column=2, sticky="ew", padx=(2,0), pady=2)
        
        # Summary frame (right side)
        summary_frame = Frame(blk_global_shopping)
        summary_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Global shopping summary
        self.global_summary_text = StringVar()
        lbl_summary = Label(summary_frame, textvariable=self.global_summary_text, 
                           anchor="w", justify=LEFT, wraplength=400)
        lbl_summary.grid(row=0, column=0, sticky="ew")
        
        # Initialize summary
        self._refresh_global_shopping_summary()
    
    def _initialize_global_shopping_state(self):
        """Initialize global shopping enabled state from waypoint data"""
        try:
            if (hasattr(self.ed_ap, 'waypoint') and 
                hasattr(self.ed_ap.waypoint, 'waypoints') and
                'GlobalShoppingList' in self.ed_ap.waypoint.waypoints):
                
                gsl_data = self.ed_ap.waypoint.waypoints['GlobalShoppingList']
                # GSL is enabled if Skip is False
                enabled = not gsl_data.get('Skip', True)
                self.global_shopping_enabled.set(enabled)
            else:
                # No GSL data, disable
                self.global_shopping_enabled.set(False)
        except Exception as e:
            from EDlogger import logger
            logger.warning(f"Failed to initialize global shopping state: {e}")
            self.global_shopping_enabled.set(False)
    
    def _on_global_shopping_toggle(self):
        """Handle global shopping enable/disable"""
        # Update the GlobalShoppingList Skip field
        if hasattr(self.ed_ap, 'waypoint') and hasattr(self.ed_ap.waypoint, 'waypoints'):
            if 'GlobalShoppingList' in self.ed_ap.waypoint.waypoints:
                # Set Skip to opposite of enabled (Skip=True means disabled)
                self.ed_ap.waypoint.waypoints['GlobalShoppingList']['Skip'] = not self.global_shopping_enabled.get()
                self.changed_waypoints.add('GlobalShoppingList')
                self._update_wp_save_button()
                self._refresh_global_shopping_summary()
    
    def _edit_global_shopping(self):
        """Open dialog to edit global shopping list"""
        self._wp_editor_dialog_global()
    
    def _refresh_global_shopping_summary(self):
        """Update the global shopping summary display"""
        try:
            if hasattr(self.ed_ap, 'waypoint') and hasattr(self.ed_ap.waypoint, 'waypoints'):
                global_data = self.ed_ap.waypoint.waypoints.get('GlobalShoppingList', {})
                
                # Update enabled state
                self.global_shopping_enabled.set(not global_data.get('Skip', True))
                
                # Build summary text
                buy_commodities = global_data.get('BuyCommodities', {})
                if buy_commodities:
                    commodity_list = [f"{name}: {qty}" for name, qty in list(buy_commodities.items())[:4]]
                    summary = "Always buy: " + ", ".join(commodity_list)
                    if len(buy_commodities) > 4:
                        summary += f" (+{len(buy_commodities) - 4} more)"
                else:
                    summary = "No global commodities configured"
                
                status = "ENABLED" if self.global_shopping_enabled.get() else "DISABLED"
                self.global_summary_text.set(f"Status: {status}\n{summary}")
            else:
                self.global_summary_text.set("Status: No waypoint file loaded")
        except Exception as e:
            self.global_summary_text.set(f"Error: {e}")
    
    def _wp_editor_dialog_global(self):
        """Open edit dialog specifically for GlobalShoppingList"""
        # Create dialog window
        dialog = Toplevel(self.parent)
        dialog.title("Edit Global Shopping List")
        dialog.geometry("500x300")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Get existing global shopping data
        global_data = {}
        if hasattr(self.ed_ap, 'waypoint') and hasattr(self.ed_ap.waypoint, 'waypoints'):
            if 'GlobalShoppingList' in self.ed_ap.waypoint.waypoints:
                global_data = self.ed_ap.waypoint.waypoints['GlobalShoppingList'].copy()
        
        # Create form fields
        fields = {}
        
        # Header
        header_frame = Frame(dialog)
        header_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        dialog.columnconfigure(0, weight=1)
        
        Label(header_frame, text="These commodities will be purchased at EVERY waypoint (if available)",
              font=('TkDefaultFont', 9, 'italic')).grid(row=0, column=0, sticky="w")
        
        # Commodities frame
        commodities_frame = LabelFrame(dialog, text="Global Buy List")
        commodities_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        dialog.rowconfigure(1, weight=1)
        commodities_frame.columnconfigure(1, weight=1)
        
        # Buy commodities (simplified - no sell for global list)
        Label(commodities_frame, text="Always Buy:").grid(row=0, column=0, padx=5, pady=2, sticky="nw")
        fields['BuyCommodities'] = tk.Text(commodities_frame, height=8, width=40)
        fields['BuyCommodities'].grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        
        # Format global buy commodities for display (with cleanup)
        buy_text = ""
        buy_commodities = global_data.get('BuyCommodities', {})
        
        for commodity, quantity in buy_commodities.items():
            buy_text += f"{commodity}: {quantity}\n"
        fields['BuyCommodities'].insert('1.0', buy_text)
        
        # Add help text
        Label(commodities_frame, text="Format: CommodityName: Quantity\nExample: Indite: 50, Gold: 100\nOr one per line", 
              font=('TkDefaultFont', 8), fg='gray').grid(row=0, column=2, padx=5, pady=2, sticky="nw")
        
        # Settings frame
        settings_frame = LabelFrame(dialog, text="Purchase Mode")
        settings_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        # Update commodity count checkbox with better explanation
        fields['UpdateCommodityCount'] = BooleanVar()
        fields['UpdateCommodityCount'].set(global_data.get('UpdateCommodityCount', True))
        cb_update = Checkbutton(settings_frame, text="Shopping List Mode (recommended) - update commodity counts at each waypoint",
                               variable=fields['UpdateCommodityCount'])
        cb_update.grid(row=0, column=0, padx=5, pady=2, sticky="w")
    
        # Buttons frame
        btn_frame = Frame(dialog)
        btn_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        
        def save_global_shopping():
            try:
                # Parse commodities (same logic as waypoint editor)
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
                
                # Build updated global shopping data (preserve existing structure)
                updated_global = global_data.copy()  # Keep existing fields
                updated_global.update({
                    'BuyCommodities': parse_commodities(fields['BuyCommodities']),
                    'UpdateCommodityCount': fields['UpdateCommodityCount'].get(),
                    'Skip': not self.global_shopping_enabled.get()  # Keep current enabled state
                })
                
                # Ensure minimum required fields exist
                for field, default in [
                    ('SystemName', ''), ('StationName', ''), ('SellCommodities', {}),
                    ('FleetCarrierTransfer', False), ('Completed', False)
                ]:
                    if field not in updated_global:
                        updated_global[field] = default
                
                # Save to waypoint list
                if not hasattr(self.ed_ap, 'waypoint'):
                    from EDWayPoint import EDWayPoint
                    self.ed_ap.waypoint = EDWayPoint(self.ed_ap)
                
                if not hasattr(self.ed_ap.waypoint, 'waypoints'):
                    self.ed_ap.waypoint.waypoints = {}
                
                self.ed_ap.waypoint.waypoints['GlobalShoppingList'] = updated_global
                self.changed_waypoints.add('GlobalShoppingList')
                
                self._update_wp_save_button()
                self._refresh_global_shopping_summary()
                self._wp_editor_refresh()
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save global shopping list: {e}")
        
        Button(btn_frame, text="Save", command=save_global_shopping).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        Button(btn_frame, text="Cancel", command=dialog.destroy).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
    def _get_gsl_templates_path(self):
        """Get the path for GSL templates"""
        templates_dir = Path('./gsl_templates')
        templates_dir.mkdir(exist_ok=True)
        return templates_dir
    
    def _save_gsl_template(self):
        """Save current Global Shopping List as a template"""
        try:
            # Get current GSL data
            if not (hasattr(self.ed_ap, 'waypoint') and 
                   hasattr(self.ed_ap.waypoint, 'waypoints') and
                   'GlobalShoppingList' in self.ed_ap.waypoint.waypoints):
                messagebox.showwarning("No Data", "No Global Shopping List found to save as template.")
                return
            
            gsl_data = self.ed_ap.waypoint.waypoints['GlobalShoppingList']
            
            # Check if there are any commodities to save
            buy_commodities = gsl_data.get('BuyCommodities', {})
            if not buy_commodities or all(qty == 0 for qty in buy_commodities.values()):
                messagebox.showwarning("Empty List", "Global Shopping List is empty. Add some commodities first.")
                return
            
            # Prompt for template name
            dialog = Toplevel(self.parent)
            dialog.title("Save GSL Template")
            dialog.geometry("400x200")
            dialog.transient(self.parent)
            dialog.grab_set()
            
            Label(dialog, text="Template Name:", font=('TkDefaultFont', 10, 'bold')).grid(row=0, column=0, padx=10, pady=10, sticky="w")
            
            name_var = StringVar()
            name_entry = Entry(dialog, textvariable=name_var, width=30)
            name_entry.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
            name_entry.focus()
            
            Label(dialog, text="Description (optional):", font=('TkDefaultFont', 10)).grid(row=2, column=0, padx=10, pady=(10,5), sticky="w")
            
            desc_var = StringVar()
            desc_entry = Entry(dialog, textvariable=desc_var, width=30)
            desc_entry.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
            
            # Preview current commodities
            commodities_text = ", ".join([f"{name}: {qty}" for name, qty in buy_commodities.items() if qty > 0])
            preview_label = Label(dialog, text=f"Commodities: {commodities_text}", 
                                 wraplength=350, justify=LEFT, fg='darkblue')
            preview_label.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
            
            dialog.columnconfigure(0, weight=1)
            
            def save_template():
                template_name = name_var.get().strip()
                if not template_name:
                    messagebox.showerror("Error", "Please enter a template name.")
                    return
                
                # Create template data
                template_data = {
                    'name': template_name,
                    'description': desc_var.get().strip(),
                    'created': datetime.now().isoformat(),
                    'buy_commodities': buy_commodities.copy(),
                    'update_commodity_count': gsl_data.get('UpdateCommodityCount', True)
                }
                
                # Save to file
                templates_dir = self._get_gsl_templates_path()
                filename = f"{template_name.replace(' ', '_').replace('/', '_')}.json"
                filepath = templates_dir / filename
                
                try:
                    import json
                    with open(filepath, 'w') as f:
                        json.dump(template_data, f, indent=2)
                    
                    messagebox.showinfo("Success", f"Template '{template_name}' saved successfully!")
                    dialog.destroy()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save template: {e}")
            
            btn_frame = Frame(dialog)
            btn_frame.grid(row=5, column=0, padx=10, pady=10, sticky="ew")
            btn_frame.columnconfigure(0, weight=1)
            btn_frame.columnconfigure(1, weight=1)
            
            Button(btn_frame, text="Save", command=save_template).grid(row=0, column=0, padx=5, sticky="ew")
            Button(btn_frame, text="Cancel", command=dialog.destroy).grid(row=0, column=1, padx=5, sticky="ew")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {e}")
    
    def _load_gsl_template(self):
        """Load a Global Shopping List template"""
        try:
            templates_dir = self._get_gsl_templates_path()
            
            # Get available templates
            template_files = list(templates_dir.glob('*.json'))
            if not template_files:
                messagebox.showinfo("No Templates", "No GSL templates found. Save a template first.")
                return
            
            # Load template data
            templates = []
            for filepath in template_files:
                try:
                    import json
                    with open(filepath, 'r') as f:
                        template_data = json.load(f)
                        template_data['filepath'] = filepath
                        templates.append(template_data)
                except Exception as e:
                    print(f"Failed to load template {filepath}: {e}")
            
            if not templates:
                messagebox.showerror("Error", "No valid templates found.")
                return
            
            # Create selection dialog
            dialog = Toplevel(self.parent)
            dialog.title("Load GSL Template")
            dialog.geometry("500x400")
            dialog.transient(self.parent)
            dialog.grab_set()
            
            Label(dialog, text="Select Template:", font=('TkDefaultFont', 10, 'bold')).grid(row=0, column=0, padx=10, pady=10, sticky="w")
            
            # Template list
            list_frame = Frame(dialog)
            list_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
            
            template_listbox = tk.Listbox(list_frame, height=8)
            template_listbox.grid(row=0, column=0, sticky="nsew")
            
            scrollbar = Scrollbar(list_frame, orient="vertical", command=template_listbox.yview)
            scrollbar.grid(row=0, column=1, sticky="ns")
            template_listbox.configure(yscrollcommand=scrollbar.set)
            
            list_frame.columnconfigure(0, weight=1)
            list_frame.rowconfigure(0, weight=1)
            
            # Populate template list
            for template in templates:
                name = template.get('name', 'Unnamed')
                desc = template.get('description', '')
                created = template.get('created', '')
                if created:
                    try:
                        from datetime import datetime
                        created_date = datetime.fromisoformat(created).strftime('%Y-%m-%d')
                        display_text = f"{name} ({created_date})"
                    except:
                        display_text = name
                else:
                    display_text = name
                
                if desc:
                    display_text += f" - {desc}"
                
                template_listbox.insert(tk.END, display_text)
            
            # Preview frame
            preview_frame = LabelFrame(dialog, text="Template Preview")
            preview_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
            
            preview_text = tk.StringVar()
            preview_label = Label(preview_frame, textvariable=preview_text, 
                                 justify=LEFT, anchor="nw", wraplength=450)
            preview_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
            
            def on_template_select(event):
                selection = template_listbox.curselection()
                if selection:
                    template = templates[selection[0]]
                    buy_commodities = template.get('buy_commodities', {})
                    commodities_text = ", ".join([f"{name}: {qty}" for name, qty in buy_commodities.items()])
                    preview_text.set(f"Commodities: {commodities_text}\n"
                                   f"Mode: {'Shopping List' if template.get('update_commodity_count', True) else 'Fixed Quantity'}")
            
            template_listbox.bind('<<ListboxSelect>>', on_template_select)
            
            dialog.columnconfigure(0, weight=1)
            dialog.rowconfigure(1, weight=1)
            
            def load_selected_template():
                selection = template_listbox.curselection()
                if not selection:
                    messagebox.showerror("Error", "Please select a template.")
                    return
                
                template = templates[selection[0]]
                
                # Apply template to current GSL
                if not hasattr(self.ed_ap, 'waypoint'):
                    from EDWayPoint import EDWayPoint
                    self.ed_ap.waypoint = EDWayPoint(self.ed_ap)
                
                if not hasattr(self.ed_ap.waypoint, 'waypoints'):
                    self.ed_ap.waypoint.waypoints = {}
                
                # Get current GSL or create new one
                current_gsl = self.ed_ap.waypoint.waypoints.get('GlobalShoppingList', {})
                
                # Update GSL with template data
                current_gsl.update({
                    'BuyCommodities': template.get('buy_commodities', {}),
                    'UpdateCommodityCount': template.get('update_commodity_count', True),
                    'Skip': False  # Enable GSL when loading template
                })
                
                # Ensure required fields exist
                for field, default in [
                    ('SystemName', ''), ('StationName', ''), ('SellCommodities', {}),
                    ('FleetCarrierTransfer', False), ('Completed', False)
                ]:
                    if field not in current_gsl:
                        current_gsl[field] = default
                
                self.ed_ap.waypoint.waypoints['GlobalShoppingList'] = current_gsl
                self.changed_waypoints.add('GlobalShoppingList')
                
                # Update UI
                self.global_shopping_enabled.set(True)  # Enable checkbox
                self._update_wp_save_button()
                self._refresh_global_shopping_summary()
                self._wp_editor_refresh()
                
                messagebox.showinfo("Success", f"Template '{template.get('name', 'Unnamed')}' loaded successfully!")
                dialog.destroy()
            
            btn_frame = Frame(dialog)
            btn_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
            btn_frame.columnconfigure(0, weight=1)
            btn_frame.columnconfigure(1, weight=1)
            btn_frame.columnconfigure(2, weight=1)
            
            Button(btn_frame, text="Load", command=load_selected_template).grid(row=0, column=0, padx=5, sticky="ew")
            Button(btn_frame, text="Delete", command=lambda: self._delete_template(template_listbox, templates, dialog)).grid(row=0, column=1, padx=5, sticky="ew")
            Button(btn_frame, text="Cancel", command=dialog.destroy).grid(row=0, column=2, padx=5, sticky="ew")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {e}")
    
    def _delete_template(self, listbox, templates, dialog):
        """Delete selected template"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showerror("Error", "Please select a template to delete.")
            return
        
        template = templates[selection[0]]
        template_name = template.get('name', 'Unnamed')
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete template '{template_name}'?"):
            try:
                filepath = template['filepath']
                filepath.unlink()  # Delete the file
                messagebox.showinfo("Success", f"Template '{template_name}' deleted successfully!")
                dialog.destroy()
                # Reopen the load dialog to refresh the list
                self._load_gsl_template()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete template: {e}")