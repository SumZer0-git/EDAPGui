import tkinter as tk
from tkinter import (
    BooleanVar, Button, Checkbutton, Entry, Frame, IntVar, Label, LabelFrame, 
    Listbox, Scrollbar, StringVar, LEFT, END, BOTH, Y, RIGHT
)
from idlelib.tooltip import Hovertip


class AssistPanel:
    """Panel for autopilot assist controls and monitoring"""
    
    def __init__(self, parent_frame, ed_ap, tooltips, check_callback):
        self.parent = parent_frame
        self.ed_ap = ed_ap
        self.tooltips = tooltips
        self.check_callback = check_callback
        
        # Store references to GUI elements
        self.checkboxvar = {}
        self.lab_ck = {}
        
        # Assist state tracking
        self.FSD_A_running = False
        self.SC_A_running = False
        self.WP_A_running = False
        self.RO_A_running = False
        self.DSS_A_running = False
        self.SWP_A_running = False
        
        # Pause system state
        self.all_paused = False
        self.paused_assists = []
        
        # String variables for file labels
        self.wp_filelabel = StringVar()
        self.wp_filelabel.set("<no waypoint list loaded>")
        
        self._create_control_gui()
    
    def _create_control_gui(self):
        """Create the control panel GUI"""
        control_main = tk.Frame(self.parent)
        control_main.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        control_main.columnconfigure([0, 1], weight=1, minsize=100, uniform="group1")

        # Assist modes block
        self._create_assist_modes_block(control_main)
        
        # Autopilot control block
        self._create_autopilot_control_block(control_main)
        
        # Log and status block
        self.msgList = self._create_log_status_block()
    
    def _create_assist_modes_block(self, parent):
        """Create assist modes checkboxes"""
        blk_modes = LabelFrame(parent, text="ASSIST MODES")
        blk_modes.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        
        modes_check_fields = ('FSD Route Assist', 'Supercruise Assist', 'Waypoint Assist', 
                             'Robigo Assist', 'AFK Combat Assist', 'DSS Assist')
        
        r = 0
        for field in modes_check_fields:
            row = tk.Frame(blk_modes)
            row.grid(row=r, column=0, padx=2, pady=2, sticky="nsew")
            r += 1

            self.checkboxvar[field] = IntVar()
            lab = Checkbutton(row, text=field, anchor='w', width=27, justify=LEFT, 
                             variable=self.checkboxvar[field], 
                             command=lambda field=field: self.check_callback(field))
            self.lab_ck[field] = lab
            lab.grid(row=0, column=0)
            
            # Add tooltip
            tip = Hovertip(row, self.tooltips[field], hover_delay=1000)
    
    def _create_autopilot_control_block(self, parent):
        """Create autopilot control buttons and waypoint loading"""
        blk_controls = LabelFrame(parent, text="AUTOPILOT CONTROL")
        blk_controls.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        
        # Pause/Resume buttons
        self.btn_pause = Button(blk_controls, text='Pause All', command=self._toggle_pause_all, 
                               bg='orange', relief='raised')
        self.btn_pause.grid(row=0, column=0, padx=2, pady=2, sticky="news")
        tip_pause = Hovertip(self.btn_pause, self.tooltips['Pause All Button'], hover_delay=1000)
        
        self.btn_resume = Button(blk_controls, text='Resume All', command=self._toggle_pause_all,
                                bg='gray', state='disabled', relief='raised')
        self.btn_resume.grid(row=0, column=1, padx=2, pady=2, sticky="news")
        tip_resume = Hovertip(self.btn_resume, self.tooltips['Resume All Button'], hover_delay=1000)
        
        # Emergency Stop button
        self.btn_stop_all = Button(blk_controls, text='STOP ALL', command=self._emergency_stop_all,
                                  bg='red', fg='white', relief='raised', font=('TkDefaultFont', 9, 'bold'))
        self.btn_stop_all.grid(row=1, column=0, padx=2, pady=2, columnspan=2, sticky="news")
        tip_stop_all = Hovertip(self.btn_stop_all, self.tooltips['Stop All Button'], hover_delay=1000)

        # Waypoint file loading
        btn_wp_file = Button(blk_controls, textvariable=self.wp_filelabel, command=self._open_wp_file)
        btn_wp_file.grid(row=2, column=0, padx=2, pady=2, columnspan=2, sticky="news")
        tip_wp_file = Hovertip(btn_wp_file, self.tooltips['Waypoint List Button'], hover_delay=1000)

        btn_reset = Button(blk_controls, text='Reset Waypoint List', command=self._reset_wp_file)
        btn_reset.grid(row=3, column=0, padx=2, pady=2, columnspan=2, sticky="news")
        tip_reset = Hovertip(btn_reset, self.tooltips['Reset Waypoint List'], hover_delay=1000)
    
    def _create_log_status_block(self):
        """Create log window and status bar"""
        log = LabelFrame(self.parent, text="LOG & STATUS")
        log.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        log.columnconfigure(0, weight=1)
        log.rowconfigure(0, weight=1)
        
        scrollbar = Scrollbar(log)
        scrollbar.grid(row=0, column=1, sticky="ns")
        mylist = Listbox(log, width=72, yscrollcommand=scrollbar.set)
        mylist.grid(row=0, column=0, sticky="nsew")
        scrollbar.config(command=mylist.yview)
        
        # Make sure the control page expands properly
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(1, weight=1)
        
        return mylist
    
    def _toggle_pause_all(self):
        """Toggle pause/resume all running assists"""
        if not self.all_paused:
            # Pause all running assists
            self.paused_assists = []
            if self.FSD_A_running:
                self.paused_assists.append('FSD')
                self._stop_fsd()
            if self.SC_A_running:
                self.paused_assists.append('SC')
                self._stop_sc()
            if self.WP_A_running:
                self.paused_assists.append('WP')
                self._stop_waypoint()
            if self.RO_A_running:
                self.paused_assists.append('RO')
                self._stop_robigo()
            if self.DSS_A_running:
                self.paused_assists.append('DSS')
                self._stop_dss()
            if self.SWP_A_running:
                self.paused_assists.append('SWP')
                self._stop_single_waypoint_assist()
            
            self.all_paused = True
            self.btn_pause.config(state='disabled', bg='gray')
            self.btn_resume.config(state='normal', bg='lightgreen')
            
        else:
            # Resume previously running assists
            for assist in self.paused_assists:
                if assist == 'FSD':
                    self._start_fsd()
                elif assist == 'SC':
                    self._start_sc()
                elif assist == 'WP':
                    self._start_waypoint()
                elif assist == 'RO':
                    self._start_robigo()
                elif assist == 'DSS':
                    self._start_dss()
                elif assist == 'SWP':
                    self._start_single_waypoint_assist()
            
            self.all_paused = False
            self.paused_assists = []
            self.btn_pause.config(state='normal', bg='orange')
            self.btn_resume.config(state='disabled', bg='gray')
    
    def _emergency_stop_all(self):
        """Emergency stop all assists"""
        self.all_paused = False
        self.paused_assists = []
        
        # Stop all assists through the callback system
        if hasattr(self, 'stop_all_callback'):
            self.stop_all_callback()
        
        # Update GUI buttons
        self.btn_pause.config(state='normal', bg='orange')
        self.btn_resume.config(state='disabled', bg='gray')
    
    def _open_wp_file(self):
        """Open waypoint file"""
        from tkinter import filedialog as fd
        from pathlib import Path
        
        filetypes = (
            ('json files', '*.json'),
            ('All files', '*.*')
        )
        filename = fd.askopenfilename(title="Waypoint File", initialdir='./waypoints/', filetypes=filetypes)
        if filename != "":
            res = self.ed_ap.waypoint.load_waypoint_file(filename)
            if res:
                self.wp_filelabel.set("loaded: " + Path(filename).name)
            else:
                self.wp_filelabel.set("<no list loaded>")
    
    def _reset_wp_file(self):
        """Reset waypoint file"""
        from tkinter import messagebox
        
        if not self.WP_A_running:
            mb = messagebox.askokcancel("Waypoint List Reset", 
                "After resetting the Waypoint List, the Waypoint Assist will start again from the first point in the list at the next start.")
            if mb == True:
                self.ed_ap.waypoint.mark_all_waypoints_not_complete()
        else:
            mb = messagebox.showerror("Waypoint List Error", 
                "Waypoint Assist must be disabled before you can reset the list.")
    
    # Assist control methods - these would need to be connected to the main ED_AP instance
    def _start_fsd(self):
        self.FSD_A_running = True
        
    def _stop_fsd(self):
        self.FSD_A_running = False
        
    def _start_sc(self):
        self.SC_A_running = True
        
    def _stop_sc(self):
        self.SC_A_running = False
        
    def _start_waypoint(self):
        self.WP_A_running = True
        
    def _stop_waypoint(self):
        self.WP_A_running = False
        
    def _start_robigo(self):
        self.RO_A_running = True
        
    def _stop_robigo(self):
        self.RO_A_running = False
        
    def _start_dss(self):
        self.DSS_A_running = True
        
    def _stop_dss(self):
        self.DSS_A_running = False
        
    def _start_single_waypoint_assist(self):
        self.SWP_A_running = True
        
    def _stop_single_waypoint_assist(self):
        self.SWP_A_running = False
    
    def set_stop_all_callback(self, callback):
        """Set callback for emergency stop"""
        self.stop_all_callback = callback
    
    def update_assist_state(self, assist_type, running):
        """Update assist running state"""
        if assist_type == 'FSD':
            self.FSD_A_running = running
        elif assist_type == 'SC':
            self.SC_A_running = running
        elif assist_type == 'WP':
            self.WP_A_running = running
        elif assist_type == 'RO':
            self.RO_A_running = running
        elif assist_type == 'DSS':
            self.DSS_A_running = running
        elif assist_type == 'SWP':
            self.SWP_A_running = running
    
    def set_checkbox_state(self, field, value):
        """Set checkbox state"""
        if field in self.checkboxvar:
            self.checkboxvar[field].set(value)
    
    def get_checkbox_state(self, field):
        """Get checkbox state"""
        if field in self.checkboxvar:
            return self.checkboxvar[field].get()
        return 0
    
    def enable_disable_checkboxes(self, field, state):
        """Enable or disable assist checkboxes"""
        for cb_field in ['FSD Route Assist', 'Supercruise Assist', 'Waypoint Assist', 
                        'Robigo Assist', 'AFK Combat Assist', 'DSS Assist']:
            if cb_field != field and cb_field in self.lab_ck:
                self.lab_ck[cb_field].config(state=state)
    
    def update_waypoint_file_label(self, label_text):
        """Update waypoint file label"""
        self.wp_filelabel.set(label_text)