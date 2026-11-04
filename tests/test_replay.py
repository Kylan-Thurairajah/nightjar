"""Deterministic public replay archives, scheduler boundaries and invalid loads."""

import json
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from nightjar.core.planning import SearchStrategy
from nightjar.core.provider import GridWorldSimulation, MissionStatus, OperationalMode
from nightjar.core.replay import HistoryCapacityError, ReplayTimeline
from nightjar.core.world import Direction, GridWorld


def simulation(**kwargs):
    return GridWorldSimulation(
        GridWorld(width=6, height=4, seed=43, obstacles={(2, 2)}),
        drone_count=3,
        search_strategy=SearchStrategy.RANDOM,
        **kwargs,
    )


def trace():
    run = simulation(max_ticks=20)
    run.step(Direction.NORTH)  # blocked movement is still a committed tick
    run.scan("02")
    run.set_mode("01", OperationalMode.AUTO)
    run.set_mode("03", OperationalMode.IDLE)
    for _ in range(4):
        run.queue_manual_action("02", Direction.WEST)
        run.fleet_round()
    return run


def test_seeded_fleet_trace_serialization_and_round_trip_match_every_snapshot():
    first, second = trace(), trace()
    assert first.history.to_json() == second.history.to_json()
    loaded = ReplayTimeline.from_json(first.history.to_json())
    assert loaded.to_json() == first.history.to_json()
    for expected, actual in zip(first.history.snapshots, loaded.snapshots):
        assert actual.frame == expected.frame
        assert actual.observations == expected.observations
        assert actual.sensor_config == expected.sensor_config
        assert actual.last_planner_decision == expected.last_planner_decision
        assert actual.belief.stats == expected.belief.stats
        np.testing.assert_array_equal(
            actual.belief.probabilities, expected.belief.probabilities
        )
    assert loaded.snapshots[0].frame.tick == 0
    assert [event.sequence for event in loaded.events] == list(
        range(1, len(loaded.events) + 1)
    )
    assert loaded.events[0].kind == "blocked"
    assert loaded.events[0].tick == 1


def test_fleet_round_captures_once_and_interleaves_modes_in_roster_order():
    run = simulation(max_ticks=10)
    run.set_mode("01", OperationalMode.AUTO)
    run.queue_manual_action("02", Direction.WEST)
    before = len(run.history.snapshots)
    run.fleet_round()
    assert len(run.history.snapshots) == before + 1
    boundary = run.history.snapshots[-1].index
    events = [event for event in run.history.events if event.boundary == boundary]
    assert [event.drone_id for event in events] == ["01", "02"]
    assert [event.tick for event in events] == [1, 2]
    assert run.history.snapshots[-1].frame == run.frame()
    ReplayTimeline.from_json(run.history.to_json())


def test_budget_exhausted_mid_round_stops_before_later_queued_action():
    run = simulation(max_ticks=1)
    second_start = run.frame().drone("02").position
    run.queue_manual_action("01", Direction.EAST)
    run.queue_manual_action("02", Direction.WEST)
    run.fleet_round()
    assert run.frame().tick == 1
    assert run.frame().status is MissionStatus.BUDGET_EXHAUSTED
    assert run.frame().drone("02").position == second_start
    assert [event.kind for event in run.history.events] == ["move", "terminal"]
    saved = run.history.to_json()
    run.fleet_round()
    run.step()
    run.autonomous_step("01")
    run.set_mode("02", OperationalMode.AUTO)
    with pytest.raises(ValueError, match="ended"):
        run.scan("01")
    with pytest.raises(ValueError, match="ended"):
        run.queue_manual_action("02", Direction.WEST)
    assert run.history.to_json() == saved
    ReplayTimeline.from_json(saved)


def test_global_planner_stop_is_terminal_and_has_no_tick():
    run = GridWorldSimulation(
        GridWorld(width=2, height=2, obstacles=()),
        drone_count=1,
        search_strategy=SearchStrategy.INFORMATION_GAIN,
    )
    run.set_mode("01", OperationalMode.AUTO)
    run.autonomous_step("01")
    assert run.frame().status is MissionStatus.PLANNER_EXHAUSTED
    assert run.frame().tick == 0
    assert [event.kind for event in run.history.events] == ["mode", "stop", "terminal"]
    ReplayTimeline.from_json(run.history.to_json())


