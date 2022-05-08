from threading import main_thread
from time import sleep

# most of these won't be needed if integrate with EDAPGui
import keyboard
import win32gui

import Screen_Regions
from ED_AP import *
from EDJournal import *
from EDKeys import *
from EDlogger import logger
from Image_Templates import *
from Overlay import *
from Screen import *
from Voice import *


"""
File:Robigo.py   

Description:
This class contains the script required to execute the Robigo passenger mission loop

Constraints:
- Must start off docked at Robigo Mines
- Odyssey only (due to unique Mission Selection and Mission Completion menus)
- Must perform 1 Robigo loop manually
    - This will ensure the Siruis Atmospherics will be on the Nav Panel on subsequent runs
- Set Nav Menu Filter to: Stations and POI only
    - Removes the clutter and allows faster selection of Robigo Mines and Sirius Athmos
``
Author: sumzer0@yahoo.com
"""

# TODO:  
#  - Mission accepting does not pick up all missions, as missions are selected the
#    list gets updated and we end up in a slot that is below the Missions we want
#  - Undock:  Still not there yet, sometimes destination on opposite side of ring
#  - Robigo Mines SC:  Some times Robigo mines are other side of the ring
#  - Scanning: trigger testing to activate heatsink, if using Scanned from event in Journal
#    it is too late as they attack at the same time.  The ReceiveText with 'prepared to be 
#    scanned seems to happen 10sec before attacking 
#  - The sothis_A5 image template currently not used
#  - to fix this for Horizon, would have to write new routines for get_missions() and complete_missions
#     then similar to Waypoints use the         if is_odyssey != True:   to call the right routine
#
# ensure Nav Menu filter is set to: Stations and POI only
# must do a run first to discover the Siruis Atmos marker so when going back there the 
#  Sirius Atmos is on the Nav Panel
#
# Set AP.json to change refuelthreshold to like 25 since python does not have scoop
# Hardset your ships pitch/yaw/roll rates in main below
#
#


