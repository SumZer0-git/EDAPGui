See [ChangeLog](/ChangeLog.md) for latest updates.<br>
Join discord if need support or wish to provide inputs on new features:  https://discord.gg/HCgkfSc
<br>

# ED Autopilot Main Features
This Elite Dangerous (ED) Autopilot supports the following main features:
## FSD Route assist
For the FSD Route Assist, you select your destination in the GalaxyMap and then enable this assistant and it will perform all the jumps to get you to your destination, AFK.  Furthermore while
executing route assistance it will perform detailed system scanning (honk) when jumping into a system and optionally perform FSS scanning
to determine if Earth, Water, or Ammonia type world is present.
## Supercruise assist
The supercruise (SC) assistant (and not using ED's SC Assist which takes up a slot, for a piece of software?) 
will keep you on target and when "TO DISENGAGE" is presented and will autodrop out of SC and perform autodocking with the targeted Station. <br>
## Waypoint assist
With Waypoint Assist you define the route in a file and this assist will jump to those waypoints.  If a Station is defined to dock at, the assistant will transition to SC Assist and
dock with the station.  A early version of a trading capability is also included.<br>
Additional information can be found [here](docs/Waypoint.md).
## Robigo Mines assist
The Robigo Assist performs the Robigo Mines passenger mission loop which includes mission selection, mission completetion, and the full loop to Sirius Atmospherics.<br>
Additional information can be found [here](docs/Robigo.md). 
## AFK Combat escape assist
## Single Waypoint assist
Note: Currently available on the debug tab.

With Single Waypoint Assist you define the target system in the text box (paste from Inara/Spansh etc.) and click the checkbox to plot a route and jump to that system.<br>

# Additional Features
## Voice
If Voice enabled, the autopilot will inform you of its actions.

## TCE (Trade Computer Extension) Integration
Basic integration with TCE. The current TCE destination may be loaded as a Single Waypoint Assist target with the Load TCE Destination button on the Debug tab. 
Refer to [TCE on Frontiers Forums](https://forums.frontier.co.uk/threads/trade-computer-extension-mk-ii.223056/) for info on TCE.

This autopilot uses Computer Vision (grabs screens and performs template matching) and issues keystrokes.  It does not perform any runtime modifications 
of Elite Dangerous, it is an external-ED construct (similar to us commanders) 

  ```
  ./docs
  * Calibration.md for details on how to calibrate EDAPGui for your system if required 
  * Waypoint.md for details on how to generate a waypoint file 
  * RollPitchYaw.md for details on how to tune the Pitch, Roll, Yaw values
  * Robgio.md for details on the Robigo Mines loop
  ```

Note: this autopilot is based on https://github.com/skai2/EDAutopilot , some of the routines were used and turned into classes and tweaks were done on sequences
 and how image matching was performed.   Kudo's to skai2mail@gmail.com
 
Also Note: This repository is provided for educational purposes as a in depth programming example of interacting with file based data, computer vision processing, user feedback via voice, win32 integration using python, threading interaction, and python classes.  

# Limitations:
* Will only work with Windows (not Linux)
* Default HUD colors must be used, if you changed those colors, this autopilot will not work
* Borderless Elite Dangerous (ED) configuration required,  Windowed does not work due to how the screen is grabbed
* Screen Resolution/scale X, Y:  The templates were captured on a 3440x1440 resolution/game configuration.  These need to be scaled
  for different resolutions.  The _config-resolution.json_ file captures these resolutions with the corresponding ScaleX, Y values.  If a resolution is not defined
  for your monitor the code will attempt to divide /3440  and /1440 to get the scale factor (not likely to be correct)
  ```
  * See docs/Calibration.md for details on how to calibrate EDAPGui for your system *
  ```
  * Field of View (Graphics->Display) setting plays here.  I run about 10-15% on the slider scale.  If you have a large FOV then the 
    template images will likely be too large
* Focus: ED must have focus when running, so you can't do other things on other windows if AP is active.
           If you change focus, then keyboard events will be sent to the focused window, can mess with the 
           window
* Control Rates: Must provide the roll, pitch, yaw rates for your ship. See HOWTO-RollPitchYaw.md, start with values from Outfitting for your ship 
* Autodocking: For the AP to recongize the "TO DISENGAGE"  so it will not matter what key you have this mapped to. 
* Routing: If using Economical Route setting, then may run into problems in jumping.  With Economical, the Stars may not be on the "other-side" of the 
  Sun as with Fastest routing.
  As such, when rolling toward the Target, the Sun may fade the console making Compass matching difficult.  Need to think through this one more.  The Sun shining on the 
  console kills the matching.  You can see that if you enable CV View
* The Left Panel (Navigation) must be on the Navigation tab as the script assumes so.  It will be reset after a FSD jump back to Nav,
  but if in SC Assist, need to ensure it is configured there to support docking request
* "Advanced Autodocking" module must be outfitted on ship to support autodock 
* The ELW Scanner may have issues for you, the screen region (defined in Screen_Region.py) isolates the region to where Earth, Water, and Ammonia
  signal would be present.  If using different resolution from 3440x1440 then this region will need to be adjusted for your resolution for
  proper detection
* Must have required keybinding set for proper autopilot behavior.  See autopilot.log for any Warnings on missing key bindings
* If you jump into a system with 2 suns next to each other, will likely over heat and drop from Supercruise.
* Have seen a few cases where after doing refueling, depending on ship acceleration, we don't get away from Sun far enough before engaging FSD
  and can over heat

# Installation
_Requires **python 3** and **git**_

_Python 3.11 is the recommended version of Python. Python 3.9 or 3.10 may also be used._
If you don't have Python installed, here is a link to [Python 3.11 installer](https://www.python.org/downloads/release/python-3110/). Scroll to the bottom and select the installer with description **Recommended**.

1. Clone this repository
```sh
> git clone https://github.com/sumzer0-git/EDAPGui
```
2. Install requirements
```sh
> cd EDAPGui
> pip install -r requirements.txt
```
3. Run script
```sh
> python EDAPGui.py
OR you may have to run
> python3 EDAPGui.py
if you have both python 2 and 3 installed.
```

If you encounter any issues during pip install, try running:
> python -m pip install -r requirements.txt
instead of > pip install -r requirements.txt

The following error may occur:
> AttributeError: '_thread._local' object has no attribute 'srcdc'

The error is usually as a result of mss incompatibility. Try pip install mss==8.0.3 or pip install mss==8.0.3.

# Running ED_AP
* With Elite Dangerous (ED) running, start ED_AP:
    * By double clicking start_ed_ap.bat in Windows Explorer (preferred method).
    * By typing 'python EDAPGui.py' in a console window.
    * By running EDAPGui.py directly in a Python supporting IDE.
* The ED_AP Gui should appear and there may be messages in the log warning of issues to be fixed. Refer to the information on this page how to resolve those issues.

# Getting Started
Once ED_AP is running there are few steps to complete the first time ED AP is run. These will help avoid common issues.
1. Perform screen calibration, detailed [here](docs/Calibration.md). This will configure ED_AP for your screen resolution. Many issues can be avoided with correct calibration.
2. Check and if necessary, change keybinding options, detailed below. Pay special attention that the Ins, Home, End and Pg Up are not used by ED as these are used by EDAP.
3. Note: the autopilot.log file will capture any required keybindings that are not set.
4. Select the correct ship file matching the ship you are flying, this will configure the pitch, roll and yaw rates to match. Depending on the ship, you may need to tune the values for best response a detailed [here](docs/RollPitchYaw.md).
5. Perform an in-system test:
    * In ED, use Left Panel to select a local target.
    * In the autopilot enable SC Assist or hit the 'Ins' key.
    * When a assist starts it will set focus to the Elite Dangerous window.
    * Ship will undock if docked, jump to SC, maneuver to the target and upon arriving at the target, will attempt to dock if it is a station.
    * Any flight issues, check ship tuning.
6. Perform an out-of-system test:
   * In ED, use Galaxy Map select a target system.
   * In the autopilot enable FSD Assist or hit the 'Home' key.
   * When a assist starts it will set focus to the Elite Dangerous window.
   * Ship will undock if docked, jump to SC, maneuver to the target, perform an FSD jump. Upon arrival in the system, it will manuever aroung the star, fuel scoop as necessary and either stop if no in system target is selected, or attempt to fly to the target and  attempt to dock if it is a station.
   * Any flight issues, check ship tuning.


# Required Keybindings
The following keybindings are required by AP, so make sure a key is assigned to each by going into the Elite Dangerous options and assigning a key. After changing keybindings run AP again for the chagnes to be read. An error will appear if any of the keybindings are missing in Elite Dangerous.

| Binding               | Name                     | Location under OPTIONS > CONTROLS            |
|-----------------------|--------------------------|----------------------------------------------|
| UI_Up                 | UI PANEL UP              | GENERAL CONTROLS > INTERFACE MODE            |
| UI_Down               | UI PANEL DOWN            | GENERAL CONTROLS > INTERFACE MODE            |
| UI_Left               | UI PANEL LEFT            | GENERAL CONTROLS > INTERFACE MODE            |
| UI_Right              | UI PANEL RIGHT           | GENERAL CONTROLS > INTERFACE MODE            |
| UI_Select             | UI PANEL SELECT          | GENERAL CONTROLS > INTERFACE MODE            |
| UI_Back               | UI Back                  | GENERAL CONTROLS > INTERFACE MODE            |
| CycleNextPanel        | NEXT PANEL TAB           | GENERAL CONTROLS > INTERFACE MODE            |
|                       |                          |                                              |
| MouseReset            | RESET MOUSE              | SHIP CONTROLS > MOUSE CONTROLS               |
|                       |                          |                                              |
| YawLeftButton         | YAW LEFT                 | SHIP CONTROLS > FLIGHT ROTATION              |
| YawRightButton        | YAW RIGHT                | SHIP CONTROLS > FLIGHT ROTATION              |
| RollLeftButton        | ROLL LEFT                | SHIP CONTROLS > FLIGHT ROTATION              |
| RollRightButton       | ROLL RIGHT               | SHIP CONTROLS > FLIGHT ROTATION              |
| PitchUpButton         | PITCH UP                 | SHIP CONTROLS > FLIGHT ROTATION              |
| PitchDownButton       | PITCH DOWN               | SHIP CONTROLS > FLIGHT ROTATION              |
|                       |                          |                                              |
| ThrustUpButton        | THRUST UP                | SHIP CONTROLS > FLIGHT THRUST                |
|                       |                          |                                              |
| SetSpeedZero          | SET SPEED TO 0%          | SHIP CONTROLS > FLIGHT THROTTLE              |
| SetSpeed50            | SET SPEED TO 50%         | SHIP CONTROLS > FLIGHT THROTTLE              |
| SetSpeed100           | SET SPEED TO 100%        | SHIP CONTROLS > FLIGHT THROTTLE              |
|                       |                          |                                              |
| UseBoostJuice         | ENGINE BOOST             | SHIP CONTROLS > FLIGHT MISCELLANEOUS         |
| HyperSuperCombination | TOGGLE FRAME SHIFT DRIVE | SHIP CONTROLS > FLIGHT MISCELLANEOUS         |
| Supercruise           | SUPERCRUISE              | SHIP CONTROLS > FLIGHT MISCELLANEOUS         |
|                       |                          |                                              |
| SelectTarget          | SELECT TARGET AHEAD      | SHIP CONTROLS > TARGETING                    |
|                       |                          |                                              |
| PrimaryFire           | PRIMARY FIRE             | SHIP CONTROLS > WEAPONS                      |
| SecondaryFire         | SECONDARY FIRE           | SHIP CONTROLS > WEAPONS                      |
| DeployHardpointToggle | DEPLOY HARDPOINTS        | SHIP CONTROLS > WEAPONS                      |
|                       |                          |                                              |
| DeployHeatSink        | DEPLOY HEATSINK          | SHIP CONTROLS > COOLING                      |
|                       |                          |                                              |
| IncreaseEnginesPower  | DIVERT POWER TO ENGINES  | SHIP CONTROLS > MISCELLANEOUS                |
| IncreaseWeaponsPower  | DIVERT POWER TO WEAPONS  | SHIP CONTROLS > MISCELLANEOUS                |
| IncreaseSystemsPower  | DIVERT POWER TO SYSTEMS  | SHIP CONTROLS > MISCELLANEOUS                |
| LandingGearToggle     | LANDING GEAR             | SHIP CONTROLS > MISCELLANEOUS                |
|                       |                          |                                              |
| UIFocus               | UI FOCUS                 | SHIP CONTROLS > MODE SWITCHES                |
| GalaxyMapOpen         | OPEN GALAXY MAP          | SHIP CONTROLS > MODE SWITCHES                |
| SystemMapOpen         | OPEN SYSTEM MAP          | SHIP CONTROLS > MODE SWITCHES                |
| ExplorationFSSEnter   | ENTER FSS MODE           | SHIP CONTROLS > MODE SWITCHES                |
|                       |                          |                                              |
| HeadLookReset         | RESET HEADLOOK           | SHIP CONTROLS > HEADLOOK MODE                |
|                       |                          |                                              |
| ExplorationFSSQuit    | LEAVE FSS                | SHIP CONTROLS > FULL SPECTRUM SYSTEM SCANNER |



# Autopilot Options:
* FSD Route Assist: will execute your route.  At each jump the sequence will perform some fuel scooping, however, if 
    fuel level goes down below a threshold  the sequence will stop at the Star until refueling is complete.  
    If refueling doesn't complete after 35 seconds it will abort and continue to next route point.  If fuel goes below 
    10% (configurable), the route assist will terminate
* Supercruise Assist: will keep your ship pointed to target, you target can only be a station for
    the autodocking to work.  If a settlement is targetted or target is obscured you will end up being kicked out of SC 
    via "Dropped Too Close" or "Dropping from Orbital Cruise" (however, no damage to ship), throttle will be set to
    Zero and exit SC Assist.  Otherwise, when the 'TO DISENGAGE' appears the SC Assist will drop you out of SC
    and attempt request docking (after traveling closer to the Station), if docking granted it will.    
    put throttle to zero and the autodocking computer will take over. Once docked it will auto-refuel and go into StarPort Services.
    Note: while in SC, a interdictor response is included.   Also, as approaching the station, if it shows the Station is occluded
    this assistant will navigate around the planet and proceed with docking
* Waypoint Assist: When selected, will prompt for the waypoint file.  The waypoint file contains System names that will be 
    entered into Galaxy Map and route plotted.  If the last entry in the waypoint file is "REPEAT", it will start from the beginning.
    If the waypoint file entry has an associated Station/StationCoord entry, the assistant will route a course to that station
    upon entering that system.  The assistant will then autodock, refuel and repair.  If a trading sequence is define, it will then
    execute that trade.  See HOWTO-Waypoint.md
* Robigo Assist:  Performs the Robigo Mines Passenger missions.  See Robigo.md under the docs folder
* AFK Combat Assist: used with a AFK Combat ship in a Rez Zone.  It will detect if shields have
    dropped and if so, will boost away and go into supercruise for ~10sec... then drop, put pips to
    system and weapons and deploy fighter, then terminate.  While in the Rez Zone, if your fighter has
    been destroyed it will deploy another figher (assumes you have two bays)
* ELW Scanner: will perform FSS scans while FSD Assist is traveling between stars.  If the FSS
    shows a signal in the region of Earth, Water or Ammonia type worlds, it will announce that discovery
    and log it into elw.txt file.  Note: it does not do the FSS scan, you would need to terminate FSD Assist
    and manually perform the detailed FSS scan to get credit.  Or come back later to the elw.txt file
    and go to those systems to perform additional detailed scanning. The elw.txt file looks like:<br>
      _Oochoss BL-M d8-3  %(dot,sig):   0.39,   0.79 Ammonia date: 2022-01-22 11:17:51.338134<br>
       Slegi BG-E c28-2  %(dot,sig):   0.36,   0.75 Water date: 2022-01-22 11:55:30.714843<br>
       Slegi TM-L c24-4  %(dot,sig):   0.31,   0.85 Earth date: 2022-01-22 12:04:47.527793<br>_
* Calibrate: will iterate through a set of scaling values getting the best match for your system.  See HOWTO-Calibrate.md
* Cap Mouse X, Y:  this will provide the StationCoord value of the Station in the SystemMap.  Selecting this button
    and then clicking on the Station in the SystemMap will return the x,y value that can be pasted in the waypoints file
* SunPitchUp+Time field are for ship that tend to overheat. Providing 1-2 more seconds of Pitch up when avoiding the Sun
    will overcome this problem.  This will be Ship unique and this value will be saved along with the Roll, Pitch, Yaw values 
* Menu
  * Open : read in a file with roll, pitch, yaw values for ship
  * Save : save the roll,pitch,yaw, and sunpitchup time values to a files
  * Enable Voice : Turns on/off voice
  * Enable CV View: Turn on/off debug images showing the image matching as it happens.  The numbers displayed
    indicate the % matched with the criteria for matching. Example:  0.55 > 0.5  means 55% match and the criteria
    is that it has to be > 50%, so in this case the match is true
    
## Hot Keys (configurable)
* Home - Start FSD Assist
* Ins  - Start SC Assist
* Pg Up - Start Robigo Assist
* End  - Terminate any running assistants

Hot keys are now configurable in the config-AP.json file, so you can remap them. Be sure not to use any keys you have mapped in ED.  You can find the key names here:
https://pythonhosted.org/pynput/keyboard.html

## Config File: config-AP.json
The following settings from the AP.json file are **not** available through the GUI and must be changed directly within AP.json:
  ```py
    "Robigo_Single_Loop": False,   # True means only 1 loop will execute and then terminate upon docking, will not perform mission processing
    "EnableRandomness": False,     # add some additional random sleep times to avoid AP detection (0-3sec at specific locations)
    "OverlayTextFont": "Eurostyle", 
    "OverlayGraphicEnable": False, # not implemented yet
    "DiscordWebhook": False,       # discord not implemented yet
    "DiscordWebhookURL": "",
    "DiscordUserID": "",
    "VoiceID": 1,                  # my Windows only have 3 defined (0-2)
    "FCDepartureTime": 30.0,       # When leaving a Fleet Carrier, this is the amount of time in Secs to fly away before enabling SC.
    "Language": "en"               # Language for OCR checks (i.e. 'en', 'fr', 'de')
```
                                                              
## Elite Dangerous, Role Play and Autopilot
* I am a CMDR in the Elite Dangerous universe and I have a trusty Diamondback Explorer
* In my travels out into the black I have become frustrated with my flight computers abilities.  I don't want to stay
  up hours and hours manually performing Sun avoidance just to jump to the next system.  
* In a nutshell, Lakon Spaceways lacks vision.  Heck, they provide Autopilot for docking, undocking, and Supercruise but can't provide
  a simple route AP?   Geezzz
* Well, I have my trusty personal quantum-based computing device (roughly 10TeraHz CPU, 15 Petabyte RAM), which is the size of a credit-card, that has vision processing capability, has ability to inteface with my Diamondback Explorer Flight Computer 
  so I'm going to develop my own autopilot.   This falls under the "consumers right to enhance", signed into law in the year 3301 and ratified by all the Galatic powers
* So CMDRs, lets enhance our ships so we can get some sleep and do real work as opposed to hours of maneuvering around Suns

## WARNING:

Use at your own risk.  Have performed over 2000 FSD jumps with this autopilot and have aborted the FSD Assist
about 6 times due to jumping into a system that had 2 suns next to each other and pretty much the ship overheated
and dropped out of supercruise.   The ship did not get destroyed but had to use a heat sink to get out of the
situation

# Email Contact

sumzer0@yahoo.com


# Screen Shots
![Alt text](screen/screen_cap_main.png?raw=true "Main Tab")
![Alt text](screen/screen_cap_settings.png?raw=true "Settings Tab")
![Alt text](screen/screen_cap_debug.png?raw=true "Debug Tab")
                                                               