@pytest.mark.parametrize("mutation", ["missing", "wrong_status", "extra_action"])
def test_stop_requires_immediate_matching_terminal_event(mutation):
    run = GridWorldSimulation(
        GridWorld(width=2, height=2, obstacles=()),
        drone_count=1,
        search_strategy=SearchStrategy.INFORMATION_GAIN,
    )
    run.set_mode("01", OperationalMode.AUTO)
    run.autonomous_step("01")
    saved = run.history.to_json()
    data = json.loads(saved)
    if mutation == "missing":
        data["events"].pop()
        data["snapshots"][-1]["event_sequence"] -= 1
        data["snapshots"][-1]["frame"]["status"] = "ACTIVE"
    elif mutation == "wrong_status":
        data["events"][-1]["details"] = [["status", "BUDGET EXHAUSTED"]]
        data["snapshots"][-1]["frame"]["status"] = "BUDGET EXHAUSTED"
    else:
        extra_event = dict(data["events"][-2])
        extra_event.update(
            sequence=data["events"][-1]["sequence"],
            kind="mode",
            details=[["mode", "MANUAL"]],
        )
        data["events"][-1]["sequence"] += 1
        data["events"].insert(-1, extra_event)
        data["snapshots"][-1]["event_sequence"] += 1
        data["snapshots"][-1]["frame"]["drones"][0]["mode"] = "MANUAL"
    with pytest.raises(ValueError):
        ReplayTimeline.from_json(json.dumps(data))
    assert run.history.to_json() == saved


def test_budget_terminal_cannot_substitute_for_a_planner_stop():
    run = simulation(max_ticks=1)
    run.step(Direction.EAST)
    saved = run.history.to_json()
    data = json.loads(saved)
    data["events"][-1]["details"] = [["status", "PLANNER EXHAUSTED"]]
    data["snapshots"][-1]["frame"]["status"] = "PLANNER EXHAUSTED"
    with pytest.raises(ValueError, match="cause"):
        ReplayTimeline.from_json(json.dumps(data))
    assert run.history.to_json() == saved


def test_noop_and_rejected_actions_do_not_append_history():
    run = simulation()
    run.set_mode("01", OperationalMode.MANUAL)
    run.fleet_round()
    assert len(run.history.snapshots) == 1
    assert run.history.events == ()
    run.set_mode("01", OperationalMode.IDLE)
    saved = run.history.to_json()
    with pytest.raises(ValueError):
        run.step(Direction.EAST)
    with pytest.raises(ValueError):
        run.queue_manual_action("01", Direction.EAST)
    with pytest.raises(ValueError):
        run.step("upwards", drone_id="02")
    assert run.history.to_json() == saved


def test_empty_history_and_seek_endpoints_and_stable_snapshot_references():
    run = simulation()
    timeline = ReplayTimeline.from_json(run.history.to_json())
    assert timeline.snapshot(-500) is timeline.snapshots[0]
    assert timeline.snapshot(500) is timeline.snapshots[0]
    run.step()
    assert len(timeline.snapshots) == 1
    assert timeline.snapshots[0].frame.tick == 0
    assert run.history.snapshot(500).frame.tick == 1
    with pytest.raises(ValueError):
        timeline.snapshot(True)


def test_snapshot_arrays_cannot_be_mutated_or_made_writable():
    run = trace()
    snapshot = run.history.snapshots[0]
    with pytest.raises(ValueError):
        snapshot.belief.probabilities[0, 0] = 1
    with pytest.raises(ValueError):
        snapshot.belief.probabilities.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        snapshot.index = 20
    loaded = ReplayTimeline.from_json(run.history.to_json())
    with pytest.raises(ValueError):
        loaded.snapshots[-1].belief.probabilities.setflags(write=True)


@pytest.mark.parametrize("action", ["scan", "auto", "fleet", "manual", "mode"])
def test_capacity_rejection_precedes_state_rng_and_queue_mutation(action):
    first, control = simulation(history_capacity=2), simulation(history_capacity=2)
    if action in {"auto", "fleet"}:
        first.set_mode("01", OperationalMode.AUTO)
        control.set_mode("01", OperationalMode.AUTO)
    else:
        first.set_mode("03", OperationalMode.IDLE)
        control.set_mode("03", OperationalMode.IDLE)
    if action == "fleet":
        first.queue_manual_action("02", Direction.WEST)
        control.queue_manual_action("02", Direction.WEST)
    old_frame = first.frame()
    old_json = first.history.to_json()
    with pytest.raises(HistoryCapacityError, match="history is full"):
        if action == "scan":
            first.scan("02")
        elif action == "auto":
            first.autonomous_step("01")
        elif action == "fleet":
            first.fleet_round()
        elif action == "manual":
            first.step(Direction.EAST)
        else:
            first.set_mode("03", OperationalMode.AUTO)
    assert first.frame() == old_frame
    assert first.history.to_json() == old_json
    assert first._sensor._random.getstate() == control._sensor._random.getstate()
    assert first._planner._random.getstate() == control._planner._random.getstate()
    assert first._manual_requests == control._manual_requests