class Robigo:
    def __init__(self, ed_ap):
        self.ap = ed_ap   # TODO: Need clean up, put some initializer in here
        self.num_missions = 0
      
    # 
    # This function will look to see if the passed in template is in the region of the screen specified  
    def is_found(self, ap, region, templ) -> bool:
        (img,
            (minVal, maxVal, minLoc, maxLoc),
            match,
        ) = ap.scrReg.match_template_in_region(region, templ)

        if maxVal > 80:
            print("Image Match: "+templ+" " + str(maxVal))

        # use high percent 
        if maxVal > 0.80: 
            return True
        else:
            return False       


    def complete_missions(self, ap):

        # Asssume in passenger Lounge
        ap.keys.send("UI_Right", repeat=2)  # go to Complete Mission
        ap.keys.send("UI_Select")

        sleep(2)  # give time for mission page to come up

        found = self.is_found(ap, "missions", "missions")

        # we don't have any missions to complete as the screen did not change
        if found:
            print("no missions to complete")
            ap.keys.send("UI_Left")
            return

        ap.keys.send("UI_Up", repeat=2)  # goto the top
        ap.keys.send("UI_Down")  # down one to select first mission
        sleep(0.5)
        for i in range(8):  # Up to 8 missions to hand in
            ap.keys.send("UI_Select")  # select mission
            sleep(0.1)
            ap.keys.send("UI_Up")  # Up to Credit
            sleep(0.1)
            ap.keys.send("UI_Select")  # Select it
            sleep(9)   # wait until the "skip" button changes to "back" button
            ap.keys.send("UI_Select")  # Select the Back key which will be highlighted
            sleep(1.5)
            self.num_missions += 1

        ap.keys.send("UI_Back")  # seem to be going back to Mission menu
        

    def lock_target(self, ap, templ) -> bool:
        found = False
        tries = 0
        
        # get to the Left Panel menu: Navigation
        ap.keys.send("UI_Back", repeat=10)
        ap.keys.send("HeadLookReset")
        ap.keys.send("UIFocus", state=1)
        ap.keys.send("UI_Left")
        ap.keys.send("UIFocus", state=0)   # this gets us over to the Nav panel
        sleep(0.5)

        # 
        ap.keys.send("UI_Down", hold=2)  # got to bottom row

        # tries is the number of rows to go through to find the item looking for
        # the Nav Panel should be filtered to reduce the number of rows in the list
        while not found and tries < 50:
            found = self.is_found(ap, "nav_panel", templ)   
            if found:
                ap.keys.send("UI_Select", repeat=2)  # Select it and lock target
            else:
                tries += 1
                ap.keys.send("UI_Up")   # up to next item
                sleep(0.2)

        ap.keys.send("UI_Back", repeat=10)  # go back and drop Nav Panel
        ap.keys.send("HeadLookReset")
        return found
        

    def select_mission(self, ap):
        ap.keys.send("UI_Select", repeat=2)  # select mission and Pick Cabin
        ap.keys.send("UI_Down")    # move down to Auto Fill line
        sleep(0.1)
        ap.keys.send("UI_Right", repeat=2)  # go over to "Auto Fill"
        ap.keys.send("UI_Select")  # Select auto fill
        sleep(0.1)
        ap.keys.send("UI_Select")  # Select Accept Mission, which was auto highlighted
        

    def get_missions(self, ap):
        cnt = 0
        mission_cnt = 0
        had_selected = False

        # Asssume in passenger Lounge. goto Missions Menu
        ap.keys.send("UI_Up", repeat=3)
        sleep(0.2)
        ap.keys.send("UI_Down", repeat=2)
        sleep(0.2)
        ap.keys.send("UI_Select")  # select personal transport
        sleep(15)  # wait 15 second for missions menu to show up

        # Loop selecting missions, go up to 15 times
        while cnt < 15:
            found = self.is_found(ap, "mission_dest", "dest_sirius")

            # not a sirius mission
            if not found:
                ap.keys.send("UI_Down")   # not sirius, go down to next
                sleep(0.1)
                # if we had selected missions and suddenly we are not
                # then go back to top and scroll down again. This is due to scrolling
                # missions 
                if had_selected:
                    ap.keys.send("UI_Up", hold=2)  # go back to very top
                    ap.keys.send("UI_Down")  # down to missions, when we loop we'll go down 1 more time
                    cnt = 1  # reset counter  
                    had_selected = False               

                cnt = cnt + 1
            else:
                mission_cnt += 1    # found a mission, select it
                had_selected = True
                self.select_mission(ap)
                sleep(1.5)

        ap.keys.send("UI_Back", repeat=4)  # go back to main menu
        

    def fill_repair_ammo(self, ap):
        # on main menu on starport/outpost
        ap.keys.send("UI_Up", hold=3)  # go to very top
        ap.keys.send("UI_Select")  # fuel highlighted, select it
        sleep(0.5)
        ap.keys.send("UI_Right")  # Repair
        ap.keys.send("UI_Select")
        sleep(0.5)
        ap.keys.send("UI_Right")  # Ammo (heat sinks)
        ap.keys.send("UI_Select")
        sleep(0.5)
        ap.keys.send("UI_Left", repeat=2)  # back to fuel
                

    def goto_passenger_lounge(self, ap):
        # Go down to station services and select
        ap.keys.send("UI_Back", repeat=5)  # make sure at station menu
        ap.keys.send("UI_Up", hold=2)  # go to very top  
        ap.keys.send("UI_Down")
        ap.keys.send("UI_Select")
        sleep(6)  # give time for Mission Board to come up

        ap.keys.send("UI_Up")      # ensure at Missio Board
        ap.keys.send("UI_Left")    #        
        ap.keys.send("UI_Select")  # select Mission Board
        sleep(1)
        ap.keys.send("UI_Right")  # Passenger lounge
        sleep(0.1)
        ap.keys.send("UI_Select")

        
    def undock_outpost(self, ap):        
        ap.undock()
        # need to wait until undock complete, that is when we are back in_space
        while ap.jn.ship_state()['status'] != 'in_space':
            sleep(1)

        # move away from station
        sleep(1.5)
        ap.keys.send('SetSpeed100')
        sleep(1)
        ap.keys.send('UseBoostJuice')
        sleep(10)  # get away from Station
        ap.keys.send('SetSpeedZero')   
             

    def loop(self, ap):
        scr = ap.scr
        scr_reg = ap.scrReg
        loop_cnt = 0
        
        starttime = time.time()

        while True:
            # start off assuming at Robigo Mines main menu
            elapsed_time = time.time() - starttime
            starttime = time.time()
            print(str(loop_cnt)+" Time for loop: "+  time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))
            loop_cnt += 1
            
            self.fill_repair_ammo(ap)
   
            print("Completing missions")

            # Complete Missions, if we have any
            self.goto_passenger_lounge(ap)
            sleep(2.5)  # wait for new menu comes up
            self.complete_missions(ap)
            print("Num Missions Completed: "+str(self.num_missions))

            print("Getting missions")
            # Select and fill up on Sirius missions   
            self.goto_passenger_lounge(ap)
            sleep(1)
            self.get_missions(ap)
            
            print("Setting waypont to SOTHIS")
            # Target SOTHIS and plot route
            ap.jn.ship_state()["target"] = None   # must clear out previous target from Journal
            dest = ap.waypoint.set_waypoint_target(ap, "SOTHIS ", target_select_cb=ap.jn.ship_state)

            if dest == False:
                print("SOTHIS destination not set: " + str(dest))
                break
            
            sleep(1)    # give time to popdown GalaxyMap
            print("Doing Undock")
            # if we got the destination and perform undocking
            ap.keys.send("SetSpeedZero")  # ensure 0 so auto undock will work           
            self.undock_outpost(ap)
            
            print("FSD Assist")
            
            # away from station, time for Route Assist to get us to SOTHIS
            ap.fsd_assist(scr_reg)
    
            # [In Sothis]
            # select Siruis Atmos
            found = self.lock_target(ap, 'sirius_atmos')  # TODO: if not find atmos, then jump back to sothis_A5
            
            if found == False:
                print("Unable to lock on Sirius Atmos in Nav Panel")
                return
            
            # SC to Marker, tell assist not to attempt docking since we are going to a marker
            ap.sc_assist(scr_reg, do_docking=False)
            
            # wait until we are back in_space
            while ap.jn.ship_state()['status'] != 'in_space':
                sleep(1)

            # give a few more seconds
            sleep(2)
            ap.keys.send("SelectTarget")    # target the marker so missions will complet
            ap.jn.ship_state()['to_be_scanned'] = False  # reset to false
            
            sleep(4)
            
            # any way to check that met mission objectives?
            
            # Set Route back to Robigo
            dest = ap.waypoint.set_waypoint_target(ap, "ROBIGO", target_select_cb=ap.jn.ship_state)
            sleep(2)
            
            if dest == False:
                print("Robigo destination not set: " + str(dest))
                break
      
            # have Route Assist bring us back to Robigo system
            ap.fsd_assist(scr_reg)
            ap.keys.send("SetSpeed50")
            sleep(2)
      
            # In Robigo System, select Robigo Mines in the Nav Panel, which should 1 down (we select in the blind)
            #   The Robigo Mines position in the list is dependent on distance from current location
            #   The Speed50 above and waiting 2 seconds ensures Robigo Mines is 2 down from top
            found = self.lock_target(ap, 'robigo_mines')
            
            if found == False:
                print("Unable to lock on Robigo Mines in Nav Panel")
                return

            # SC Assist to Robigo Mines and dock
            ap.sc_assist(scr_reg)
            # the sc_assist and docks does refueling and repair, need to go back Left to Fuel to be highlighted
            ap.keys.send("UI_Left")    #               


