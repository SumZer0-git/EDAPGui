from time import sleep
from EDlogger import logger
import json
from pyautogui import typewrite, keyUp, keyDown
from MousePt import MousePoint
from pathlib import Path



"""
File: EDWayPoint.py    

Description:
   Class will load file called waypoints.json which contains a list of System name to jump to.
   Provides methods to select a waypoint pass into it.  

Author: sumzer0@yahoo.com
"""

class EDWayPoint:
    def __init__(self, is_odyssey=True):
        
        self.is_odyssey = is_odyssey
        self.filename = './waypoints.json'

        self.waypoints = {}
        #  { "Ninabin": {"DockWithTarget": false, "TradeSeq": None, "Completed": false} }
        # for i, key in enumerate(self.waypoints):
        # self.waypoints[target]['DockWithTarget'] == True ... then go into SC Assist
        # self.waypoints[target]['Completed'] == True
        # if docked and self.waypoints[target]['Completed'] == False
        #    execute_seq(self.waypoints[target]['TradeSeq'])
 
        ss = self.read_waypoints()

        # if we read it then point to it, otherwise use the default table above
        if ss is not None:
            self.waypoints = ss
            logger.debug("EDWayPoint: read json:"+str(ss))    
            
        self.num_waypoints = len(self.waypoints)
     
        #print("waypoints: "+str(self.waypoints))
        self.step = 0
        
        self.mouse = MousePoint()
     
     
    def load_waypoint_file(self, filename=None):
        if filename == None:
            return
        
        ss = self.read_waypoints(filename)
        
        if ss is not None:
            self.waypoints = ss
            self.filename = filename
            logger.debug("EDWayPoint: read json:"+str(ss))            
        
         
    def read_waypoints(self, fileName='./waypoints/waypoints.json'):
        s = None
        try:
            with open(fileName,"r") as fp:
                s = json.load(fp)
        except  Exception as e:
            logger.warning("EDWayPoint.py read_waypoints error :" + str(e))

        return s    
       

    def write_waypoints(self, data, fileName='./waypoints/waypoints.json'):
        if data is None:
            data = self.waypoints
        try:
            with open(fileName,"w") as fp:
                json.dump(data,fp, indent=4)
        except Exception as e:
            logger.warning("EDWayPoint.py write_waypoints error:" + str(e))

    def mark_waypoint_complete(self, key):
        self.waypoints[key]['Completed'] = True
        self.write_waypoints(data=None, fileName='./waypoints/' + Path(self.filename).name)  

    def set_next_system(self, ap, target_system) -> bool:
        """ Sets the next system to jump to, or the final system to jump to.
        If the system is already selected or is selected correctly, returns True,
        otherwise False.
        """
        # Call sequence to select route
        if self.set_waypoint_target(ap, target_system, None):
            return True
        else:
            # Error setting target
            logger.warning("Error setting waypoint, breaking")
            return False

    def waypoint_next(self, ap, target_select_cb=None) -> str:
        dest_key = "REPEAT"
        
        # loop back to beginning if last record is "REPEAT"
        while dest_key == "REPEAT":                       
            for i, key in enumerate(self.waypoints):

                # skip records we already processed
                if i < self.step:  
                    continue

                # if this step is marked to skip.. i.e. completed, go to next step
                if self.waypoints[key]['Completed'] == True:
                    continue

                # if this entry is REPEAT, loop through all and mark them all as Completed = False
                if key == "REPEAT":
                    self.mark_all_waypoints_not_complete()             
                else: 
                    # Call sequence to select route
                    if self.set_waypoint_target(ap, key, target_select_cb) == False:
                        # Error setting target
                        logger.warning("Error setting waypoint, breaking")
                    self.step = i                    
                dest_key = key

                break
            else:
                dest_key = ""   # End of list, return empty string
        print("test: " + dest_key)     
        return dest_key

    def mark_all_waypoints_not_complete(self):
        for j, tkey in enumerate(self.waypoints):  
            self.waypoints[tkey]['Completed'] = False   
            self.step = 0 
        self.write_waypoints(data=None, fileName='./waypoints/' + Path(self.filename).name) 
    
    def is_station_targeted(self, dest) -> bool:
        return self.waypoints[dest]['DockWithStation']
    
    
    def set_station_target(self, ap, dest):
        (x, y) = self.waypoints[dest]['StationCoord']

        # check if StationBookmark exists to get the transition compatibility with old waypoint lists
        if "StationBookmark" in self.waypoints[dest]:
            bookmark = self.waypoints[dest]['StationBookmark']
        else:
            bookmark = -1

        # Check if this is a normal station
        if self.waypoints[dest]['DockWithStation'] != "System Colonisation Ship":
            ap.keys.send('SystemMapOpen')
            sleep(3.5)
            if self.is_odyssey and bookmark != -1:
                ap.keys.send('UI_Left')
                sleep(1)
                ap.keys.send('UI_Select')
                sleep(.5)
                ap.keys.send('UI_Right')
                sleep(.5)
                ap.keys.send('UI_Down', repeat=2)
                sleep(.5)
                ap.keys.send('UI_Right')
                sleep(.5)
                ap.keys.send('UI_Down', repeat=bookmark)
                sleep(.5)
                ap.keys.send('UI_Select', hold=4.0)
            else:
                self.mouse.do_click(x, y)
                self.mouse.do_click(x, y, 1.25)

                # for horizons we need to select it
                if self.is_odyssey == False:
                    ap.keys.send('UI_Select')

            ap.keys.send('SystemMapOpen')
            sleep(0.5)

        elif self.waypoints[dest]['DockWithStation'] == "System Colonisation Ship":
            # Colonisation ships are bookmarked on the galaxy map WHY!?!?!?
            ap.keys.send('GalaxyMapOpen')
            sleep(2)
            if self.is_odyssey and bookmark != -1:
                ap.keys.send('UI_Left')  # Go to BOOKMARKS
                sleep(1)
                ap.keys.send('UI_Select')  # Select BOOKMARKS
                sleep(.5)
                ap.keys.send('UI_Right')  # Go to FAVORITES
                sleep(.5)
                ap.keys.send('UI_Down')  # Go to SYSTEMS
                sleep(.5)
                ap.keys.send('UI_Select')  # Select SYSTEMS
                sleep(.5)
                ap.keys.send('UI_Down', repeat=bookmark)
                sleep(.5)
                ap.keys.send('UI_Select', hold=4.0)

            ap.keys.send('GalaxyMapOpen')
            sleep(0.5)

    # Call either the Odyssey or Horizons version of the Galatic Map sequence
    def set_waypoint_target(self, ap, target_name, target_select_cb=None) -> bool:
        # No waypoints defined, then return False
        if self.waypoints == None:
            return False

        if self.is_odyssey != True:
            return self.set_waypoint_target_horizons(ap, target_name, target_select_cb)
        else:
            return self.set_waypoint_target_odyssey(ap, target_name, target_select_cb)
              
            
    #
    # This sequence for the Horizons
    #      
    def set_waypoint_target_horizons(self, ap, target_name, target_select_cb=None) -> bool:
    
        ap.keys.send('GalaxyMapOpen')
        sleep(2)
        ap.keys.send('CycleNextPanel')
        sleep(1)
        ap.keys.send('UI_Select')
        sleep(2)
              
        typewrite(target_name, interval=0.25)
        sleep(1)         
  
        # send enter key
        ap.keys.send_key('Down', 28)
        sleep(0.05)
        ap.keys.send_key('Up', 28)
        
        sleep(7)
        ap.keys.send('UI_Right')
        sleep(1)
        ap.keys.send('UI_Select')   
        
        # if got passed through the ship() object, lets call it to see if a target has been
        # selected yet.. otherwise we wait.  If long route, it may take a few seconds      
        if target_select_cb != None:
            while not target_select_cb()['target']:
                sleep(1)
                
        ap.keys.send('GalaxyMapOpen')
        sleep(2)
        return True

  
    #
    # This sequence for the Odyssey
 
    def set_waypoint_target_odyssey(self, ap, target_name, target_select_cb=None) -> bool:

        ap.keys.send('GalaxyMapOpen')
        sleep(2)

        # navigate to and select: search field
        ap.keys.send('UI_Up')
        sleep(0.05)
        ap.keys.send('UI_Select')
        sleep(0.05)

        #print("Target:"+target_name)       
        # type in the System name
        typewrite(target_name, interval=0.25)
        sleep(0.05)

        # send enter key (removes focus out of input field)
        ap.keys.send_key('Down', 28)  # 28=ENTER
        sleep(0.05)
        ap.keys.send_key('Up', 28)  # 28=ENTER
        sleep(0.05)

        # navigate to and select: search button
        ap.keys.send('UI_Right')
        sleep(0.05)
        ap.keys.send('UI_Select')

        # zoom camera which puts focus back on the map
        ap.keys.send('CamZoomIn')
        sleep(0.05)

        # plot route. Not that once the system has been selected, as shown in the info panel
        # and the gal map has focus, there is no need to wait for the map to bring the system
        # to the center screen, the system can be selected while the map is moving.
        ap.keys.send('UI_Select', hold=0.75)

        sleep(0.05)

        # if got passed through the ship() object, lets call it to see if a target has been
        # selected yet.. otherwise we wait.  If long route, it may take a few seconds
        if target_select_cb != None:
            while not target_select_cb()['target']:
                sleep(1)

        ap.keys.send('GalaxyMapOpen')
        
        return True

    def execute_trade(self, ap, dest):
        sell_down = self.waypoints[dest]['SellNumDown']
        buy_down = self.waypoints[dest]['BuyNumDown']  
        
        if sell_down == -1 and buy_down == -1:
            return

        # Check if a regular station/fleet carrier (not a colonisation ship)
        if self.waypoints[dest]['DockWithStation'] != "System Colonisation Ship":
            # We start off on the Main Menu in the Station
            ap.keys.send('UI_Up', repeat=3)  # make sure at the top
            ap.keys.send('UI_Down')
            ap.keys.send('UI_Select')  # Select StarPort Services

            sleep(8)   # wait for new menu to finish rendering

            ap.keys.send('UI_Down')
            ap.keys.send('UI_Select')  # Select Commodities

            sleep(2.5)

            # --------- SELL ----------
            if sell_down != -1:
                ap.keys.send('UI_Down')
                ap.keys.send('UI_Select')  # Select Sell

                sleep(1.5)   # give time to bring up, if needed
                ap.keys.send('UI_Right')   # Go to top of commodities list
                ap.keys.send('UI_Up', repeat=10)  # go up 10x in case were not on top of list
                ap.keys.send('UI_Down', repeat=sell_down)  # go down # of times user specified
                ap.keys.send('UI_Select')  # Select that commodity

                sleep(3)  # give time for popup
                ap.keys.send('UI_Up', repeat=3)  # make sure at top
                ap.keys.send('UI_Down')    # Down to the Sell button (already assume sell all)
                ap.keys.send('UI_Select')  # Select to Sell all

            # TODO: Note, if the waypoint plan has sell_down != -1, then we are assuming we have
            # cargo to sell, if not we are in limbo here as the Sell button not selectable
            #  Could look at the ship_status['MarketSel'] == True (to be added), to see that we sold
            #  and if not, go down 1 and select cancel

            # --------- BUY ----------
            if buy_down != -1:
                sleep(3)  # give time to popdown
                ap.keys.send('UI_Left')    # back to left menu
                sleep(0.5)
                ap.keys.send('UI_Up', repeat=2)      # go up to Buy
                ap.keys.send('UI_Select')  # Select Buy

                sleep(1.5) # give time to bring up list
                ap.keys.send('UI_Right')   # Go to top of commodities list
                ap.keys.send('UI_Up', repeat=sell_down+5)  # go up sell_down times in case were not on top of list (+5 for pad)
                ap.keys.send('UI_Down', repeat=buy_down)  # go down # of times user specified
                ap.keys.send('UI_Select')  # Select that commodity

                sleep(2) # give time to popup
                ap.keys.send('UI_Up', repeat=3)      # go up to quantity to buy (may not default to this)
                ap.keys.send('UI_Right', hold=4.0)   # Hold down Right key to buy will fill cargo
                ap.keys.send('UI_Down')
                ap.keys.send('UI_Select')  # Select Buy

            sleep(1.5)  # give time to popdown
            ap.keys.send('UI_Left')    # back to left menu
            ap.keys.send('UI_Down', repeat=8)    # go down 4x to highlight Exit
            ap.keys.send('UI_Select')  # Select Exit, back to StartPort Menu
            sleep(1) # give time to get back to menu
            if self.is_odyssey == True:
                ap.keys.send('UI_Down', repeat=4)    # go down 4x to highlight Exit

            ap.keys.send('UI_Select')  # Select Exit, back to top menu
            sleep(2)  # give time to popdown menu

        elif self.waypoints[dest]['DockWithStation'] == "System Colonisation Ship":
            # We start off on the Main Menu in the Station
            ap.keys.send('UI_Up', repeat=3)  # make sure at the top
            ap.keys.send('UI_Down')
            ap.keys.send('UI_Select')  # Select StarPort Services

            sleep(5)  # wait for new menu to finish rendering

            # --------- SELL ----------
            if sell_down != -1:
                ap.keys.send('UI_Left', repeat=3)  # Go to table
                ap.keys.send('UI_Down', hold=2)  # Go to bottom
                ap.keys.send('UI_Up')  # Select RESET/CONFIRM TRANSFER/TRANSFER ALL
                ap.keys.send('UI_Left', repeat=2)  # Go to RESET
                ap.keys.send('UI_Right', repeat=2)  # Go to TRANSFER ALL
                ap.keys.send('UI_Select')  # Select TRANSFER ALL
                sleep(0.5)

                ap.keys.send('UI_Left')  # Go to CONFIRM TRANSFER
                ap.keys.send('UI_Select')  # Select CONFIRM TRANSFER
                sleep(2)

                ap.keys.send('UI_Down')  # Go to EXIT
                ap.keys.send('UI_Select')  # Select EXIT

                sleep(2)  # give time to popdown menu


# this import the temp class needed for unit testing
"""
from EDKeys import *       
class temp:
    def __init__(self):
        self.keys = EDKeys()
"""

def main():
    
    #keys   = temp()
    wp  = EDWayPoint(True)  # False = Horizons
    wp.step = 0   #start at first waypoint
        
    sleep(3)
    

    
    #dest = 'Enayex'
    #print(dest)
    
    #print("In waypoint_assist, at:"+str(dest))

    
    # already in doc config, test the trade
    #wp.execute_trade(keys, dest)    

    # Set the Route for the waypoint^#
    dest = wp.waypoint_next(ap=None) 

    while dest != "":

      #  print("Doing: "+str(dest))
      #  print(wp.waypoints[dest])
       # print("Dock w/station: "+  str(wp.is_station_targeted(dest)))
        
        #wp.set_station_target(None, dest)
        
        # Mark this waypoint as complated
        #wp.mark_waypoint_complete(dest)
        
        # set target to next waypoint and loop)::@
        dest = wp.waypoint_next(ap=None) 




if __name__ == "__main__":
    main()
