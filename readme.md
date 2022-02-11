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
* The Left Panel (Navigation) must be on the Navigation tab as the script assumes so.  It will be reset after a FSD jump back to Nav,
  but if in SC Assist, need to ensure it is configured there to support docking request
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
  * Note: the default Roll, Pitch, and Yaw rates are for my Diamondback Explorer, you need to enter the values
    for your ship, which can be found in Outfitting. 
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
    the autodocking to work.  If a settlement or target is obscured you will end up being kicked out of SC and
    probably have some damage.   When the SC Disenage appears the SC Assist will drop you out of SC
    and attempt request docking (after traveling closer to the Station), if docking granted it will
    put throttle to zero and the autodocking computer will take over
* ELW Scanner: will perform FSS scans while FSD Assist is traveling between stars.  If the FSS
    shows a signal in the region of Earth, Water or Ammonia type worlds, it will announce that discovery
    and log it into elw.txt file.  Note: it does not do the FSS scan, you would need to terminate FSD Assist
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
    
# Approach
## FSD Assist FLow
* When entering a new System, Speed to 0
* Rotate left 90 degree and perform sun aviodance by pitching up until sun just below us
  * this configuration puts the sun beneath us so we won't be suceptible to sun shining on our console making
    image matching very difficult for the Compass
* Accelerate to 100 for <some> seconds, speed to 50, fuel scooping will start
* if our fuel is below a threshold (hardcode, need to lookup) then put speed to 0
* Wait for refule complete or 35 sec elapsed
* Accel back to 100, delay some seconds while we get away from Sun
* Perform DSS on the System
* if ELW Scanner enabled, go into FSS, do image matching in specific region looking for filled circle or frequency signal present.
  if so, log wether an Earth, Water or Ammonia world based on where the frequency signal is at in the image
* Now do Nav align looking at the Compass on the console, perform roll and pitch based on Nav point in the compass
* Then perform Target align (as the target should be pretty close in front of us) 
* if reached destination system then determine, however if we still have a target to a Station, then auto-enable SC Assist
  else have not reach destination, so issue FSD and loop 
 
## SC Assist Flow
* Loop 
  * Do Target align, keeping is us a tight deadband on the target
  * Do image match checking to see if SC Disengage pops up, if so, break loop
* Accel for ~10sec... then put speed to 0 (this put us < 7.5km)
* Do Left Menu... Right twice to get to Contact and the Right to request docking
  * Do this up to 3 times, if needed
  * if docking rejected, put that info in the log
* if docking accepted, we are at speed 0 so let Docking Computer take over
* wait for up to 120 sec for dock complete... then done
*
 
# Enhancement ideas
* A lot more error trapping needs to be put into the code
  * since I do exception trapping for uncaught exception at the top, I can create a set of my own exceptions
    and depending on what exception was raised could put the vehicle in appropriate safe condition
* Saw forks on skai's repo, some good stuff.  I like the route planning (route plan in file and it parses it)
  * explore other peoples updates.  Can't push this back to skai's repo because most of this is a re-write.
    Need to put more config items in a config file to be read at startup
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

## Known Limitations
 * As described in the constraints, if you jump into a system with 2 suns next to each other, will likely over heat and drop from Supercruis
 * The target alignment goal is to perform 1 roll and 1 pitch action to align close to taget.  If you have wrong rates for your ship then you will
   overshoot or undershoot.  The algorithm attempts to align the nav point on the Y axis (north or south, depending on which is closer)
 * Have seen a few cases where after doing refueling, depending on ship acceleration, we don't get away from Sun far enough before engaging FSD
   and can over heat

## WARNING:

Use at your own risk.  Have performed over 2000 FSD jumps with this autopilot and have aborted the FSD Assist
about 6 times due to jumping into a system that had 2 suns next to each out and pretty much the ship overheated
and dropped out of supercruise.   The ship did not get destroyed but had to use a heat sink to get out of the
situation

# Email Contact

sumzer0@yahoo.com


# Screen Shots
![Alt text](screen/screen_cap.png?raw=true "Screen")