# --------------------------------------------------------
global main_thrd
global ap1

class EDAP_Interrupt(Exception):
    pass

def key_callback(name):
    global ap1, main_thrd 
    print("exiting")

    # if name == "end":
    ap1.ctype_async_raise(main_thrd, EDAP_Interrupt)
    


def callback(self, key, body=None):
    pass
   # print("cb:"+str(body))


def main():
    global main_thrd , ap1
    
    main_thrd = threading.current_thread()

    ap = EDAutopilot(callback, False)
    ap1 = ap

    # assume python
    ap.rollrate  = 104.0
    ap.pitchrate = 33.0
    ap.yawrate   = 11.0
    ap.sunpitchuptime = 1.0

    robigo = Robigo(ap)

    ap.terminate = True  # no need for the AP's engine loop to run

    # trap specific hotkeys
    keyboard.add_hotkey("home", key_callback, args=("q"))
    keyboard.add_hotkey("end", key_callback, args=("s"))

    # print("Going to sleep")
    try:
        robigo.loop(ap)
    except EDAP_Interrupt:
        logger.debug("Caught stop exception")
    except Exception as e:
        print("Trapped generic:" + str(e))
        traceback.print_exc()

    print("Terminating")
    ap.overlay.overlay_quit()
    ap.vce.quit()


if __name__ == "__main__":
    main()
