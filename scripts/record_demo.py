"""Record the deterministic README walkthrough from real Textual app states.

The script uses macOS's Swift toolchain and ImageIO framework; it adds no
application dependencies.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

from nightjar.core.discovery import discovery_state
from nightjar.core.mission import (
    MapPreset,
    MissionConfig,
    ScenarioPreset,
    create_world,
)
from nightjar.core.planning import SearchStrategy
from nightjar.core.provider import (
    GridWorldSimulation,
    MissionStatus,
    OperationalMode,
)
from nightjar.core.sensor import SensorConfig, SensorPreset, SensorType
from nightjar.tui.app import NightjarApp

# Textual's headless driver otherwise sees the inherited NO_COLOR environment and
# renders the capture without the application's approved field colors.
os.environ.pop("NO_COLOR", None)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/demo/media/beacon-search.mp4"
POSTER = ROOT / "docs/demo/media/beacon-search.png"
ENCODER = Path(__file__).with_name("encode_demo_video.swift")
SIZE = (132, 55)


def _path(frame, start: tuple[int, int], target: tuple[int, int]) -> list[str] | None:
    """Find a shortest legal route using only public walls and drone positions."""
    blocked = set(frame.obstacles)
    blocked.update(drone.position for drone in frame.drones if drone.position != start)
    queue = [start]
    routes: dict[tuple[int, int], list[str]] = {start: []}
    directions = ((0, -1, "w"), (1, 0, "d"), (0, 1, "s"), (-1, 0, "a"))
    for x, y in queue:
        if (x, y) == target:
            return routes[(x, y)]
        for dx, dy, key in directions:
            point = (x + dx, y + dy)
            if (
                point in routes
                or point in blocked
                or not (0 <= point[0] < frame.width and 0 <= point[1] < frame.height)
            ):
                continue
            routes[point] = [*routes[(x, y)], key]
            queue.append(point)
    return None


def _swift_sdk_path() -> str:
    command_line_sdks = Path("/Library/Developer/CommandLineTools/SDKs")
    versioned = [
        sdk for sdk in command_line_sdks.glob("MacOSX*.sdk") if sdk.name != "MacOSX.sdk"
    ]
    if versioned:
        return str(
            max(
                versioned,
                key=lambda sdk: tuple(
                    int(component)
                    for component in sdk.stem.removeprefix("MacOSX").split(".")
                ),
            )
        )
    return subprocess.run(
        ["xcrun", "--sdk", "macosx", "--show-sdk-path"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


async def _record_frames(directory: Path) -> list[dict[str, object]]:
    config = MissionConfig(
        operation_name="NIGHTJAR BEACON SEARCH",
        scenario=ScenarioPreset.FACILITY,
        drone_count=3,
        map_preset=MapPreset.STANDARD,
        max_ticks=1200,
        seed=6,
        sensor_preset=SensorPreset.HIGH_RELIABILITY,
        search_strategy=SearchStrategy.FRONTIER,
    )
    simulation = GridWorldSimulation(
        create_world(config),
        drone_count=config.drone_count,
        initial_mode=OperationalMode.MANUAL,
        max_ticks=config.max_ticks,
        operation_name=config.operation_name,
        scenario=config.scenario.value,
        sensor_config=SensorConfig(
            detection_radius=0,
            sensitivity=0.98,
            false_positive_probability=0.02,
            preset=SensorPreset.HIGH_RELIABILITY,
        ),
        search_strategy=config.search_strategy,
    )
    app = NightjarApp(
        mode="gridworld",
        gridworld_simulation=simulation,
        mission_config=config,
    )
    captured: list[dict[str, object]] = []

    async def capture(pilot, name: str, delay: float = 0.065) -> None:
        await pilot.pause()
        svg_path = directory / f"{len(captured):02d}-{name}.svg"
        svg_path.write_text(app.export_screenshot(), encoding="utf-8")
        captured.append({"path": str(svg_path), "delay": delay})

    async with app.run_test(size=SIZE) as pilot:
        app._mission_timer.pause()
        await app.wait_for_commands()
        # Begin only after deployment and a few fleet rounds; the clip should open
        # in active mission control, never on configuration or a static title view.
        for _ in range(6):
            await pilot.press("n")
            await app.wait_for_commands()
        await capture(pilot, "deployed", 0.55)
        candidate_captured = False
        sample_captured = False
        rescanned: set[str] = set()
        last_frame_tick = app._controller.view_snapshot.frame.tick
        for _ in range(config.max_ticks * 3):
            snapshot = app._controller.view_snapshot
            discovery = discovery_state(snapshot)
            if snapshot.frame.status is not MissionStatus.ACTIVE:
                break

            if discovery.candidate_position is not None:
                if not candidate_captured:
                    if app.layer != "belief":
                        await pilot.press("h")
                        await app.wait_for_commands()
                    await capture(pilot, "candidate", 0.6)
                    candidate_captured = True

                await pilot.press("3")
                await app.wait_for_commands()
                snapshot = app._controller.view_snapshot
                candidate = discovery_state(snapshot).candidate_position
                if candidate is not None:
                    frame = snapshot.frame
                    manual = next(
                        drone
                        for drone in frame.drones
                        if drone.mode is OperationalMode.MANUAL
                    )
                    route = _path(frame, manual.position, candidate)
                    if route is not None:
                        for key in route:
                            await pilot.press(key)
                            await app.wait_for_commands()
                            await capture(pilot, "approach")
                        await pilot.press("f")
                        await app.wait_for_commands()
                        checked = app._controller.view_snapshot
                        if checked.frame.status is MissionStatus.CONFIRMED:
                            await capture(pilot, "beacon-verified", 1.0)
                            break

            snapshot = app._controller.view_snapshot
            latest_positive = next(
                (
                    observation
                    for observation in reversed(snapshot.observations)
                    if observation.sensor_type is SensorType.PROXIMITY
                    and observation.positive
                    and observation.observation_id not in rescanned
                ),
                None,
            )
            if latest_positive is not None:
                rescanned.add(latest_positive.observation_id)
                if not sample_captured:
                    if app.layer != "belief":
                        await pilot.press("h")
                        await app.wait_for_commands()
                    sample_captured = True
                await pilot.press(latest_positive.drone_id[-1])
                await app.wait_for_commands()
                await pilot.press("e")
                await app.wait_for_commands()
            else:
                await pilot.press("n")
                await app.wait_for_commands()
            snapshot = app._controller.view_snapshot
            if snapshot.frame.tick - last_frame_tick >= 2:
                await capture(pilot, "search")
                last_frame_tick = snapshot.frame.tick

        final = app._controller.view_snapshot
        if final.frame.status is not MissionStatus.CONFIRMED:
            state = discovery_state(final)
            raise RuntimeError(
                "The deterministic walkthrough did not verify the beacon within "
                f"{config.max_ticks} ticks (stopped at tick {final.frame.tick}; "
                f"{len(final.observations)} scans/checks, "
                f"MAP {final.belief.stats.map_probability:.1%}, "
                f"phase {state.phase.value})."
            )
        if len(captured) < 20 or captured[-1]["delay"] != 1.0:
            raise RuntimeError(
                "The continuous verified mission sequence was not captured."
            )
    return captured


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="nightjar-demo-") as temp:
        directory = Path(temp)
        frames = await _record_frames(directory)
        duration = sum(float(frame["delay"]) for frame in frames)
        if duration > 30:
            raise RuntimeError(
                f"The README walkthrough is {duration:.1f}s; maximum is 30s."
            )
        manifest = directory / "frames.json"
        manifest.write_text(json.dumps(frames), encoding="utf-8")
        temporary_output = directory / "beacon-search.mp4"
        temporary_poster = directory / "beacon-search.png"
        subprocess.run(
            [
                "swift",
                "-sdk",
                _swift_sdk_path(),
                "-module-cache-path",
                str(directory / "swift-module-cache"),
                str(ENCODER),
                str(manifest),
                str(temporary_output),
                str(temporary_poster),
            ],
            check=True,
        )
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temporary_output.replace(OUTPUT)
        temporary_poster.replace(POSTER)
    print(
        f"Recorded {OUTPUT.relative_to(ROOT)} "
        f"({duration:.0f}s across {len(frames)} app states)"
    )


if __name__ == "__main__":
    asyncio.run(main())
