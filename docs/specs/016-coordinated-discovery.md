# Coordinated assignments and verified beacon discovery - next slice

Owner approved the user-facing operation direction. Reconcile against final015 code
before implementation. Demo/blog/restart/replay optimization remain deprioritized.

## Operational mode and boundaries

Introduce an explicit operational layer for user missions; keep standalone baseline
benchmark/comparison semantics unchanged unless they explicitly select and label
operational mode. Preserve default low-level core behavior and v1 golden archives.
No hidden ground truth enters planners; only the verifier checks the synthetic beacon.

## Persistent public tasks

Frozen Assignment(drone_id,kind,target,assigned_tick,reason), kindSEARCH_SCAN or
VERIFY_BEACON. Public OperationsSnapshot includes phase, candidate, verifier_id,
confirmed_position(optional onlyafterconfirmation), assignments and typedmilestones.
Retain useful reachable sensing locations until scanned/invalidated; deterministic
travelcost/informationutility/redundancy preferences. Prefer different rooms/regions
without treating room boundaries as walls. Plan routes against actual occupancy.
Release/reallocate on MANUAL takeover, IDLE parking, blocked/unreachable route,
completed scan or new contact. Avoid thrashing; one verifier, others continue search.
Temporary blockage must not end the whole operation solely because one agent waits;
define bounded yield/no-progress behavior explicitly and test terminal conditions.

## Discovery sequence

SEARCHING -> CONTACT -> VERIFYING -> CONFIRMED. CONTACT is provisional evidence,
not truth. Initial proposed product threshold: MAPprobability>=0.6 after evidence;
parameter is not a measured optimum. Pin candidate during active verification until
verified/impossible/unreachable or verifier changes control; reconsider coherently.

Manual F verifies current cell; AUTO verifier travels to candidate and verifies.
Verification consumes one globaltick, no proximity RNG draw. Distinct VERIFICATION
observation records reliable exactcell presence: radius0,sensitivity1,falsepositive0.
Reuse Bayesian likelihood normalization: falseverification zeros that cell and logs
candidate rejected; trueverification collapses posterior and emitsconfirmation.
Provider verifier alone accesses hidden position. Existing noisy E scans unchanged.
Confirmation wins if verification consumes the last allowed tick; later actions stop.
Persistent objective mark, confirmingdrone/room/tick banner, paused mission/debrief
and confirmation milestone are public only after the verified positive observation.

## Replay/model compatibility

MissionSnapshot.operations optionalNone; omit absentfield in version1 encoding to
preserve exact legacy archives. Version2 operational archives validate assignments,
phase transitions, geometry/ownership, verification sensorconfig/action/ticks,
posterior reconstruction, confirmationcause and postterminal behavior. Decode v1
unchanged. A newkind/config must not simply bypass strict replay validation.

## Acceptance

- Deterministic threeAUTO tasks split useful reachable work and persist acrossrounds;
  release/reassignment fixtures cover all control/completion/block/contact triggers.
- Manual and AUTO verification success/failure, falsecontacts, finaltick precedence,
  budget/no-progress/capacity atomicity and hidden-state isolation have focused tests.
- v1goldensunchanged; v2operational roundtrip/tamperrejection/historyisolation.
- Each assignment has its own owner marker/letter with a shared neutral palette
  and selection-only emphasis and visible reason/activity; outcome
  banner/objective mark/debrief change only on verified discovery, not highbelief.
- Architecture/simulation/QA/review with focused checks and fullregression; no new
  dependencies or unmeasured performance/discoveryaccuracy claims.

Definition of done: implemented end-to-end operational mission and actual verified
results, documented limits and manual walkthrough. No automatic nextmilestone,
commit/push/merge/publication. This document is a concrete nextspec, not a claim that
these mechanics already exist in015.
