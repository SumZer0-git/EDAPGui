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
   It confirms panel focus and the selected Contacts tab before sending the docking inputs. Tab changes are sent
   individually and checked again; unreadable highlights do not trigger blind switching. If confirmation times out,
   the docking attempt stops with an error instead of retrying selection in an unknown tab.
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

### Assist statistics and ETA

The Info tab shows lifetime assisted jumps, lightyears and active time for the current account and individual ship,
plus the ship's average jump-cycle duration and lifetime count of valid time measurements. Accounts are separated
by the journal's commander ID (`FID`); ships use the combination of `ShipID` and the journal ship type,
not their editable name or registration. The type is an additional safeguard against a different model
ever receiving the same ID; it does not imply that the game normally reuses IDs.
Two ships of the same type therefore have independent histories. Switching account or ship ends the active
measurement chain. There is no reset button.

Travel, Waypoint and Single Waypoint flight contribute active assist time. Target-only plotting, DSS and AFK Combat
do not contribute. System travel time covers the FSD route phase, including alignment, charging, hyperspace,
intermediate refueling and positioning. It ends on arrival at the plotted destination, before final-system refueling,
station approach, docking or trading. Local actions contribute only to overall active assist time.

Only autopilot-requested hyperspace jumps confirmed by new journal events count toward jump and distance totals.
Past journal records are not imported. The first confirmed jump in each FSD phase counts but establishes only a
timing baseline. Each following arrival provides one jump-cycle measurement while that phase remains uninterrupted.
Stopping, switching ships/accounts or entering a new FSD phase breaks the chain. A partial or interrupted cycle
never becomes a valid time measurement. Ordinary refueling delays remain in the measured duration.
Durations use a monotonic clock; the measurement timestamp is stored in UTC. Journal polling can introduce small
timing differences. Batched arrivals without a reliable interval are not used as time measurements.

**Overlay > Estimated arrival** controls one sortable line, for example `ETA: ~1h 12m (00:58)`.
The footer also shows the ETA while the system route is active. It estimates arrival at the final system of the
current plotted route, not completion of a whole waypoint list or its station/trade actions. The clock in parentheses
uses the PC's local timezone. Without three valid measurements for the ship, it shows `Calculating...`; with
sufficient stored history it is available immediately on a new route. ETA is hidden during local travel,
when off route or after system arrival.

The estimate is based on remaining jumps, not lightyears. Each valid measurement adjusts a persisted
ship-specific estimate with a 5% weight for the new cycle; older observations gradually lose influence.
The lifetime arithmetic average remains separate. Between jumps, elapsed cycle time reduces the estimate.
An overdue cycle does not consume the estimated time of later jumps or falsely indicate arrival.
The prediction is approximate, particularly after outfitting changes, during retries or on unusual refueling routes.
It never changes assist controls, fuel policy or navigation. A completed system route adds one concise summary
to the GUI log without replacing the AP status.

#### Storage and backups

Statistics are local and unversioned in `user_data/stats/statistics.sqlite3`; Python's built-in SQLite requires no
additional dependency. The database stores account/ship identifiers, numeric counters and UTC-timestamped duration
measurements, not commander names, ship names, system names or complete journals.
Only the latest **1,000 valid time measurements per ship** are retained. Age alone never deletes a measurement.
Lifetime totals and measurement counts are not reduced when old details are removed.

Writes use transactions. Active time is checkpointed at each confirmed jump and when a phase/assist ends;
an abrupt process termination can lose active time since the last checkpoint, but not previously committed totals.
After changed data is committed, a consistent SQLite backup is made if none exists or the previous successful
regular backup is at least **24 hours** old. Restarting or remaining idle does not itself produce another backup.
The latest **ten** regular `statistics-backup-*.sqlite3` files are retained in the same folder.
A new backup is checked before replacing its temporary file and rotating older backups.
Future schema migrations must first create a separate `statistics-migration-*.sqlite3` backup, outside regular
rotation. The original statistics format without ship types is migrated automatically after a verified backup.
Entries without a confirmed type remain intact in account totals, but are not guessed into a ship history or ETA.
Unknown database schema versions are rejected without rewriting the data.

