
from time import sleep

import keyboard
import win32gui

from EDJournal import *
from EDKeys import *
from EDlogger import logger
from Voice import *

"""
Description:  AFK Combat in Rez site (see Type 10 AFK videos).
  This script will monitor shields (from Journal file), if shields are lost (ShieldsUp == False) then
  boost and supercruise away, after a bit, drop from supercruise, pips to System/Weapons and deploy fighter
  This script will also monitor if a deployed Fighter is destroyed, if so it will deploy another fighter,
  this requires another fighter bay with a fighter ready (could modify to wait for fighter rebuild)

Required State:
  - Point away from Rez sight (so when boost away can get out of mass lock)

Author: sumzer0@yahoo.com
"""

"""
TODO: consider the following enhancements
  - If a key is not mapped need to list which are needed and exit
  - Need key for commading fighter to 'attack at will' or defend
  - After retreat complete, could go into while loop looking for "UnderAttack" or 
    simply go back into shields down logic again.  Would have to wait until shields are up
  - 
    
"""


class AFK_Combat:

    def __init__(self, k, journal, v=None):
        self.k = k
        self.jn = journal
        self.voice = v 
        self.fighter_bay = 2     
    
    def check_shields_up(self):
        return self.jn.ship_state()['shieldsup'] 
        
    def check_fighter_destroyed(self):
        des = self.jn.ship_state()['fighter_destroyed']
        self.jn.ship_state()['fighter_destroyed'] = False    # reset it to false after we read it
        return des

    def evade(self):
        # boost and prep for supercruise
        if self.voice != None:
            self.voice.say("Boosting, reconfiguring")
        self.k.send('SetSpeed100', repeat=2)
        self.k.send('DeployHardpointToggle')
        self.k.send('IncreaseEnginesPower', repeat=4)
        self.k.send('UseBoostJuice') 
        sleep(2)

        # while the ship is not in supercruise: booster and attempt supercruise
        # could be mass locked for a bit
        while self.jn.ship_state()['status'] == 'in_space':
            if self.voice != None:
                self.voice.say("Boosting, commanding supercruise")
            self.k.send('UseBoostJuice')       
            sleep(1)            
            self.k.send('HyperSuperCombination')     
            sleep(9)
            
        # in supercruise, wait a bit to get away, then throttle 0 and exit supercruise, full pips to system   
        if self.voice != None:
            self.voice.say("In supercruise, retreating from site")     

        sleep(1)
        self.k.send('SetSpeed100', repeat=2)     
        sleep(20)
        self.k.send('SetSpeedZero')
        sleep(10)
        if self.voice != None:
            self.voice.say("Exiting supercruise, all power to system and weapons")        
        self.k.send('HyperSuperCombination', repeat=2)
        sleep(7)
        self.k.send('IncreaseSystemsPower', repeat=3)  
        self.k.send('IncreaseWeaponsPower', repeat=3)        
      


    def launch_fighter(self):
         # menu select figher deploy
        if self.voice != None:
            self.voice.say("Deploying fighter")         
        self.k.send('HeadLookReset')
        self.k.send('UIFocus', state=1)
        self.k.send('UI_Down')
        self.k.send('UIFocus', state=0)
        sleep(0.2)
        
        # Reset to top, go left x2, go up x3
        self.k.send('UI_Left', repeat=2)
        self.k.send('UI_Up', repeat=3)
        sleep(0.1)        

        # Down to fighter and then Right then will be over deploy button
        self.k.send('UI_Down')
        self.k.send('UI_Right')  
        sleep(0.1)
        
        # go to top fighter bay selection
        self.k.send('UI_Up')

        # toggle between fighter bays, if a fighter gets restored, that bay is busy
        # rebuilding so need to us the other one
        if self.fighter_bay == 2:
            self.k.send('UI_Down')     
            self.fighter_bay = 1 
        else:
             self.fighter_bay = 2        

        # Deploy should be highlighted, Select it
        self.k.send('UI_Select')

        # select which pilot
        self.k.send('UI_Up', repeat=4)  # ensure top entry selected
        self.k.send('UI_Down')      # go down one and select the hired pilot
        self.k.send('UI_Select')

        sleep(0.2)
        self.k.send('UI_Back')
        self.k.send('HeadLookReset')
        #
        # Command fighter to attack at will
        # self.k.send().... ??OrderAggressiveBehaviour
        self.k.send('SetSpeedZero')



"""

Uncomment this whole block below to run this standalone:  >python afk-combat.py

Hotkeys:
  Alt + q - quit program
  Alt + s - force shield down event
  Alt + f - force fighter destroy event
  Alt + d - dump the states

"""

"""Remove this line and last line at button to uncomment the blow of code below

inp = None

def key_callback(name):
    global inp
    inp = name

        
def main():
    global inp
    k = EDKeys()
    jn = EDJournal()
    v = Voice()
    v.set_on()

    afk = AFK_Combat(k, jn, v)
    v.say(" AFK Combat Assist active")

    print("Hot keys\n alt+q = Quit\n alt+s = force shield down event\n alt+f = force fighter destroy event\n alt+d = dump state\n")    
    # trap specific hotkeys
    keyboard.add_hotkey('alt+q', key_callback, args =('q'))
    keyboard.add_hotkey('alt+s', key_callback, args =('s'))
    keyboard.add_hotkey('alt+f', key_callback, args =('f'))
    keyboard.add_hotkey('alt+d', key_callback, args =('d'))
    
    while True:
        inp = None
        sleep(2)

        if inp == 'q':
            break

        if inp == 'd':
            print (jn.ship_state())       

        if afk.check_shields_up() == False or inp == 's':
            afk.set_focus_elite_window()
            v.say("Shields down, evading")
            afk.evade()
            # after supercruise the menu is reset to top
            afk.launch_fighter()  # at new location launch fighter
            break
            
        if afk.check_fighter_destroyed() == True or inp == 'f':
            afk.set_focus_elite_window()
            v.say("Fighter Destroyed, redeploying") 
            afk.launch_fighter()  # assuming two fighter bays
        
    
    v.say("Terminating AFK Combat Assist")
    sleep(1)
    v.quit()
    
            
if __name__ == "__main__":
    main()

"""