def test_public_archive_excludes_hidden_target_rng_and_pending_queue():
    run = trace()
    data = run.history.to_json()
    for private in (
        "objective_position",
        '"random":',
        "reservations",
        "manual_requests",
    ):
        assert private not in data
    # Preparing/cancelling an uncommitted action is not an action event/boundary.
    saved = data
    run.queue_manual_action("02", Direction.SOUTH)
    run.clear_manual_action("02")
    assert run.history.to_json() == saved


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data.update(version=2),
        lambda data: data.update(version=True),
        lambda data: data.update(unexpected="hidden state"),
        lambda data: data.update(snapshots=[]),
        lambda data: data["snapshots"][0].update(index=1),
        lambda data: data["snapshots"][1].update(index=0),
        lambda data: data["events"][0].update(sequence=2),
        lambda data: data["events"][0].update(boundary=2),
        lambda data: data["events"][0].update(tick=True),
        lambda data: data["events"][0].update(kind="teleport"),
        lambda data: data["snapshots"][-1]["frame"].update(tick=100000),
        lambda data: data["snapshots"][-1]["frame"]["drones"][0].update(
            position=[5, 3]
        ),
        lambda data: data["snapshots"][-1]["belief"]["probabilities"][0].__setitem__(
            0, float("nan")
        ),
        lambda data: data["snapshots"][-1]["belief"]["probabilities"][0].__setitem__(
            0, -0.1
        ),
        lambda data: data["snapshots"][-1]["belief"]["stats"].update(entropy_bits=50),
        lambda data: data["snapshots"][-1]["observations"][0].update(sequence_number=2),
        lambda data: data["snapshots"][-1]["observations"][0].update(
            positive=not data["snapshots"][-1]["observations"][0]["positive"]
        ),
        lambda data: data["snapshots"][-1].update(observations=[]),
    ],
)
def test_invalid_loads_are_rejected_without_mutating_live_state(mutation):
    run = trace()
    saved = run.history.to_json()
    data = json.loads(saved)
    mutation(data)
    with pytest.raises(ValueError):
        ReplayTimeline.from_json(json.dumps(data))
    assert run.history.to_json() == saved


def test_duplicate_json_fields_and_truncated_json_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        ReplayTimeline.from_json('{"version":1,"version":1,"snapshots":[],"events":[]}')
    with pytest.raises(ValueError):
        ReplayTimeline.from_json('{"version":')


def test_boundary_nesting_is_balanced_when_planner_raises():
    run = simulation()
    run.set_mode("01", OperationalMode.AUTO)

    class BrokenPlanner:
        def decide(self, state):
            raise RuntimeError("planner failed")

    planner = run._planner
    run._planner = BrokenPlanner()
    with pytest.raises(RuntimeError, match="failed"):
        run.autonomous_step("01")
    assert run._capture_depth == 0
    run._planner = planner
    run.autonomous_step("01")
    assert run.history.snapshots[-1].frame.tick == 1


def test_negative_core_seed_round_trips_without_narrowing_world_contract():
    run = GridWorldSimulation(
        GridWorld(width=6, height=4, seed=-1, obstacles=()),
        drone_count=2,
        search_strategy=SearchStrategy.FRONTIER,
    )
    run.step(Direction.EAST)
    run.scan("02")
    run.set_mode("01", OperationalMode.AUTO)
    run.fleet_round()
    saved = run.history.to_json()
    loaded = ReplayTimeline.from_json(saved)
    assert loaded.to_json() == saved
    assert all(snapshot.frame.seed == -1 for snapshot in loaded.snapshots)


def test_planner_metadata_cannot_claim_stop_for_a_committed_frontier_scan():
    run = GridWorldSimulation(
        GridWorld(width=6, height=4, obstacles=()),
        drone_count=1,
        search_strategy=SearchStrategy.FRONTIER,
    )
    run.set_mode("01", OperationalMode.AUTO)
    run.autonomous_step("01")
    data = json.loads(run.history.to_json())
    data["snapshots"][-1]["last_planner_decision"]["action"]["type"] = "stop"
    with pytest.raises(ValueError, match="metadata|STOP"):
        ReplayTimeline.from_json(json.dumps(data))


def test_stale_planner_metadata_survives_direct_auto_scans_manual_and_mode_calls():
    run = GridWorldSimulation(
        GridWorld(width=6, height=4, obstacles=()),
        drone_count=2,
        search_strategy=SearchStrategy.FRONTIER,
    )
    run.set_mode("01", OperationalMode.AUTO)
    run.autonomous_step("01")  # planner scan
    run.autonomous_step("01")  # planner move
    decision = run.last_planner_decision
    run.scan("01")  # public direct scan, even though the drone is AUTO
    assert run.last_planner_decision == decision
    run.scan("02")
    run.set_mode("01", OperationalMode.MANUAL)
    run.step(Direction.SOUTH)
    assert run.last_planner_decision == decision
    saved = run.history.to_json()
    assert ReplayTimeline.from_json(saved).to_json() == saved
    data = json.loads(saved)
    data["snapshots"][-1]["last_planner_decision"]["reason"] = (
        "not an executed decision"
    )
    with pytest.raises(ValueError, match="without an AUTO action"):
        ReplayTimeline.from_json(json.dumps(data))
