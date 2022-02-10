# ED Autopilot - Gui
This Autopilot supports route assistance, supercruise assistance, and AFK Combat escape assistance.  Furthermore while
executing route assistance it will perform detailed system scanning (honk) when jumping into a system and optionally perform FSS scanning
to determine if Earth, Water, or Ammonia type world is present.   If enable Voice, the autopilot will inform you of the actions it is
taking

Note: much of the autopilot code was taking from https://github.com/skai2/EDAutopilot , many of the routines were turned into classes and tweaks were done on sequences
 and how image matching was performed.   Kudo's to skai2mail@gmail.com
 
Also Note: This repository is provided for educational purposes as a in depth programming example of interacting with file based data, computer vision processing, user feedback via voice, win32 integration using python, threading interaction, and python classes.  

# Constraints:
* Will only work with Windows (not Linux)
* Borderless Elite Dangerous (ED) configuration required,  Windowed does not work due to how the screen is grabbed
* Screen Resolution that works:  3440x1440, 1920x1080, 2560x1080, resolutions that do not work: 1920x1200, 1920x1440, 2560x1440
  * To use these none working resolutions you have to change the scaleX, scaleY in Screen.py 
  * Reason: The Image Templates were generated via 3440x1440 screen, at startup the screen size
        is grabbed and the scaling factor for scaling down from 3440x1440 is calculated for the
        template images
* Focus: ED must have focus when running, so you can't do other things on other windows if AP is active.
           If you change focus, then keyboard events will be sent to the focused window, can mess with the 
           window
* Control Rates: Must provide the roll, pitch, yaw rates as defined in Outfitting for your ship, 
        you probably want to save the config.  Each ship is different.  The rates shown in Outfitting
        are for normal space, in supercriuse they will be a little slower.
         see:  https://forums.frontier.co.uk/threads/supercruise-handling-of-ships.396845/
* Route Star:  Good idea to restrict your route Stars to 'KGB FOAM' type stars for scooping 
* Detailed Scanner must be mapped to firebutton 1 
* Must install needed packages:  pip install -r requirements.txt
* "Advanced Autodocking" module must be outfitted on ship
* The ELW Scanner may have issues for you, the screen region (defined in Screen_Region.py) isolates the region to where Earth, Water, and Ammonia
  signal would be present.  If using different resolution from 3440x1440 then this region will need to be adjust for your resolution for
  proper detection
* Must have required keybinding set for proper autopilot behavior.  See autopilot.log for any Warnings on missing key bindings
* See https://github.com/skai2/EDAutopilot for other constraints that probably apply

# Hot Keys:
* Home - Start FSD Assist
* Ins  - Start SC Assist
* End  - Terminate any running assistants

# How to run:
* With Elite Dangerous (ED) running, start EDAPgui.py
  * python EDAPgui.py     
* In ED, Use Left Panel to select your route
* Go to supercruise and go ahead and line up with Target
* In the autopilot enable FSD Assist or hit the 'Home' key.  When a assist starts it will set focus
      to the Elite Dangerous window.  
Note: the autopilot.log file will capture any required keybindings that are not set
   
# Autopilot Options:
* FSD Route Assist: will execute your route.  It is possible to jump into a system that has two stars
    next to each other.  You can overheat in this case and be dropped out of Assist.  At each jump the 
    sequence will perform some fuel scooping, however, if fuel level goes down below a hardcoded threshold
    the sequence will stop at the star until refueling is complete.  If refueling doesn't complete after
    35 seconds it will abort and continue to next route point.  If fuel goes below 35%, the route assist
    will terminate
* Supercruise Assist: will keep your ship pointed to target, you target can only be a station for
    the autodocking to work.  If a settlement or obscured you will end up being kicked out of SC and
    probably have some damage.   When the SC Disenage appears the SC Assist will drop you out of SC
    and attempt request docking (after traveling closer to the Station), if docking granted it will
    put throttle to zero and the autodocking computer will take over
* ELW Scanner: will perform FSS scans while FSD Assist is traveling between starts.  If the FSS
    shows a signal in the region of Earth, Water or Ammonia type worlds, it will announce that discovery
    and log it into elw.txt file.  Note it does not do the scan, you would need to terminate FSD Assist
    and manually perform the detailed FSS scan to get credit.  Or come back later to the elw.txt file
    and go to those systems to perform additional detailed scanning. 
* AFK Combat Assist: used with a AFK Combat ship in a Rez Zone.  It will detect if shields have
    dropped and if so, will boost away and go into supercruise for ~10sec... then drop, put pips to
    system and weapons and deploy fighter, then terminate.  While in the Rez Zone, if your fighter has
    been destroyed it will deploy another figher (assumes you have two bays)
* Menu
  * Open : read in a file with roll, pitch, yaw values for ship
  * Save : save the roll,pitch,yaw values to a files
  * Enable Voice : Turns on/off voice
  * Enable CV View: Turn on/off debug images showing the image matching as it happens.  The numbers displayed
    indicate the % matched with the criteria for matching. Example:  0.55 > 0.5  means 55% match and the criteria
    is that it has to be > 50%, so in this case the match is true
    
# Enhancement ideas
* The Overlay.py is cool, would be nice to show the matched image on the actual ED screen
* Handle ED in windowed mode
* Handle other screen resolutions
* FSS/ELW screen region needs to be able to handle diff screen resolutions


## Setup:
_Requires **python 3** and **git**_
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

If you are going to run dist/EDAPGui.exe, you need to have the template directory so your path would be ./templates/<file>


## WARNING:

Use at your own risk.  Have performed over 2000 FSD jumps with this autopilot and have aborted the FSD Assist
about 6 times due to jumping into a system that had 2 suns next to each out and pretty much the ship overheated
and dropped out of supercruise.   The ship did not get destroyed but had to use a heat sink to get out of the
situation

# Email Contact

sumzer0@yahoo.com


# Screen Shots
![Alt text](screen/screen_cap.png?raw=true "Screen")
