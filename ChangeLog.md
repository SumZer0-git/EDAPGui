
2/20/2022 
Configurable Settings
  config-AP.json
    - Aded EnableRandomness flag to adjust sleep times
    - OverlayTextEnable flag to show overlay on ED, prototype
    - OverlayTextYOffset the Y location to put overlay (X hardcoded)
    - OverlayTextFontSize allows you to specify size
    - FuelScoopTimeOut how long to wait in fuel scooping before aborting
    - and others

Autopilot
  - Added Waypoint Assist  (works both in Odyssey and Horisons)
    - Jumps to Systems defined in waypoints.json (or user selected) file
      - Can dock with a station that is defined in the file also (requires X, Y of mouse to select the 
        station from the System Map, this too is a little more complex so see separate HowTo)
        - Added GUI Button "Get X, Y Mouse" to help with determining the StationCoord 
      - Once docked can perform trades (somewhat complex to setup, will need separate HowTo), Sells first
        then Buys
      - Auto undock to take you to next waypoint system
      - If last line in the waypoint file is "REPEAT", it will loop to top and do it again, forever, otherwise
        Waypoint assist terminates at the end
  - GUI, in statusline, how shows: Distance Jumped, Jumps/Total Jumps, #Refuels, Sec/Jump
  - GUI, added text field for SunPitchUP+Time (in seconds) which adds this number of seconds after 
    sun avoidance to continue pitching up.  If your ship heats up easy (like my Cutter), then you will want
    to add a second or two to be pitch away from the Sun
  - While in SC, check for being interdicted, if so take action (submit, booster away), [initial approach]
  - Optimized number of seconds per jump.   Average just under 60 sec/jump, with fuel scooping once in a while at 70 s/j
  - Added Target Occlusion detection.  As you approach the Station it might suddenly show that
    it is behind the Planet.  This will now be detected and repositioning will occurs to go 
    around the planet
  - Tuned color ranges for masking the region for better image template matching.  If using anything other
    than default ED HUD color scheme, this AP will not work at all
  - Handled non FGB FOAM star avoidance when jumping into those Systems (for dim red suns), 
    so now won't crashed into those
  - Added journal catch to check if game odyssey, capture distance jumped, jumps remaining
  - Added Galaxy and System Map Open for key binding lookup
  - Added total light years traveled for FSD Route Assist and Waypoint Assit

Update requirements.txt file
  - One new packages is required to be installed, pynput==1.7.6, to support mouse click




