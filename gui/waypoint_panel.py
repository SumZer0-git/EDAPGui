import tkinter as tk
from tkinter import (
    BooleanVar, Button, Entry, Frame, IntVar, Label, LabelFrame, 
    StringVar, LEFT
)
from tkinter import Checkbutton


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