Storage errors disable statistics/ETA and explicitly notify the user; backup failures warn without stopping flight.
A damaged database is never silently replaced with empty statistics or automatically restored from an older backup.
To restore manually, close EDAPGui, preserve the damaged/current file, then copy a known-good backup to
`statistics.sqlite3`. Restoration recovers only the data present in that backup.
Same-folder backups protect against individual file damage, not disk failure or deletion of the whole folder;
include `user_data/stats/` in an external backup for that protection.

### Vision diagnostics

Cockpit tab and navigation-row recognition first checks the existing bright filled highlights, including
thin-line removal. If neither check finds a highlight, a bounded adaptive brightness threshold separates
dim selected backgrounds from dark inactive tabs. The fallback uses HSV value (the brightest color channel),
so shaded default-orange highlights are not rejected merely because their grayscale luminance is low.
Its threshold stays between 140 and 210; it does not lower the normal bright-highlight threshold.
The same brightness measure and threshold validate the rectified highlight's
filled area; quadrilateral, size and fill checks still reject text-only areas and hollow outlines.
Tab navigation still requires one uniquely recognized, OCR-confirmed tab before sending a switch or action.
The left tab capture includes the System icon when the panel appears slightly farther left.

Occluded-target detection checks white and beige dashed rings with their existing color-specific match thresholds.
If the normal-size template does not match, it also checks templates 5% smaller and larger to tolerate slight
ring-size variation at the same screen resolution. Bright surfaces alone do not qualify as a ring.

Compass marker fallback uses sphere-relative pixel areas for 1080p and 4K and checks both bright and dim,
low-saturation markers. Hollow markers are preferred over filled charging glow; small antialiased ring centers
are checked separately so a behind marker is not mistaken for an ahead dot. A rejected filled-template match
cannot validate a weak behind-template match. Unknown markers still stop compass alignment rather than providing
a guessed direction. This is one shared recognition path for SDR/HDR and both HUD color schemes, not a
resolution-specific mode. Real monitor/HDR and HUD-brightness combinations still require in-game validation.
If a dim hollow marker merges with the compass rim or charging glow, an additional fallback checks for one
compact dark hole with a brighter surrounding ring. It requires contrast in at least seven of eight directions
and rejects multiple candidate holes rather than guessing a position.

Set **Debug > Log level > Debug** before reproducing a recognition problem. Normal technical messages remain in
`user_data/logs/autopilot.log`; the complete technical log, including those messages and debug details, is written to
`user_data/debug/debug.log` while Debug is enabled. Both logs rotate separately in their respective folders on the first use of each log in a
program run; up to ten older files are kept for each. The GUI's log-file button opens `autopilot.log`.
Recognition scores, message-gate measurements, OCR text and fallback attempts are Debug-only diagnostics.
Short user-facing events, such as sending the supercruise exit, remain at Info level.
The optional CV view draws match boxes on display copies; it does not alter the recognition images or saved context.
Raw BGRA-backed OCR crops are copied into writable display images before annotations are drawn.
Its windows are managed by the main GUI thread and open within the work area of the monitor containing the main window.
Large images are scaled down to fit. You can move the windows; subsequent frames do not reset their positions.
Resizing a CV window scales its images up or down while preserving their aspect ratios, including the last frame
when recognition is idle. Only the display is resized; captures, matching and saved diagnostic images are unchanged.
The Debug tab has four **CV Views** buttons: **Compass**, **Target**, **Occluded Target** and **HUD Messages**.
A button opens or focuses its window; the title-bar X closes it, and the button opens it again.
HUD Messages combines the message pre-check and OCR result in two separate display areas.
Windows initially show "Waiting for recognition..." until the corresponding recognition step runs. There are no
extra background captures; the last displayed frame remains visible between recognition steps.
Only opened views prepare display images, and none open automatically at startup. The old global CV switch is no
longer used. The CV view is independent of Debug logging and diagnostic image recording.
Display images may be filtered, cropped, annotated or scaled; they are not always unmodified raw search captures.

**Debug Overlay** takes effect without restarting. It draws search rectangles and OCR results over the game only during
supported HUD-message and panel/OCR checks, not continuously for compass or target matching. Switching it off removes
diagnostic markings without clearing normal AP status information. CV windows can overlap screen captures, and so can
debug markings when **Show in screenshots and recordings** is enabled on the Overlay tab; disable them for unobstructed
diagnostic runs or move CV windows to another monitor.

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
- Unconfirmed navigation and internal-panel highlights save the evaluated region and a later panel-context image,
  before the next navigation input. The later image is not necessarily identical to the evaluated frame.
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
