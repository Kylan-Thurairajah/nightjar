# Hybrid fleet manual acceptance

Run these commands in PowerShell, in order:

```powershell
Set-Location C:\Users\kylan\coding\nightjar
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m nightjar
```

Use three drones, Compact map, Open field, FRONTIER planner, MANUAL control,
seed 0 and a 100-tick budget for an easy-to-observe run. Review preflight and launch.

| Check | Expected result |
| --- | --- |
| Launch | Paused; 01 MANUAL, 02/03 AUTO. |
| Space | 02/03 act while 01 waits for you. |
| WASD, then E while running | Selected MANUAL drone moves/scans; background AUTO continues. A blocked movement consumes a tick. |
| Tab | Next active drone becomes MANUAL; previous controlled drone becomes AUTO. |
| I, then try WASD/E | Selected drone stays parked; input is denied without pausing other AUTO drones. |
| M on parked selected drone | Selected returns to MANUAL; other parked drones remain parked. |
| Space to pause, then N | One roster-order AUTO round; no implicit MANUAL movement. With two eligible AUTO drones this usually consumes two ticks. |
| H / C / P | Belief / coverage / paths display without changing mission state. |
| R, Left/Right, Tab | Historical viewing; selection is view-only. WASD/E/M/I/N do not mutate live state. |
| R again | Original live selection restored, fleet paused. Space resumes AUTO. |
| Tick limit | Global ticks do not exceed budget; mission stops. Planner exhaustion may stop the whole mission earlier. |

Quit with Q. Run the application again using the same command; choose IDLE initial
control. All drones should stay parked and Space should not start autoplay. M
reactivates selected as MANUAL; pressing M again releases it to AUTO, then Space runs it.

Repeat key controls and replay in a terminal approximately 80 columns by 24 rows.
Telemetry may scroll; the mission/replay status should remain usable. Optionally
repeat with INFORMATION GAIN to check input responsiveness during planning.

For a scripted-demo regression check after quitting:

```powershell
.\.venv\Scripts\python.exe -m nightjar --mode demo
```

Space/N, H/C/P and R/Left/Right should retain scripted-demo behavior; Q exits.

## Acceptance record

- 2026-11-05: Owner said the delivered work "looks good" and requested continuation.
  This records positive general feedback, not confirmation that every check above ran.
- 2026-11-05: Owner confirmed they ran the supplied manual tests and all looked good.
  Manual acceptance passed by owner report; no blocking issues reported. Exact
  terminal dimensions/configurations were not separately recorded.
- Automated implementation evidence: [delivery report](reports/010-hybrid-fleet-controls.md),
  237 passing tests at delivery. No new test execution is claimed by this guide.
- Integration: no commit, push, merge or publication approved by this acceptance task.

## Fleet coordination follow-up (milestone 011)

New behavior: AUTO planners use all drones' visited coverage. FRONTIER and INFORMATION
GAIN also prefer different eligible targets within a fleet round. There are no new
shortcuts or fixed sector boundaries. Paths and sensing footprints may still overlap;
short runs with distinct targets are not a general efficiency guarantee.

After automated validation, launch with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m nightjar
```

Choose three drones, Compact/Open field, FRONTIER, MANUAL and a 100-tick budget.
Move drone01 a few cells with WASD while paused. Press P or C, then Space: other
AUTO drones should continue exploring with shared coverage. Use Tab to hand off,
I to park and M to reclaim; controls should behave as before. Pause and use N to
observe one fleet round at a time. Shared corridors/revisited transit cells are valid.

Repeat with INFORMATION GAIN. Check R/arrows/Tab/R restores the unchanged live
mission/control selection, paused. Check compact-terminal responsiveness. Reaching
the tick budget or one planner's exhaustion still stops the mission globally.

Milestone011 manual acceptance: pending; the earlier owner pass applies to hybrid
controls before this coordination change. Exact target preference is verified by
seeded automated fixtures, since the UI shows only the latest planner decision.

## Mission presentation follow-up (012)

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m nightjar
```

Choose Training facility, Compact, three drones, MANUAL, FRONTIER and150ticks.
Preflight should explain one synthetic objective and uncertain readings. Launch;
neutral terrain should show room names. Press E: latest-reading text and a scan-area
tint appear. Space runs background AUTO; `+` marks latest fleet movement target.
Use H/C/P and Tab to check readable layers and room/activity telemetry.

Press B while running: summary opens after accepted work, shows actual coverage/
scans/uncertainty and pauses further rounds. Esc/Enter/Q closes to the same paused
mission. Resume, then use R/arrows/B to inspect a historical summary; no future
readings/ticks should appear. Exit to the same replay position, then R returns live.
At mission end B should show the actual stopping reason without a discovery claim.
Check B at80x24: body can scroll and close button/shortcuts remain usable.

No owner manual acceptance for012 has been recorded yet.

## Matched comparison follow-up (013)

Run `python -m nightjar` with the project environment. Choose Training facility,
Compact, three drones and a40-tick budget for a quick comparison.

- Move/scan manually, then V: original mission pauses and comparison settings are
  explicit. Enter/Run starts fresh all-AUTO runs; your manual actions are not copied.
- After completion inspect both summaries. Tab/1/2 switches visible policy at80x24;
  widen the terminal for two full maps. H/C/P change comparison layers only.
  PgUp/PgDn scroll vertically; Shift+Left/Right reaches clipped wide-map cells.
- Left/Right and Home/End seek common ticks; actual displayed ticks can lag the
  cursor at round boundaries or after an early stop. Space plays recorded views.
- Esc/Q returns to the same paused live/replay mission, same selection and evidence.
- Reopen, Run then close while computing: cancelling stays responsive and returns
  only after worker completion. No further live actions should appear.
- Try a configured budget above1000: show a clear limit error, no silent clamping.

Owner manual acceptance of013 is pending. Exact totals/cancellation and replay
isolation also have focused automated evidence; no new inference model is introduced.

## Field awareness follow-up (015)

Run the normal application. Choose Training facility, Compact, three drones and
MANUAL control. Confirm animal markers, visible doors/equipment and matching
telemetry. G should switch to numbers without moving drones or consuming ticks.
Use P to see owner-colored/lettered trails and shared crossings.

Move through a doorway into another room: one room-entry log should appear. A
blocked wall/equipment move should not produce an entry. Telemetry shows physical
room visitation. T opens room coverage and ordered milestones; B includes a brief
field summary. Opening either pauses AUTO; Esc/Enter/Q returns to the same view.

Seek an earlier view with R/arrows then T: later entries/readings/stopping milestones
must not appear. Check T at80x24, including its scrollable body and close button.
A positive signal stays explicitly unconfirmed. Actual beacon confirmation and
persistent per-drone tasks are planned next, not implemented by this visual slice.

Selection-only unit marker check: withthree drones, Tab/1/2/3 must move the amber
highlight to exactlyone selected drone; VIPER must stayneutral whenunselected.
Toggle selected M then I: highlight followsselection, not mode. G swaps compact ASCII R1/G2/V3 designators for numeric IDs. No emoji colorfonts or fixedVIPERorange.
