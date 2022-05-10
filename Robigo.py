# from threading import main_thread
from time import sleep
import time

# most of these won't be needed if integrate with EDAPGui

'''
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
'''


# TODO:
#  - Use GalaxyMap Search for Robigo Mines
#  - Clean up Loop, integrate with GUI
#  - Rework Undocking into main ED_AP
#  - update main ED_AP for fuel_repair_ammo()  add ammo
#  - Handle not at Sirius Atmos, go back into SC, use Journal Body
#  - Anything to do about crash into Robigo Ring?  check body and exit AP
#  - use Statemachine
#    - determine currently location and start from there
#  - Use mission_redirected, mission_completed counters
#  - Update: ChangeLog.md,  Robigo.md,  readme.md
#    - new screen shots
# 

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
- Set refuelthreshold low.. like 35%  so not attempt refuel with a ship that doesn't have fuel scoop
``
Author: sumzer0@yahoo.com
"""

# TODO:  

#  - Robigo Mines SC:  Some times Robigo mines are other side of the ring
#  - to fix this for Horizon, would have to write new routines for get_missions() and complete_missions
#     then similar to Waypoints use the         if is_odyssey != True:   to call the right routine
#
# Set AP.json to change refuelthreshold to like 25 since python does not have scoop
# Hardset your ships pitch/yaw/roll rates in main below
#
#


class Robigo:
    def __init__(self, ed_ap):
        self.ap = ed_ap  
        self.mission_redirect = 0
        self.mission_complete = 0
      
    # 
    # This function will look to see if the passed in template is in the region of the screen specified  
    def is_found(self, ap, region, templ) -> bool:
        (img,
            (minVal, maxVal, minLoc, maxLoc),
            match,
        ) = ap.scrReg.match_template_in_region(region, templ)

        #if maxVal > 75:
        #    print("Image Match: "+templ+" " + str(maxVal))

        # use high percent 
        if maxVal > 0.75: 
            return True
        else:
            return False       


    def complete_missions(self, ap):

        loop_missions = ap.jn.ship_state()['mission_redirected']
        if loop_missions == 0:
            loop_missions = 8
        ap.jn.ship_state()['mission_completed'] = 0
        
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
        for i in range(loop_missions):  
            ap.keys.send("UI_Select")  # select mission
            sleep(0.1)
            ap.keys.send("UI_Up")  # Up to Credit
            sleep(0.1)
            ap.keys.send("UI_Select")  # Select it
            sleep(10)   # wait until the "skip" button changes to "back" button
            ap.keys.send("UI_Select")  # Select the Back key which will be highlighted
            sleep(1.5)

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
                    sleep(0.5)
                    cnt = 1  # reset counter  
                    had_selected = False               

                cnt = cnt + 1
            else:
                mission_cnt += 1    # found a mission, select it
                had_selected = True
                self.select_mission(ap)
                sleep(1.5)

        ap.keys.send("UI_Back", repeat=4)  # go back to main menu              

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
        ap.keys.send("UI_Right")   # Passenger lounge
        sleep(0.1)
        ap.keys.send("UI_Select")
        sleep(2)                   # give time to bring up menu
               
        
    def travel_to_sirius_atmos(self, ap):
 
        ap.jn.ship_state()['mission_redirected'] = 0        
        self.mission_redirected = 0
        
        # at times when coming out of SC, we are still 700-800km away from Sirius Atmos
        # if we do not get mission_redirected journal notices, then SC again
        while self.mission_redirected == 0:        
            # SC to Marker, tell assist not to attempt docking since we are going to a marker
            ap.sc_assist(ap.scrReg, do_docking=False)
            
            # wait until we are back in_space
            while ap.jn.ship_state()['status'] != 'in_space':
                sleep(1)

            # give a few more seconds
            sleep(2)
            ap.keys.send("SetSpeedZero")
            ap.keys.send("SelectTarget")    # target the marker so missions will complete
            # takes about 10-22 sec to acknowledge missions
            sleep(15)
            if ap.jn.ship_state()['mission_redirected'] == 0:
                print("Didnt make it to sirius atmos, should SC again")     

            self.mission_redirected = ap.jn.ship_state()['mission_redirected']
             

    def loop(self, ap):
        loop_cnt = 0
        
        starttime = time.time()

        while True:
            # start off assuming at Robigo Mines main menu
            # Calc elapsed time for a loop and display it
            elapsed_time = time.time() - starttime
            starttime = time.time()
            if loop_cnt != 0:
                ap.ap_ckb('log',str(loop_cnt)+" Time for loop: "+  time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))
            loop_cnt += 1
       
            ap.update_ap_status("Completing missions")
            
            # Complete Missions, if we have any
            self.goto_passenger_lounge(ap)
            sleep(2.5)  # wait for new menu comes up
            self.complete_missions(ap)

            ap.update_ap_status("Get missions")
            # Select and fill up on Sirius missions   
            self.goto_passenger_lounge(ap)
            sleep(1)
            self.get_missions(ap)
            
            ap.update_ap_status("Route to SOTHIS")
            # Target SOTHIS and plot route
            ap.jn.ship_state()["target"] = None   # must clear out previous target from Journal
            dest = ap.waypoint.set_waypoint_target(ap, "SOTHIS ", target_select_cb=ap.jn.ship_state)

            if dest == False:
                ap.update_ap_status("SOTHIS not set: " + str(dest))
                break
            
            sleep(1)    # give time to popdown GalaxyMap
  
            # if we got the destination and perform undocking
            ap.keys.send("SetSpeedZero")  # ensure 0 so auto undock will work 
                      
            ap.waypoint_undock_seq()
            
            ap.update_ap_status("FSD to SOTHIS")
            
            # away from station, time for Route Assist to get us to SOTHIS
            ap.fsd_assist(ap.scrReg)
            
            # [In Sothis]
            # select Siruis Atmos
            found = self.lock_target(ap, 'sirius_atmos')  
            
            if found == False:
                ap.update_ap_status("No Sirius Atmos in Nav Panel")
                return
 
            ap.update_ap_status("SC to Marker")            
            self.travel_to_sirius_atmos(ap)

            ap.update_ap_status("Missions: "+str(self.mission_redirected))
                                 
            # Set Route back to Robigo
            dest = ap.waypoint.set_waypoint_target(ap, "ROBIGO", target_select_cb=ap.jn.ship_state)
            sleep(2)
            
            if dest == False:
                ap.update_ap_status("Robigo not set: " + str(dest))
                break

            ap.update_ap_status("FSD to Robigo")      
            # have Route Assist bring us back to Robigo system
            ap.fsd_assist(ap.scrReg)
            ap.keys.send("SetSpeed50")
            sleep(2)
      
            # In Robigo System, select Robigo Mines in the Nav Panel, which should 1 down (we select in the blind)
            #   The Robigo Mines position in the list is dependent on distance from current location
            #   The Speed50 above and waiting 2 seconds ensures Robigo Mines is 2 down from top
            found = self.lock_target(ap, 'robigo_mines')
            
            if found == False:
                ap.update_ap_status("No lock on Robigo Mines in Nav Panel")
                return

            ap.update_ap_status("SC to Robigo Mines")
            # SC Assist to Robigo Mines and dock
            ap.sc_assist(ap.scrReg)
            #
            # if didn't make it to Robigo Mines (at the ring), need to retry
            #"timestamp":"2022-05-08T23:49:43Z", "event":"SupercruiseExit", "Taxi":false, "Multicrew":false, "StarSystem":"Robigo", "SystemAddress":9463020987689, "Body":"Robigo 1 A Ring", "BodyID":12, "BodyType":"PlanetaryRing" }

            #This entry shows we made it to the Robigo Mines
            #{ "timestamp":"2022-05-08T23:51:43Z", "event":"SupercruiseExit", "Taxi":false, "Multicrew":false, "StarSystem":"Robigo", "SystemAddress":9463020987689, "Body":"Robigo Mines", "BodyID":64, "BodyType":"Station" }
            
            # if we get these then we got mission complete and made it to Sirius Atmos, if not we are short
            #  "event":"MissionRedirected", "NewDestinationStation":"Robigo Mines", "NewDestinationSystem":"Robigo", "OldDestinationStation":"", "OldDestinationSystem":"Sothis" }

            # if didn't make it to Sirius Atmos, go back into SC
            #{ "timestamp":"2022-05-08T22:01:27Z", "event":"SupercruiseExit", "Taxi":false, "Multicrew":false, "StarSystem":"Sothis", "SystemAddress":3137146456387, "Body":"Sothis A 5", "BodyID":14, "BodyType":"Planet" }
                        


# --------------------------------------------------------
'''
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

'''