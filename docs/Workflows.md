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

1. Loads the route selected in the Waypoints tab and visits its stops in order, skipping inactive and completed stops.
   Older route files must first be imported through **Import... > Legacy JSON...** and saved.
2. For another system, it first tries the configured Galaxy Map bookmark. If there is none or it does not produce
   the expected route, it searches by system name. A blank system name means the current system.
3. After entering supercruise, it selects and confirms the next route system before each jump alignment.
   If the active target cannot be confirmed, it sets throttle to zero and stops with a message.
   Zero throttle in supercruise does not bring the ship to a standstill.
4. If the requested station is already selected after arrival, it reuses that target. Otherwise, it tries configured
   local bookmarks, then reads station names from the Navigation panel and scrolls to the first exact match.
   The station must be visible under the game's current filters. An unconfirmed target stops the assist before local travel.
5. It runs the local-target flight and docking sequence for the selected destination. If already docked at the
   destination, it can perform configured trades or cargo transfers, then marks the waypoint complete and saves the
   progress separately from the route. Ordinary market trades require confirmation from the game before remaining
   quantities are reduced.
   Trade requests use commodity IDs; their editor order is preserved and the current market supplies the localized
   name used for dialog confirmation. A change of display language does not change the requested goods.
6. **Repeat route** restores the original quantities and makes all stops pending after the last active stop.
   The route then starts again until stopped; a fixed repetition count is not available. Waypoint Assist
   remains docked at the end of a non-repeating route and
   undocks when the next travel operation requires it.

For route editing, imports, trade options and troubleshooting, see the [Waypoint guide](Waypoint.md).
The editor's **Plot to System/Station** buttons only select targets; they do not start travel or trading.

### Vision diagnostics

Set **Debug > Log level > Debug** before reproducing a recognition problem. Normal technical messages remain in
`user_data/logs/autopilot.log`; the complete technical log, including those messages and debug details, is written to
`user_data/debug/debug.log` while Debug is enabled. Both logs rotate separately in their respective folders on the first use of each log in a
program run; up to ten older files are kept for each. The GUI's log-file button opens `autopilot.log`.
Recognition scores, message-gate measurements, OCR text and fallback attempts are Debug-only diagnostics.
Short user-facing events, such as sending the supercruise exit, remain at Info level.
Diagnostic images are saved directly in `user_data/debug/<category>/`. Images from the same case share a timestamp
and identifier in their filenames, followed by their role, such as `_evaluated.png` or `_context.png`. The debug log
identifies the category, reason and filename prefix; related scores, OCR text and decisions are logged by the recognition
code. New case prefixes are relative to the program folder, such as `user_data/debug/compass/<case>`, rather than exposing
the absolute installation path. For a debug-directory override on another drive, prefixes are relative to that debug
directory instead. Existing logs are not rewritten. At most 50 cases are retained per category across runs: after successfully saving a new case, all images belonging
to the oldest excess cases in that category are removed. Unmanaged files and older case directories are not rotated.
Images and logs rotate independently, so their retention periods can differ. Existing logs at the old
`user_data/logs/debug.log` location are not moved or deleted.

To share a run, review and ZIP `user_data/debug/`; it can also contain earlier cases and rotated logs.
For maintainers, `user_data/incoming-debug/` is a separate local inbox for debug dumps received from other users.
The application creates it but does not process or automatically clean its contents. It is not part of the debug ZIP
and is excluded from Git along with the rest of `user_data/`.

- A failed target alignment saves the original search region used for the last failed match and a same-frame context
  with 1.5 times its width and height (clipped at screen edges). The search region and matching behavior stay unchanged.
  While Debug is enabled, each target search captures the larger region; images are saved only for a diagnostic case.
  The target can still lie outside the context; this is not a full screenshot.
- Missing compasses and weak nav-point matches save the evaluated image and a larger same-frame context. The search
  itself still uses the original region. The larger capture is used only while Debug is enabled.
- An unconfirmed trade dialog saves its separately captured title and commodity regions and a later dialog context.
  OCR wait timeouts, unreadable disengage messages and ambiguous alignment or line-of-sight text can also save cases.

The program cannot automatically detect every wrong recognition: an apparently successful match can still be wrong.
Not every absence of HUD text is an error. Images and logs can contain player information; review and remove sensitive
details before sharing them. Debug images are not captured or saved with Debug disabled. Image encoding and the larger
compass and target captures can add overhead while debugging.

Navigation destination selection accepts long, narrow filled row highlights without collapsing their corners during
contour simplification. Thin lines and hollow outlines do not count as selected rows; the destination still requires
an exact name match and confirmation from game state.

### Other assists

- **DSS Assist** monitors the current system while in supercruise and attempts a discovery scan after entering a
  different system.
- **Single Waypoint Assist** selects a system entered on the Debug tab and travels there; it can also be given a
  local station target. It uses the same next-jump target checks as Waypoint Assist.
- **AFK Combat Assist** monitors shield and fighter status, evades when shields are down, and redeploys a fighter
  when one is destroyed.

## Follow-up items

- Refine station-name screen reading for additional destination icons and HUD layouts as examples become available.
  Bookmarks remain an alternative when a destination cannot be read reliably.
- Avoid changing hyperspace-interdiction recovery until there is a reliable way to validate it. Interdiction attempts
  are too unpredictable for routine testing: they may not occur for days, then happen several times within an hour.
