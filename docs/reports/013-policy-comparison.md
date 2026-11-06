# Matched policy comparison delivery - 2026-11-05

Status: implemented and locally verified on `feature/policy-comparison`.
Spec: [013](../specs/013-policy-comparison.md).

Owner requested continuation after approving the presentation roadmap. Preserve
previous uncommitted012 work. Featurebranch created without committing/pushing.

## Plan and agent ownership

- `/root/comparison_architecture` (`architecture`, read-only instructions): existing
  immutable public snapshots and ordinary isolated fleet runs suffice. Recommended
  bounded budget, event cancellation/shielded executor ownership, common-ticklatest
  snapshot selection (including zero-tick mode changes), uniform tick sampling and
  no hidden state/no benchmark protocol changes. No edits/tests.
- `/root/comparison_service` (`implementation`): new services/comparison.py and
  tests/test_comparison.py only; immutable raw reports, paired runs and cancellation.
- `/root/comparison_ui` (`implementation`): new comparison screen/CSS, appV guard
  and tests/test_tui_comparison.py only.
- `/root/comparison_verification` (`simulation`, read-only instructions): bounded
  independent adapter/traces/ownership verification; no repeated numerical sweep.
- Lead: spec/NEXT/roadmap/docs, CI allowlist, integration/full gates and review.

Native read-only roles inherit sessionpermissions; instruction-only, not filesystem
isolation. Final code review uses separate read-only CLI where supported. No new
framework/dependency, sensing/planning algorithm, archive schema or external write.

## Acceptance and evidence

Use the spec checklist: actual pairedinputs/metrics, isolated immutablehistories,
thread cancellation/drain, honest replay/traces, responsive normal/narrow UI.
Prior012 fullsuite294passed plus50affectedUI tests after its layout correction;
there is now one additionalviewporttest. No redundant baseline rerun before changes.

Results pending implementation. New sourceprovenance includes the comparison adapter
without changing the standalone benchmark fingerprint/protocol merely for UI work.

## Service verification and measured example

Service newtests: **9passed0.39s**. Expanded comparison/hybrid/benchmark check:
44passed with2known restricted-temp fixture errors; not a passing full gate.
Ruff/format passed, mypy14sourcefiles passed. Delayed real-round probes by independent
simulation reviewer verified five repeated task cancellations and separate Event
cancellation retain ownership until actualthreadexit, with no partial pair or second
policy. Matched input/public point/archive/common-tick probes passed on facility seed7
budgets1/7. Complete review results recorded after UI integration.

Lead recorded docs/benchmarks/facility-pair-40.json through publicrun_comparison:
Compactfacility,Standard sensor,3AUTO,seed0,40ticks. FRONTIER21scans,13.0178%visited,
H2.773751bits; IG3scans,23.0769%visited,H6.893118bits. Bothbudgetexhausted. Exact raw
points and software/source provenance retained; no general efficiency claim.

## Integration findings and corrections

Independent verification caught a screen-construction failure: Screen.layer is a
read-only Textual property. Lead inspection of installed MessagePump then identified
_task and _closing as framework-owned fields. UI writer assigned domain-specific
map_layer/_experiment_task/_comparison_closing names before final integration.
Closing now drains through a worker so an input handler does not hold the message
pump while waiting for core completion. Actual compact viewport rows, not merely
unbounded widget text, must remain readable. These findings are resolved and tested
before completion evidence is claimed.

## Integrated verification and final review

- Full integration suite once: **309 passed in38.80s** with pytest temp-directory
  access, command `python -m pytest -q -p no:cacheprovider`.
- New UI fivecases passed3.44s; affected presentation/hybrid/replay/comparison
  integration **28passed16.44s**. Ruffcheck passed, formatter31files passed,
  mypy14sourcefiles passed, whitespacecheck passed.
- Independent simulation reviewer: service9passed0.36s; facilityseed7 budgets1/7
  repeatedJSON/archive/metrics/tickprobes passed. Five repeatedTaskcancel and Event
  delayedround probes passed. Final80x24live/140x42replay headlessprobes preserved
  livearchive/selection/replayindex, checked common-tick samples[0,0,3,3,7] for
  coords[0,2,4,5,7], and rendered both finalmetric/units/traceaxes. No remaining
  service/ownership/isolation blocker.
- Actual80x24 PTY smoke: facilityCompact40ticks, V->Enter ran bothpolicies,
  Tab/Space switched/playedrecords, Q returnedpaused, Q exited0. Measuredresults
  and actualticks rendered correctly. This is not owner manualacceptance.
- Separate bounded code-only CLIreview executed with enforced sandboxread-only,
  approvalnever, apps/pluginsdisabled and exec--ephemeral. Found P2 childlessStatic
  mapoverflow not actuallyscrollable, plus80x30 longsummarycroppedmetrics. UIwriter
  assigned naturally sizedmaps inside true scrollcontainers and width-aware compact
  summaries, with targeted viewport/scroll regressions. No other actionable findings
  in cancellation, restart, traces, common-tickview or isolation.

Final display corrections verified; do not present earlier309tests as
verification of later fixes. OptionalGitHubMCP tokenmissing did not blocklocalreview.

## Final display corrections

MapWidget now has full natural cell dimensions inside real ScrollableContainers,
with PgUp/PgDn vertical and ShiftLeft/Right horizontal controls plus mouse scrolling.
Compact formatting uses width as well as height, preserving both policy summaries
at80x30. **8 UI cases passed in5.38s**, including actual terminal compositor checks
for bottomroomlabels and bottom-rightdrone02 on Compact/Extended maps at80x24, and
full metric/entropychange/stopreason rendered-line assertions at80x30. Lead inspected
the corrected implementation and reran Ruff/types/whitespace successfully. The earlier
309-test fullsuite predates these three added regression cases; only affected tests
were rerun after the display correction, per focused verification approach.

## Changed files and limits

New services/comparison.py, tui/comparison.py, comparison.tcss and two focused test
modules; V entry guards in app.py; existing CI format/typegates include the new code.
README/architecture/design/benchmark/manual guides, NEXT, roadmap, specs013/014 and
this report describe the new behavior and next demo/story handoff. Raw measured pair
is in docs/benchmarks/facility-pair-40.json. Earlier012 uncommitted work is preserved.

No dependency, simulation math, archive schema or standalone benchmark protocol change.
Paired runs are reset all-AUTO experiments, not continuations of human actions. Shared
seeds do not imply identical noisy readings on different routes. Common cursor can
lead actual snapshot tick at round boundaries; no interpolation. Long jobs are bounded
to1000ticks, cancellation can wait for one in-flight round, and histories consume
memory. Displayed uncertainty/coverage are not discovery/correctness or a general
policy ranking. No automatic disk save; raw JSON is a service API. Original live/
replay state is retained and returns paused. Owner manual acceptance remains pending.
No commit, push, merge, external publication or next-feature execution performed.

Independent correction follow-up:80x30Extended probe passed natural80x20 map,
vertical/horizontal keyboardscroll, viewport endpointsx6/y8 and actual bottom-right
02 in compositor output; bothfinalmetrics/units/controls visible, originalarchive
unchanged onreturn. Initialprobeassumedscroll_end movesright; fixingharnessx_axis
behavior passed with no productionchange. No remaining blockers.

Final wheel build `python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist`
passed; ZIPinspection confirmed comparison service/screen/CSS packaged. This is not
an isolated freshmachineinstall claim. FinalRuff/types/format/whitespace passed.
Local acceptance and definitionofdone met. NEXT hands off014 repeatable demo/story;
that next slice was not started automatically.
