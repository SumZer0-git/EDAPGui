import sys
import os 
import threading
import kthread
from datetime import datetime
from time import sleep
import cv2
import json
from pathlib import Path
import keyboard

from PIL import Image, ImageGrab, ImageTk
import tkinter as tk
from tkinter import messagebox
from tkinter import *
from tkinter import filedialog as fd

from Voice import *

from Image_Templates import *
from Screen import * 
from Screen_Regions import * 
from EDKeys import * 
from EDJournal import * 
from ED_AP import *

from EDlogger import logger


"""
File:EDAPGui.py    

Description:
User interface for controlling the ED Autopilot

Note:
A lot of the code in this package was taken from:
 https://github.com/skai2/EDAutopilot
 
 HotKeys:
    Home - Start FSD Assist
    INS  - Start SC Assist
    End - Terminate any ongoing assist (FSD, SC, AFK)

Author: sumzer0@yahoo.com
"""

class APGui():
    def __init__(self, root):
        self.root = root
        root.title("EDAutopilot")
        #root.overrideredirect(True)
        #root.geometry("400x550")
        #root.configure(bg="blue")
        root.protocol("WM_DELETE_WINDOW", self.close_window)
        root.resizable(False, False)
        
        self.ed_ap = EDAutopilot(cb=self.callback)
     

        self.checkboxvar = {}
        self.entries = {}
        self.lab_ck = {}
       
        self.FSD_A_running = False
        self.SC_A_running = False

        self.cv_view = False

        self.msgList = self.gui_gen(root)
     
        self.checkboxvar['Enable Voice'].set(1)
       
        # load the rates we have hardcoded
        self.entries['PitchRate'].delete(0,END)
        self.entries['RollRate'].delete(0,END) 
        self.entries['YawRate'].delete(0,END)  
        self.entries['PitchRate'].insert(0,float(self.ed_ap.pitchrate))
        self.entries['RollRate'].insert(0, float(self.ed_ap.rollrate)) 
        self.entries['YawRate'].insert(0,float(self.ed_ap.yawrate))   

        # global trap for these keys, the 'end' key will stop any current AP action
        # the 'home' key will start the FSD Assist.  May want another to start SC Assist
        keyboard.add_hotkey('end',  self.stop_all_assists)
        keyboard.add_hotkey('home', self.callback, args =('fsd_start', None))
        keyboard.add_hotkey('ins',  self.callback, args =('sc_start',  None))
 

    # callback from the EDAP, to configure GUI items
    def callback(self, key, body=None):
        if key == 'log':
            self.log_msg(body)
        elif key == 'fsd_stop':
            self.checkboxvar['FSD Route Assist'].set(0)
            self.check_cb('FSD Route Assist')
        elif key == 'fsd_start':
            self.checkboxvar['FSD Route Assist'].set(1)
            self.check_cb('FSD Route Assist')            
        elif key == 'sc_stop':
            self.checkboxvar['Supercruise Assist'].set(0)
            self.check_cb('Supercruise Assist')
        elif key == 'sc_start':
            self.checkboxvar['Supercruise Assist'].set(1)
            self.check_cb('Supercruise Assist')
        elif key == 'afk_stop':
            self.checkboxvar['AFK Combat Assist'].set(0)
            self.check_cb('AFK Combat Assist')       
        elif key == 'jumpcount':
            self.update_jumpcount(body)
        elif key == 'statusline':
            self.update_statusline(body)

    def test_callback(self):
        sleep(2)
        #dock()
    
    def quit(self):
        self.close_window()
       
    def close_window(self):
        self.stop_fsd()
        self.stop_sc()
        self.ed_ap.quit()
        sleep(0.1)
        self.root.destroy()

    # this routine is to stop any current autopilot activity 
    def stop_all_assists(self):
        self.stop_fsd()
        self.stop_sc()
        #self.stop_afk()

    def start_fsd(self):
        self.ed_ap.set_fsd_assist(True)
        self.FSD_A_running = True

    def stop_fsd(self):
        self.ed_ap.set_fsd_assist(False)
        self.FSD_A_running = False
       
    def start_sc(self):
        self.ed_ap.set_sc_assist(True)
        self.SC_A_running = True

    def stop_sc(self):
        self.ed_ap.set_sc_assist(False)
        self.SC_A_running = False
   
    def about(self):
        messagebox.showinfo('Autopilot', 'Autopilot')

    def log_msg(self, msg):
        self.msgList.insert(END, msg)
        self.msgList.yview(END)

    def set_statusbar(self, txt):
        self.statusbar.configure(text=txt)

    def update_jumpcount(self, txt):
        self.jumpcount.configure(text=txt)

    def update_statusline(self, txt):
        self.status.configure(text="Status: "+txt)

    def open_file(self):
        filetypes = (
            ('text files', '*.txt'),
            ('All files', '*.*')
        )

        filename = fd.askopenfilename(
            title='Open a file',
            initialdir='.',
            filetypes=filetypes)

        if not filename:
            return

        with open(filename, 'r') as json_file:
            f_details = json.load(json_file)

        # load up the display with what we read, the pass it along to AP
        self.entries['PitchRate'].delete(0,END)
        self.entries['RollRate'].delete(0,END) 
        self.entries['YawRate'].delete(0,END)    

        self.entries['PitchRate'].insert(0,f_details['pitchrate'])
        self.entries['RollRate'].insert(0, f_details['rollrate']) 
        self.entries['YawRate'].insert(0,f_details['yawrate'])       

        self.ed_ap.rollrate = float(f_details['rollrate'])
        self.ed_ap.pitchrate = float(f_details['pitchrate'])
        self.ed_ap.yawrate = float(f_details['yawrate'])
        
        self.filelabel.set("Config: "+ Path(filename).name)


    def save_file(self):
        filetypes = (
            ('text files', '*.txt'),
            ('All files', '*.*')
        )

        self.ed_ap.pitchrate = self.entries['PitchRate'].get()
        self.ed_ap.rollrate = self.entries['RollRate'].get()
        self.ed_ap.yawrate = self.entries['YawRate'].get()  

        f_details = {
                'rollrate': self.ed_ap.rollrate,
                'pitchrate': self.ed_ap.pitchrate,
                'yawrate': self.ed_ap.yawrate
            }
        filename = fd.asksaveasfilename(
            title='Save a file',
            initialdir='.',
            filetypes=filetypes)

        if not filename:
            return

        with open(filename, 'w') as json_file:
            json.dump(f_details, json_file)

        self.filelabel.set("Config: "+ Path(filename).name)
        

    # new data was added to a field, re-read them all for simple logic
    def entry_update(self, event):
        self.ed_ap.pitchrate = self.entries['PitchRate'].get()
        self.ed_ap.rollrate = self.entries['RollRate'].get()
        self.ed_ap.yawrate = self.entries['YawRate'].get()  


     # ckbox.state:(ACTIVE | DISABLED)

    # ('FSD Route Assist', 'Supercruise Assist', 'Enable Voice', 'Enable CV View')
    def check_cb(self, field):
    #    print("got event:",  checkboxvar['FSD Route Assist'].get(), " ", str(FSD_A_running))
        if field == 'FSD Route Assist':
            if (self.checkboxvar['FSD Route Assist'].get() == 1 and self.FSD_A_running == False):
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                self.start_fsd()

            elif (self.checkboxvar['FSD Route Assist'].get() == 0 and self.FSD_A_running == True):
                self.stop_fsd()
                self.lab_ck['Supercruise Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
            
        if field == 'Supercruise Assist':
            if (self.checkboxvar['Supercruise Assist'].get() == 1 and self.SC_A_running == False):
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.start_sc()

            elif (self.checkboxvar['Supercruise Assist'].get() == 0 and self.SC_A_running == True):
                self.stop_sc()
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
    
        if self.checkboxvar['ELW Scanner'].get() == 1:
            self.ed_ap.set_fss_scan(True)
        if self.checkboxvar['ELW Scanner'].get() == 0:
            self.ed_ap.set_fss_scan(False)

        if field == 'AFK Combat Assist':
            if self.checkboxvar['AFK Combat Assist'].get() == 1:
                self.ed_ap.set_afk_combat_assist(True)
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                
            elif self.checkboxvar['AFK Combat Assist'].get() == 0:
                self.ed_ap.set_afk_combat_assist(False)
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['Supercruise Assist'].config(state='active')

     
        if (self.checkboxvar['Enable Voice'].get() == 1):
            self.ed_ap.set_voice(True)
        else:
            self.ed_ap.set_voice(False)

        if (self.checkboxvar['Enable CV View'].get() == 1):
            self.cv_view = True
            x = self.root.winfo_x() + self.root.winfo_width() + 4
            y = self.root.winfo_y()
            self.ed_ap.set_cv_view(True, x, y)
        else:
            self.cv_view = False
            self.ed_ap.set_cv_view(False)



    def makeform(self, win, ftype, fields):
        entries = {}

        for field in fields:
            row = tk.Frame(win)
            if (ftype == 0):
                self.checkboxvar[field] = IntVar()
                lab = Checkbutton(row, text=field, anchor='w', justify=LEFT, variable=self.checkboxvar[field], command=(lambda field=field: self.check_cb(field)))
                self.lab_ck[field] = lab 
            else:
                ent = tk.Entry(row, width=10)
                ent.bind('<FocusOut>', self.entry_update)
                lab = tk.Label(row, width=15, text=field+": ", anchor='w')
                ent.insert(0, "0")
      
            row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=1)  # 

            lab.pack(side=tk.LEFT)

            if (ftype == 1):
                ent.pack(side=tk.LEFT)  # , expand=tk.YES)  # , fill=tk.X) 
                entries[field] = ent
        return entries


    def gui_gen(self, win):

        check_fields = ('FSD Route Assist', 'Supercruise Assist', "ELW Scanner", "AFK Combat Assist") 
        entry_fields = ('RollRate', 'PitchRate', 'YawRate' )  # , 'ScoopAccelTime')

        blk0 = tk.Frame(win, relief=tk.RAISED, borderwidth=1) 

        blk1 = tk.Frame(blk0, relief=tk.RAISED, borderwidth=1, width=25)
        cEnt = self.makeform(blk1, 0, check_fields)

        self.filelabel = StringVar()
        self.filelabel.set("<no config loaded>")
        lab = Label(blk0, textvariable=self.filelabel)
        lab.pack(side=BOTTOM, anchor=S)
            
        blk2 = tk.Frame(blk0, relief=tk.RAISED, borderwidth=1, width=40)
        self.entries = self.makeform(blk2, 1, entry_fields)
        
        blk1.pack(side=LEFT, anchor=N, padx=10, pady=3)
        blk2.pack(side=LEFT, padx=2, pady=3)

     #   btn = Button(blk1, text=test_label, command=self.test_callback)
     #   btn.pack(side=tk.LEFT)

        blk0.grid(row=0, column=0, padx=2, pady=2)
        
        row = tk.Frame(win, relief=tk.RAISED, borderwidth=1, width=200)
        scrollbar = Scrollbar(row)
        scrollbar.pack( side = RIGHT, fill = Y )

        #Label(win, text="Runtime Messages")   # .grid(row=4, sticky=W)
        mylist = Listbox(row, width=60, height=10, yscrollcommand = scrollbar.set )

        mylist.pack( side = LEFT, expand=True, fill = X )
        scrollbar.config( command = mylist.yview )

        row.grid(row=1,column=0, padx=2, pady=2)

        #
        # Define all the menus
        #
        menubar = Menu(win, background='#ff8000', foreground='black', activebackground='white', activeforeground='black')  
        file = Menu(menubar, tearoff=1, background='#ffcc99', foreground='black')  
        file.add_command(label="Open",command=self.open_file)  
        file.add_command(label="Save as", command=self.save_file)    
        file.add_separator() 
        self.checkboxvar['Enable Voice'] = IntVar()
        file.add_checkbutton(label='Enable Voice', onvalue=1, offvalue=0, variable=self.checkboxvar['Enable Voice'], command=(lambda field='Enable Voice': self.check_cb(field))) 
        self.checkboxvar['Enable CV View'] = IntVar()
        file.add_checkbutton(label='Enable CV View', onvalue=1, offvalue=0, variable=self.checkboxvar['Enable CV View'], command=(lambda field='Enable CV View': self.check_cb(field)))
        file.add_separator()
        file.add_command(label="Exit", command=self.close_window)   # win.quit)  
        menubar.add_cascade(label="File", menu=file)  

        help = Menu(menubar, tearoff=0)  
        help.add_command(label="About", command=self.about)  
        menubar.add_cascade(label="Help", menu=help) 

        win.config(menu=menubar)

        statusbar = Frame(win)
        #statusbar.pack(side="bottom", fill="x", expand=False)
        statusbar.grid(row=2, column=0)

        self.status    = tk.Label(win, text="Status: ", bd=1, relief=tk.SUNKEN, anchor=tk.W, justify=LEFT, width=45 )
        self.jumpcount = tk.Label(statusbar, text="Jump: ",   bd=1, relief=tk.SUNKEN, anchor=tk.W, justify=LEFT, width=15)
        self.status.pack(in_=statusbar, side=LEFT, fill=BOTH, expand=True)
        self.jumpcount.pack(in_=statusbar, side=RIGHT, fill=Y, expand=False)

        #status.configure(text="Text Updated")

        return mylist






def main():

 #   handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")   
 #   if handle != None:
 #       win32gui.SetForegroundWindow(handle)  # put the window in foreground
        
    root = tk.Tk()
    app = APGui(root)

    root.mainloop()


if __name__ == "__main__":
    main()


 