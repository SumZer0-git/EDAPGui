
# Robigo Mines Passenger Loop

## What does it do?
- Completes Robigo Mines to Sirius Athmospherics passenger missions
- Performs Mission completion, Mission selection (fills cabins), executes the loop, docks and 
  loop again
- What is Robigo Mines Passenger Missions?  https://www.youtube.com/watch?v=JtDiR51QMJc
  
## Run Stats
- Expect $15m/loop (if AFK)
- Expect 17-20min per loop
  
## Optimizing $$
1. Disable Robigo Assist when docking to Robigo Mines and select missions manually to optimize the $$ 
   1. Found can get up to $25-27m per loop (at times) when loading the cabins with high paying passengers
2. After selecting missions
   1. Target SOTHIS System (via GalaxyMap)
   2. Go back to main station menu
   4. Emable Robigo Assist
      - In latest version, when you enable Robigo Assist, it will determine where are you in the Robigo loop and pick up from that point
      - In this csae it will see that you are In Station and have a Target defined so will pick up the loop by performing the undock

## Interdiction
- Found that 1 out of 10 or so loops you will probably get interdicted and killed
  - You respawn at a station ~60ly from Robigo, so not too bad
- If you want to fight the interdiction (if you are monitoring), then:
  - Disable the Roobigo Assist ('end' key by default)
  - Fight Interdiction
  - Re-enable Robigo Assit and it will pick up where you left off

## Constraints:
- This assists determines where you are in the loop and continues from there. If starting, best to jump to Robigo Mines and dock at the station to start
- Odyssey only (due to unique Mission Selection and Mission Completion menus)
  - However, if configure the config/AP.json to only do a single loop (Robigo_Single_Loop : True) then this Assist will work in Horizons
    - The CMDR will have to manually complete and select missions, then re-engage the Robigo Assist
- Set Nav Menu Filter to: Stations and POI only
    - Removes the clutter and allows faster selection of Robigo Mines and Sirius Atmos
- Must have Advanced Docking Computer, don't need a SC Assist module
- If you have never taken passenger missions from Robigo, I would recommend doing one mission manually so that all locations are discovered before trying Robigo Assist. Otherwise, following 'first loop' instructions below.
- First Loop:
  - When arriving in Sothis, the Robigo Assist will target Sirius Atmospherics from the Nav Panel
    - Likely, in this first loop, Sirius Atmospherics will not be listed in the Nav Panel
    - Terminate the Robigo Assist if this is the case
      - Target "Don's Inheritence"
      - Enable Robigo Assist,  when < 1000ls from Don's Inheritence Sirius Atmosperhics will show up in Nav Panel
      - Terminate the Robigo Assist, Select Sirius Atmospherics from the Nav Panel, and Re-enable Robigo Assist
  - This may be required only for the first loop in the ED Session
- Does not handle interdiction and you could be attacked at Sirius Atmos or when traveling back to Robigo Mines if you have
  illegal passengers (AP does nothing to help with this)

## Testing
- Has only been tested with a Python ship
- Tested with resolutions of 1920x1080, 2560x1080, and 3440x1440

## Observed Behaviors
- If Robigo Mines outpost is behind the Rings as you approach, the ship will drop out of SC
  with "Too Close"..  you must terminate the AP and manually dock 
- The Cabin Autofill option is very poor (in the game), it does not optimize putting the passengers into 
  optimal cabins.  This reduces the payout
