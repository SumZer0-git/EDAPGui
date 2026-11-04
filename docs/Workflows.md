# Assist workflows

This document summarizes the behavior currently implemented and lists a small number of follow-up items.

## Current implementation

### Travel Assist

1. Starts from the system route and/or local target selected in Elite Dangerous. If a system target remains, it
   follows the Galaxy Map route; otherwise, it starts with the local target.
2. During system travel, it avoids a bright star in front of the ship, aligns to the navigation compass, aligns to
   the target using screen detection, and starts the FSD jump.
3. After each jump, it starts a discovery scan in a background thread, attempts to refuel, then accelerates to move
   away from the star. The scan is attempted only in Analysis Mode.
4. When the system route ends, it continues to a remaining local target automatically. If there is no local target,
   it stops at the destination.
5. For a local target, it undocks or enters supercruise if needed, aligns using the navigation compass, and repeatedly
   aligns using screen detection while watching for the supercruise disengage prompt.
   When the target is occluded, it attempts a repositioning maneuver; it also checks for interdiction and realigns
   afterward.
6. On disengagement, it checks whether docking is possible and whether the destination supports docking. When
   applicable, it approaches, requests docking through the Navigation panel, and waits for the docking computer.
7. Once docked, the docking sequence selects refuel, repair, and ammunition services. The local-target phase does not
   run a waypoint trade sequence.

### Waypoint Assist

1. Loads the selected JSON file and processes its entries in file order, skipping entries marked `Skip` or
   `Completed`.
2. Travels to a different `SystemName` by selecting it in the Galaxy Map and running the system route. A blank
   system name means the current system.
3. In the system, it can select the destination with a Galaxy Map or System Map bookmark. A station name by itself
   is not currently enough to select a target.
4. It runs the local-target flight and docking sequence for the selected destination. If already docked at the
   destination, it can perform configured trades or cargo transfers, then marks the waypoint complete and saves the
   file.
5. A `REPEAT` entry resets completion flags and starts the list again unless that entry is skipped. Waypoint Assist
   does not explicitly undock after every completed stop: it remains docked at the end of a non-repeating list and
   undocks when the next travel operation requires it.

### Other assists

- **DSS Assist** monitors the current system while in supercruise and attempts a discovery scan after entering a
  different system.
- **Single Waypoint Assist** selects a system entered on the Debug tab and travels there; it can also be given a
  local station target.
- **AFK Combat Assist** monitors shield and fighter status, evades when shields are down, and redeploys a fighter
  when one is destroyed.

## Follow-up items

- Revisit targeting local destinations by name as part of a future Waypoint Assist overhaul. Name-based selection has
  previously been unreliable and error-prone; bookmark selection remains the supported approach for now.
- Avoid changing hyperspace-interdiction recovery until there is a reliable way to validate it. Interdiction attempts
  are too unpredictable for routine testing: they may not occur for days, then happen several times within an hour.
