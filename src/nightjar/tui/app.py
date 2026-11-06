"""Nightjar's first terminal application (Textual + Rich)."""

import asyncio

from rich.text import Text
from typing import Awaitable, Callable, Literal

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.widgets import Footer, Static

from nightjar.core.demo import DemoSimulation, MAX_TICK
from nightjar.core.mission import MissionConfig, create_simulation
from nightjar.core.provider import GridWorldSimulation, MissionStatus
from nightjar.core.replay import HistoryCapacityError, MissionSnapshot, ReplayTimeline
from nightjar.core.world import Direction
from nightjar.services.hybrid import ControlDeniedError, HybridMissionController
from nightjar.tui.map_widget import MapWidget
from nightjar.tui.awareness import build_awareness, merge_room_entries
from nightjar.tui.drone_identity import drone_color, drone_marker
from nightjar.tui.comparison import ComparisonScreen
from nightjar.tui.mission_screens import MissionConfigScreen
from nightjar.tui.presentation import (
    MissionSummaryScreen,
    coverage,
    evidence_text,
    progress_bar,
    room_name,
)


class NightjarApp(App[None]):
    TITLE = "NIGHTJAR"
    SUB_TITLE = "MISSION CONFIGURATION / SIM LAB"
    CSS_PATH = "nightjar.tcss"

    BINDINGS = [
        Binding("space", "toggle_play", "Play / Pause"),
        Binding("n", "step", "Step"),
        Binding("w", "move('north')", "Move North"),
        Binding("a", "move('west')", "Move West"),
        Binding("s", "move('south')", "Move South"),
        Binding("d", "move('east')", "Move East"),
        Binding("e", "scan", "Sensor Scan"),
        Binding("h", "layer('belief')", "Heatmap"),
        Binding("c", "layer('coverage')", "Coverage"),
        Binding("p", "layer('paths')", "Paths"),
        Binding("tab", "next_agent", "Next drone", priority=True),
        Binding("1", "select_drone('01')", "RAVEN"),
        Binding("2", "select_drone('02')", "GHOST"),
        Binding("3", "select_drone('03')", "VIPER"),
        Binding("m", "toggle_control", "Toggle manual / auto"),
        Binding("i", "set_control('IDLE')", "Idle control"),
        Binding("r", "toggle_replay", "Replay"),
        Binding("b", "mission_summary", "Brief / Debrief"),
        Binding("v", "comparison", "Compare policies"),
        Binding("t", "mission_milestones", "Milestones"),
        Binding("g", "toggle_drone_icons", "Unit IDs"),
        Binding("left", "seek(-1)", "Back", show=False),
        Binding("right", "seek(1)", "Forward", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        mode: Literal["mission", "demo", "gridworld"] = "mission",
        gridworld_simulation: GridWorldSimulation | None = None,
        mission_config: MissionConfig | None = None,
    ) -> None:
        super().__init__()
        if mode not in {"mission", "demo", "gridworld"}:
            raise ValueError(f"unsupported simulation mode: {mode!r}")
        self.mode = "demo" if mode == "demo" else "gridworld"
        self._show_configuration = mode == "mission" and mission_config is None
        self.mission_config = mission_config or MissionConfig()
        self.sim = DemoSimulation()
        self.gridworld_simulation = (
            gridworld_simulation
            if gridworld_simulation is not None
            else create_simulation(self.mission_config)
        )
        self._controller = HybridMissionController(self.gridworld_simulation)
        self._command_lock = asyncio.Lock()
        self._pending_commands = 0
        self._generation = 0
        self._configuration_pending = self._show_configuration
        self._summary_open = False
        self._comparison_open = False
        self.animal_icons = True
        self._seen_room_entries: set[int] = set()
        self._play_requested = False
        self._play_request_revision = 0
        self.tick = 0
        self.playing = False
        self.replay_mode = False
        self._replay_timeline: ReplayTimeline | None = None
        self._replay_index = 0
        self.layer = "terrain" if self.mode == "gridworld" else "belief"
        self.selected_agent = 0
        self.selected_drone_id = "01"
        initial_events = self._controller.live_snapshot.frame.events
        self._ui_events = list(initial_events)
        self._seen_provider_events = set(initial_events)

    def compose(self) -> ComposeResult:
        mode_label = "GRIDWORLD MODE" if self.mode == "gridworld" else "DEMO MODE"
        yield Static(
            f" ◈ NIGHTJAR    /  01     AUTONOMOUS SEARCH SIMULATION     /  {mode_label}",
            id="masthead",
        )
        with Horizontal(id="workspace"):
            with Vertical(id="map_panel"):
                map_label = (
                    "NEUTRAL TERRAIN"
                    if self.mode == "gridworld"
                    else "PROBABILITY GRID"
                )
                yield Static(
                    f" ┌ SECTOR ALPHA / {map_label}                       "
                    f"{self.mission_config.width} × {self.mission_config.height}",
                    id="map_title",
                    classes="section_title",
                )
                if self.mode == "gridworld":
                    yield Static(id="mission_focus")
                yield MapWidget(id="map")
                legend = (
                    " ▓▓ WALL  01-10 DRONES  WASD MOVE  [E] SCAN  "
                    "[H] BELIEF / RELATIVE INTENSITY  [C] COVER  [P] PATH"
                    if self.mode == "gridworld"
                    else " LOW  ░░  ▒▒  ██   ▓▓ WALL     01 DRONE     [H] HEAT  [C] COVER  [P] PATH"
                )
                yield Static(legend, id="legend")
            with Vertical(id="telemetry_panel"):
                yield Static("┌ AGENT TELEMETRY", classes="section_title")
                yield Static(id="agents")
                status_title = (
                    "┌ SELECTED DRONE" if self.mode == "gridworld" else "┌ BELIEF STATE"
                )
                yield Static(status_title, classes="section_title")
                yield Static(id="metrics")
        with Horizontal(id="bottom_panels"):
            with Vertical(id="events_panel"):
                yield Static("┌ SYSTEM EVENT LOG", classes="section_title")
                if self.mode == "gridworld":
                    yield Static(id="evidence")
                yield Static(id="events")
            with Vertical(id="replay_panel"):
                yield Static("┌ MISSION REPLAY", classes="section_title")
                yield Static(id="timeline")
        mode_note = (
            " GRIDWORLD  •  WASD/E manual  M manual/auto  N step  Space run  "
            "H belief  Tab/1-3 select"
            if self.mode == "gridworld"
            else " TERMINAL-FIRST PROTOTYPE  •  Synthetic belief field, scripted agent routes  •  No external sensors"
        )
        yield Static(mode_note, id="mode_note")
        yield Footer()

    def on_mount(self) -> None:
        self._set_compact_layout(self.size.width, self.size.height)
        self._mission_timer = self.set_interval(0.22, self._timer_tick)
        self._refresh_screen()
        if not self._configuration_pending and self.mode == "gridworld":
            self._submit_command(self._controller.initialize, "INITIALIZE")
        if self._show_configuration:
            self.push_screen(
                MissionConfigScreen(self.mission_config),
                self._on_mission_configured,
            )

    def on_resize(self, event: Resize) -> None:
        self._set_compact_layout(event.size.width, event.size.height)

    def _set_compact_layout(self, width: int, height: int) -> None:
        # A configuration screen may cover the mission when the terminal resizes.
        # Keep the underlying screen ready for launch as well as the visible one.
        for screen in self.screen_stack:
            screen.set_class(height < 36 or width < 100, "compact")
            screen.set_class(self.mode == "gridworld", "gridworld")

    def _on_mission_configured(self, config: MissionConfig | None) -> None:
        if config is None:
            return
        self.mission_config = config
        self.gridworld_simulation = create_simulation(config)
        self._controller = HybridMissionController(self.gridworld_simulation)
        self._generation += 1
        self._configuration_pending = False
        self.mode = "gridworld"
        self.tick = 0
        self.playing = False
        self._play_requested = False
        self.replay_mode = False
        self._replay_timeline = None
        self._replay_index = 0
        self.selected_drone_id = "01"
        self.layer = "terrain"
        self._set_compact_layout(self.size.width, self.size.height)
        initial_events = self._controller.live_snapshot.frame.events
        self._ui_events = list(initial_events)
        self._seen_provider_events = set(initial_events)
        self._submit_command(self._controller.initialize, "INITIALIZE")
        self._seen_room_entries.clear()
        self._refresh_screen()

    def _mission_available(self) -> bool:
        return (
            self.mode == "gridworld"
            and not self._configuration_pending
            and not self._summary_open
            and not self._comparison_open
        )

    def _timer_tick(self) -> None:
        if self.mode == "gridworld":
            if self.replay_mode:
                self.playing = False
                if not self._pending_commands:
                    self._play_requested = False
                return
            if (
                not self._mission_available()
                or not self.playing
                or self.replay_mode
                or self._pending_commands
                or self._controller.busy
            ):
                return
            controller = self._controller
            self._submit_command(
                lambda: controller.fleet_round(should_run=lambda: self.playing),
                "AUTO FLEET",
            )
            return
        if self.playing:
            self.tick = min(MAX_TICK, self.tick + 1)
            if self.tick == MAX_TICK:
                self.playing = False
            self._refresh_screen()

    def _sync_controller(self) -> None:
        controller = self._controller
        self.selected_drone_id = controller.selected_drone_id
        self.replay_mode = controller.replay_mode
        self._replay_index = controller.replay_index
        self._replay_timeline = controller.replay_history
        live = controller.live_snapshot.frame
        if (
            self.replay_mode
            or live.status is not MissionStatus.ACTIVE
            or not any(drone.mode.value == "AUTO" for drone in live.drones)
        ):
            self.playing = False
            if self._pending_commands <= 1 or live.status is not MissionStatus.ACTIVE:
                self._play_requested = False

    def _submit_command(
        self, command: Callable[[], Awaitable[object]], label: str
    ) -> None:
        """Reserve explicit input synchronously; serialize without blocking the UI."""
        if not self._mission_available():
            return
        generation = self._generation
        self._pending_commands += 1

        async def perform() -> None:
            try:
                async with self._command_lock:
                    if generation != self._generation:
                        return
                    previous_selection = self.selected_drone_id
                    try:
                        await command()
                    except HistoryCapacityError as error:
                        self.playing = False
                        self._play_requested = False
                        self._ui_events.append(f"HISTORY FULL / {error}")
                    except ControlDeniedError as error:
                        self._ui_events.append(f"{label} DENIED / {error}")
                    except (ValueError, RuntimeError) as error:
                        self.playing = False
                        self._play_requested = False
                        detail = (
                            "MISSION INACTIVE"
                            if label == "SCAN"
                            and self._controller.live_snapshot.frame.status
                            is not MissionStatus.ACTIVE
                            else str(error)
                        )
                        self._ui_events.append(f"{label} DENIED / {detail}")
                    finally:
                        if generation == self._generation:
                            self._sync_controller()
                    if (
                        previous_selection != self.selected_drone_id
                        and not self.replay_mode
                    ):
                        drone = self._controller.live_snapshot.frame.drone(
                            self.selected_drone_id
                        )
                        self._ui_events.append(
                            f"[{self._controller.live_snapshot.frame.tick:04d}]  "
                            f"SELECTED {drone.identifier} {drone.callsign}"
                        )
                    if self.is_running:
                        self._refresh_screen()
            finally:
                self._pending_commands -= 1

        self.run_worker(perform(), group="mission-commands", exclusive=False)

    async def wait_for_commands(self) -> None:
        """Wait for submitted explicit work, useful for deterministic UI tests."""
        await self.workers.wait_for_complete()
        if self.mode == "gridworld":
            self._sync_controller()

    def action_set_control(self, mode: str) -> None:
        if not self._mission_available():
            return
        controller = self._controller
        self._submit_command(lambda: controller.set_control(mode), "CONTROL")

    def action_toggle_control(self) -> None:
        if not self._mission_available():
            return
        self._submit_command(self._controller.toggle_control, "CONTROL")

    def _gridworld_snapshot(self) -> MissionSnapshot:
        return self._controller.view_snapshot

    def _refresh_screen(self) -> None:
        if self.mode == "gridworld":
            self._refresh_gridworld_screen(self._gridworld_snapshot())
            return

        frame = self.sim.frame(self.tick)
        self.query_one("#map", MapWidget).show_frame(
            frame, self.layer, self.selected_agent
        )
        layer_labels = {
            "belief": "PROBABILITY GRID",
            "coverage": "VISITED CELLS",
            "paths": "TRAVEL HISTORY",
        }
        self.query_one("#map_title", Static).update(
            f" ┌ SECTOR ALPHA / {layer_labels[self.layer]}                      32 × 16"
        )
        agent_lines = []
        for i, agent in enumerate(frame.agents):
            arrow = "▶" if i == self.selected_agent else " "
            bar = "▰" * (agent.energy // 10) + "▱" * (10 - agent.energy // 10)
            agent_lines.extend(
                [
                    f" {arrow} [{agent.identifier}] {agent.callsign}",
                    f"   {agent.status:<10} {agent.energy:3d}%",
                    f"   [green]{bar}[/green]",
                    "",
                ]
            )
        self.query_one("#agents", Static).update("\n".join(agent_lines))
        self.query_one("#metrics", Static).update(
            f" ENTROPY     {frame.entropy_bits:6.2f} bits\n"
            f" COVERAGE    {frame.coverage_pct:5.1f}%\n"
            f" AGENTS      {len(frame.agents):>5}\n"
            f" MAP         [amber]SYNTHETIC[/amber]\n"
            f" TICK        {self.tick:5d}"
        )
        self.query_one("#events", Static).update("\n".join(frame.events))
        progress = round(24 * self.tick / MAX_TICK)
        track = "━" * progress + "●" + "─" * (24 - progress)
        state = (
            "REPLAY" if self.replay_mode else "RUNNING" if self.playing else "PAUSED"
        )
        self.query_one("#timeline", Static).update(
            f" RUN 001  /  TICK {self.tick:04d}\n\n"
            f" [green]{track}[/green]\n"
            f" 0000                      {MAX_TICK:04d}\n\n"
            f" STATE: {state}\n"
            " [dim]R replay  ← / → seek  Space live[/dim]"
        )

    def _refresh_gridworld_screen(self, snapshot: MissionSnapshot) -> None:
        frame = snapshot.frame
        history = self._controller.replay_history or self._controller.live_history
        awareness = build_awareness(history, snapshot)
        self.tick = frame.tick
        selected = frame.drone(self.selected_drone_id)
        observations = snapshot.observations
        selected_observation = next(
            (
                observation
                for observation in reversed(observations)
                if observation.drone_id == selected.identifier
            ),
            None,
        )
        last_observation = observations[-1] if observations else None
        self.query_one("#map", MapWidget).show_gridworld_frame(
            frame,
            self.layer,
            self.selected_drone_id,
            snapshot.belief,
            last_observation=last_observation,
            planner_decision=snapshot.last_planner_decision,
            animal_icons=self.animal_icons,
            styled_drones=True,
            target_owner=awareness.target_owner,
        )
        layer_labels = {
            "terrain": "NEUTRAL TERRAIN",
            "belief": "BELIEF HEATMAP",
            "coverage": "VISITED CELLS",
            "paths": "TRAVEL HISTORY",
        }
        self.query_one("#map_title", Static).update(
            f" ┌ {frame.mission_id} / {layer_labels[self.layer]}                       "
            f"{frame.width} × {frame.height}"
        )
        self.query_one("#masthead", Static).update(
            f" ◈ NIGHTJAR    /  {frame.mission_id}     /  GRIDWORLD MISSION"
        )
        self.query_one("#mode_note", Static).update(
            f" {frame.operation_name}  •  {frame.scenario.replace('_', ' ').upper()}  "
            f"•  SEED {frame.seed}"
        )
        telemetry = Text()
        for drone in frame.drones:
            marker = "▶" if drone.identifier == self.selected_drone_id else " "
            telemetry.append(
                f" {marker} {drone_marker(drone.identifier, animal_icons=self.animal_icons)} "
                f"[{drone.identifier}] {drone.callsign}  {drone.mode.value}\n",
                style=f"bold {drone_color(drone.identifier, selected=drone.identifier == self.selected_drone_id)}",
            )
            activity = {
                "MANUAL": "OPERATOR CONTROL",
                "AUTO": "RECONNAISSANCE",
                "IDLE": "PARKED",
            }[drone.mode.value]
            location = room_name(frame, drone.position)
            room_coverage = next(
                (room for room in awareness.room_coverage if room.name == location),
                None,
            )
            visits = f" / {room_coverage.fraction:.0%} visited" if room_coverage else ""
            telemetry.append(
                f"   {location}{visits}\n"
                f"   ({drone.position[0]:02d},{drone.position[1]:02d}) {activity}\n"
            )
        self.query_one("#agents", Static).update(telemetry)
        if selected.last_result is None or selected.last_direction is None:
            movement = "NOT STARTED"
        elif selected.last_result.moved:
            movement = f"MOVED {selected.last_direction.value.upper()}"
        else:
            reason = selected.last_result.blocked_by
            if reason is None:
                raise RuntimeError("blocked GridWorld step did not include a reason")
            reason_label = (
                "WALL" if reason.value == "obstacle" else reason.value.upper()
            )
            if reason.value == "drone":
                reason_label = "DRONE COLLISION"
            movement = f"BLOCKED BY {reason_label}"
        sensor_status = (
            "READY"
            if selected_observation is None
            else f"LAST {selected_observation.sequence_number:03d} "
            f"{'POSITIVE' if selected_observation.positive else 'NEGATIVE'}"
        )
        last_reading = (
            "NONE"
            if last_observation is None
            else (
                "[amber]POSITIVE[/amber]" if last_observation.positive else "NEGATIVE"
            )
        )
        sensor_preset = snapshot.sensor_config.preset.value.replace("_", " ").upper()
        belief = snapshot.belief.stats
        map_x, map_y = belief.map_position
        metrics = (
            f" SELECTED    {selected.identifier} {selected.callsign}\n"
            f" POSITION    ({selected.position[0]:02d},{selected.position[1]:02d})\n"
            f" STATUS      {selected.mode.value}\n"
            f" PLANNER     {snapshot.search_strategy.label}\n"
            f" SENSOR      {sensor_status}\n"
            f" PRESET      {sensor_preset}\n"
            f" OBSERVATIONS {len(observations):4d}\n"
            f" LAST READING {last_reading}\n"
            f" BELIEF H    {belief.entropy_bits:6.2f} bits\n"
            f" ΔH / PRIOR  {belief.entropy_change_bits:+6.2f} bits\n"
            f" MAP CELL    ({map_x:02d},{map_y:02d})\n"
            f" MAP PROB    {belief.map_probability:6.1%}\n"
            f" CANDIDATES  {belief.candidate_count:5d}\n"
            f" MOVES       {selected.moves:5d}\n"
            f" TICK        {frame.tick:5d}\n"
            f" BUDGET      {frame.max_ticks if frame.max_ticks is not None else 'OPEN'}\n"
            f" MISSION     {frame.status.value}\n"
            f" RESULT      {movement}"
        )
        decision = snapshot.last_planner_decision
        self.query_one("#metrics", Static).update(metrics)
        budget = str(frame.max_ticks) if frame.max_ticks is not None else "OPEN"
        phase = (
            "ENDED / B DEBRIEF"
            if frame.status is not MissionStatus.ACTIVE
            else "1 OBJECTIVE / B BRIEF"
        )
        self.query_one("#mission_focus", Static).update(
            Text(
                f" {phase}  {frame.tick}/{budget} TICKS\n"
                f" COVERAGE {progress_bar(coverage(snapshot), 12)} {coverage(snapshot):.0%}",
                no_wrap=True,
                overflow="crop",
            )
        )
        self.query_one("#legend", Static).update(
            Text(
                " H RELATIVE INTENSITY / C COVER / P PATH\n"
                " T MILESTONES / G UNIT IDS / TINT LATEST SCAN",
                no_wrap=True,
                overflow="crop",
            )
        )
        self.query_one("#evidence", Static).update(evidence_text(snapshot))
        if self.replay_mode:
            self.query_one("#events", Static).update(
                "\n".join(
                    merge_room_entries(list(frame.events), awareness.room_entries[-3:])[
                        -8:
                    ]
                )
            )
        else:
            new_events = [
                event
                for event in frame.events
                if event not in self._seen_provider_events
            ]
            self._seen_provider_events = set(frame.events)
            new_entries = tuple(
                entry
                for entry in awareness.room_entries
                if entry.event_sequence not in self._seen_room_entries
            )
            self._seen_room_entries.update(
                entry.event_sequence for entry in new_entries
            )
            self._ui_events.extend(new_events)
            self._ui_events = merge_room_entries(self._ui_events, new_entries)
            self.query_one("#events", Static).update("\n".join(self._ui_events[-8:]))
        if decision is None:
            planner_summary = " FLEET PLAN: READY"
        else:
            action_label = decision.action.type.value.upper()
            if decision.action.direction is not None:
                action_label += f" {decision.action.direction.value.upper()}"
            if decision.target is not None:
                action_label += (
                    f" → ({decision.target[0]:02d},{decision.target[1]:02d})"
                )
            planner_summary = f" FLEET PLAN: {action_label}"
            if decision.expected_information_gain_bits is not None:
                planner_summary += (
                    f"\n IG {decision.expected_information_gain_bits:.4f} bits"
                )
            if decision.travel_cost is not None:
                planner_summary += f" / COST {decision.travel_cost}"
        state = "RUNNING" if self.playing else "PAUSED"
        replay_label = (
            f"REPLAY {self._replay_index + 1}/{len(self._replay_timeline.snapshots)} / READ ONLY"
            if self.replay_mode and self._replay_timeline is not None
            else f"FLEET {state}"
        )
        self.query_one("#timeline", Static).update(
            f" GRIDWORLD  /  TICK {frame.tick:04d}\n"
            f" {replay_label}\n"
            " [dim]Space run  N step  R replay  ←/→[/dim]\n"
            f" {snapshot.search_strategy.label}\n"
            f"{planner_summary}\n"
            f" STATUS: {frame.status.value}"
            + (" / B" if frame.status is not MissionStatus.ACTIVE else "")
        )

    def action_toggle_play(self) -> None:
        if self.mode == "gridworld":
            if not self._mission_available():
                return
            self._play_request_revision += 1
            revision = self._play_request_revision
            requested = not self._play_requested
            self._play_requested = requested
            if not requested:
                self.playing = False
            controller = self._controller

            async def apply_play() -> None:
                # An older rejected resume must not cancel a newer run request.
                if revision != self._play_request_revision:
                    return
                if controller.replay_mode:
                    self.playing = False
                    self._play_requested = False
                    return
                # N, replay or a later pause can supersede an earlier queued
                # resume while its controller barrier is still pending.
                if requested and not self._play_requested:
                    return
                if requested and await controller.can_run() and self._play_requested:
                    self.playing = True
                else:
                    self.playing = False
                    if requested:
                        self._play_requested = False
                        self._ui_events.append(
                            "FLEET RUN DENIED / NO ACTIVE AUTO DRONES"
                        )

            self._submit_command(apply_play, "FLEET RUN")
            self._refresh_screen()
            return
        self.replay_mode = False
        if self.tick >= MAX_TICK:
            self.tick = 0
        self.playing = not self.playing
        self._refresh_screen()

    def action_step(self) -> None:
        if self.mode == "gridworld":
            if not self._mission_available():
                return
            self.playing = False
            self._play_request_revision += 1
            self._play_requested = False
            self._submit_command(self._controller.fleet_round, "FLEET STEP")
            return
        self.playing = False
        self.tick = min(MAX_TICK, self.tick + 1)
        self._refresh_screen()

    def action_move(self, direction: str) -> None:
        if not self._mission_available():
            return
        controller = self._controller
        self._submit_command(lambda: controller.move(Direction(direction)), "MOVEMENT")

    def action_scan(self) -> None:
        if not self._mission_available():
            return
        self._submit_command(self._controller.scan, "SCAN")

    def action_select_drone(self, drone_id: str) -> None:
        if self.mode == "gridworld":
            if not self._mission_available():
                return
            # Invalid keyboard roster entries are harmless, and this cached read
            # cannot observe an in-flight provider round.
            if drone_id not in {
                d.identifier for d in self._gridworld_snapshot().frame.drones
            }:
                return
            controller = self._controller
            self._submit_command(lambda: controller.select(drone_id), "SELECT")
        else:
            index = int(drone_id) - 1
            if 0 <= index < 3:
                self.selected_agent = index
                self._refresh_screen()

    def action_layer(self, layer: str) -> None:
        if self._summary_open or self._comparison_open:
            return
        if self.mode == "demo" and layer in {"belief", "coverage", "paths"}:
            self.layer = layer
            self._refresh_screen()
        elif self.mode == "gridworld":
            if layer == "belief":
                self.layer = "terrain" if self.layer == "belief" else "belief"
            elif layer in {"coverage", "paths"}:
                self.layer = layer
            self._refresh_screen()

    def action_next_agent(self) -> None:
        if self._comparison_open:
            if isinstance(self.screen, ComparisonScreen):
                self.screen.action_switch_policy()
            return
        if self.mode == "gridworld":
            self._submit_command(self._controller.next_drone, "SELECT")
            return
        self.selected_agent = (self.selected_agent + 1) % 3
        self._refresh_screen()

    def action_toggle_replay(self) -> None:
        if self.mode == "gridworld":
            if not self._mission_available():
                return
            self.playing = False
            self._play_request_revision += 1
            self._play_requested = False
            self._submit_command(self._controller.toggle_replay, "REPLAY")
            return
        self.replay_mode = not self.replay_mode
        self.playing = False
        self._refresh_screen()

    def action_seek(self, direction: int) -> None:
        if self.mode == "gridworld":
            if not self._mission_available():
                return
            controller = self._controller

            async def seek_view() -> None:
                controller.seek(direction)

            self._submit_command(seek_view, "SEEK")
            return
        if self.mode == "demo" and self.replay_mode:
            self.tick = max(0, min(MAX_TICK, self.tick + direction))
            self._refresh_screen()

    def action_mission_summary(self) -> None:
        self._open_mission_summary(milestones_only=False)

    def action_mission_milestones(self) -> None:
        self._open_mission_summary(milestones_only=True)

    def action_toggle_drone_icons(self) -> None:
        if not self._mission_available():
            return
        self.animal_icons = not self.animal_icons
        self._refresh_screen()

    def _open_mission_summary(self, *, milestones_only: bool) -> None:
        """Pause now, then present the committed view after accepted commands finish."""
        if not self._mission_available():
            return
        self.playing = False
        self._play_requested = False
        self._play_request_revision += 1

        async def show_summary() -> None:
            snapshot = self._controller.view_snapshot
            history = self._controller.replay_history or self._controller.live_history
            initial_entropy = history.snapshots[0].belief.stats.entropy_bits
            self.push_screen(
                MissionSummaryScreen(
                    snapshot,
                    initial_entropy,
                    replay=self._controller.replay_mode,
                    field_awareness=build_awareness(history, snapshot),
                    milestones_only=milestones_only,
                ),
                self._summary_closed,
            )

        # Reserve through the same FIFO as manual/replay inputs before blocking
        # subsequent key bindings. An already executing round is allowed to finish.
        self._submit_command(show_summary, "MISSION SUMMARY")
        self._summary_open = True
        self._refresh_screen()

    def _summary_closed(self, _: None) -> None:
        self._summary_open = False
        self.playing = False
        self._play_requested = False
        self._refresh_screen()

    def action_comparison(self) -> None:
        """Pause the mission and enter a fresh, isolated paired experiment."""
        if not self._mission_available():
            return
        self.playing = False
        self._play_requested = False
        self._play_request_revision += 1

        async def show_comparison() -> None:
            self.push_screen(
                ComparisonScreen(self.mission_config), self._comparison_closed
            )

        self._submit_command(show_comparison, "POLICY COMPARISON")
        self._comparison_open = True

    def _comparison_closed(self, _: None) -> None:
        self._comparison_open = False
        self.playing = False
        self._play_requested = False
        self._refresh_screen()
