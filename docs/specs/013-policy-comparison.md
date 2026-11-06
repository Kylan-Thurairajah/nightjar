# Matched policy comparison

Status: implemented and locally verified; owner manual review pending.
See [delivery evidence](../reports/013-policy-comparison.md).

## Objective and behavior

Press V in a configured GridWorld mission to pause and open an isolated comparison
screen behind the accepted-command barrier. It uses that mission's validated scenario,
map, seed, sensor preset, fleet size and total tick ceiling. Explicit Run/Enter starts
FRONTIER then INFORMATION GAIN as separate all-AUTO simulations; current launch control
and chosen single policy do not affect this experiment. Inputs are identical except
policy; shared seed is not an identical sensor-reading stream across different paths.

Budget must be1-1000; reject larger configured workloads clearly before allocation.
No benchmark on UI loop. Show running/cancelling/error states; Esc/Q/close requests
cooperative cancellation and waits asynchronously for the actual core thread to finish
before dismiss/restart. Repeated asyncio cancellation cannot release thread ownership.
Run state and RNG are isolated from the original live/replay mission at all times.

On completion show both real maps on sufficiently wide screens; compact80x24 uses
one selected policy view with Tab/1/2 switching and both final summary metrics visible.
H/C/P select comparison layers. Left/Right seek a shared tick cursor, Space plays the
recorded comparison only. Choose latest committed snapshot whose actual tick<=cursor;
show actual displayedtick, not interpolated actions. Earlier-terminal run freezes at
its final snapshot. All traces use real cumulative visited coverage and entropy, with
axis/range labels. Initial spawn visits count; unreachable cells remain in denominator.

Report actual action ticks/scans/coverage/uncertainty change/stop reason and no winner,
accuracy or confirmed-discovery score. Offer deterministic raw JSON through the service
API with configuration, protocol, per-boundary metric points, finals, source/software
provenance; no new save dialog or automatic writes. No core planner/sensor changes.

## Implementation plan and ownership

1. services/comparison.py and tests/test_comparison.py: isolated synchronous runner,
   immutable report/run/trace contracts, public-state metrics and safe async wrapper.
2. tui/comparison.py, comparison.tcss, app.py and tests/test_tui_comparison.py: explicit
   run/cancel screen, dual/toggled maps, measured traces/replay and guarded V entry.
3. Lead docs/spec/NEXT/roadmap, CI formatter and report; integration verification.

## Service contract

- ComparisonPoint(tick,snapshot_index,coverage,entropy_bits,scans), frozen.
- ComparisonRun(strategy,timeline,points), frozen; at_tick(tick)->MissionSnapshot
  selects latest committed snapshot<=cursor. final property returns final snapshot.
- ComparisonReport(config,runs,source_sha256,python_version,numpy_version,
  application_version), frozen; to_json()->str with raw metric/provenance report.
- run_comparison(config,*,cancel_event:threading.Event|None=None)->ComparisonReport.
- compare_policies(config,*,cancel_event:threading.Event|None=None) async wrapper.
- ComparisonCancelled(RuntimeError). Check Event before creation/between rounds/
  policies; shield executor Future through repeated cancellation and wait for exit.

## Acceptance and definition of done

- Deterministic identical paired inputs except strategy, correct public totals/traces,
  global budget/early-stop behavior, valid independent histories and no groundtruth.
- Cancellation before/mid-run and repeated task cancellation verified; no busy loops
  on no-progress ACTIVErounds, failure/error does not leak ownership or live state.
- Normal/80x24 real mapped comparison and labels, responsive cancel/close, common-tick
  seek/replay/clamp, view switching and original live/replay byte-isolation verified.
- Focused service/UI checks and fullregression once, existing lint/types/format,
  bounded independent actual-diff review, smoke where supported; fix blockers and
  rerun affected checks only. No redundant broad numerical experiments.
- Docs match actual controls/limits; NEXT hands off demo/story stage014. Stop after
  verified delivery. No new dependency, commit/push/merge or external publication.
