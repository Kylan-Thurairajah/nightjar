"""Nightjar's first terminal application (Textual + Rich)."""

from typing import Callable, Literal

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
from nightjar.tui.map_widget import MapWidget
from nightjar.tui.mission_screens import MissionConfigScreen


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
        self.tick = 0
        self.playing = False
        self.replay_mode = False
        self._replay_timeline: ReplayTimeline | None = None
        self._replay_index = 0
        self.layer = "terrain" if self.mode == "gridworld" else "belief"
        self.selected_agent = 0
        self.selected_drone_id = "01"
        initial_events = self.gridworld_simulation.frame().events
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
        self.set_interval(0.22, self._timer_tick)
        self._refresh_screen()
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

    def _on_mission_configured(self, config: MissionConfig | None) -> None:
        if config is None:
            return
        self.mission_config = config
        self.gridworld_simulation = create_simulation(config)
        self.mode = "gridworld"
        self.tick = 0
        self.playing = False
        self.replay_mode = False
        self._replay_timeline = None
        self._replay_index = 0
        self.selected_drone_id = "01"
        self.layer = "terrain"
        self._set_compact_layout(self.size.width, self.size.height)
        initial_events = self.gridworld_simulation.frame().events
        self._ui_events = list(initial_events)
        self._seen_provider_events = set(initial_events)
        self._refresh_screen()

    def _timer_tick(self) -> None:
        if self.mode == "gridworld":
            if self.replay_mode:
                self.playing = False
                return
            if not self.playing:
                return
            selected = self.gridworld_simulation.frame().drone(self.selected_drone_id)
            if selected.mode.value != "AUTO":
                self.playing = False
                self._refresh_screen()
                return
            self._perform_live_action(
                lambda: self.gridworld_simulation.autonomous_step(
                    self.selected_drone_id
                )
            )
            if self.gridworld_simulation.frame().status is not MissionStatus.ACTIVE:
                self.playing = False
            self._refresh_screen()
            return
        if self.playing:
            self.tick = min(MAX_TICK, self.tick + 1)
            if self.tick == MAX_TICK:
                self.playing = False
            self._refresh_screen()

    def action_set_control(self, mode: str) -> None:
        if self.mode != "gridworld" or self._replay_blocks_mutation():
            return
        if mode != "AUTO":
            self.playing = False
        self._perform_live_action(
            lambda: self.gridworld_simulation.set_mode(self.selected_drone_id, mode)
        )
        self._refresh_screen()

    def action_toggle_control(self) -> None:
        if self.mode != "gridworld" or self._replay_blocks_mutation():
            return
        selected = self.gridworld_simulation.frame().drone(self.selected_drone_id)
        next_mode = "AUTO" if selected.mode.value == "MANUAL" else "MANUAL"
        if next_mode == "MANUAL":
            self.playing = False
        self._perform_live_action(
            lambda: self.gridworld_simulation.set_mode(
                self.selected_drone_id, next_mode
            )
        )
        self._refresh_screen()

    def _replay_blocks_mutation(self) -> bool:
        if self.mode == "gridworld" and self.replay_mode:
            self.playing = False
            return True
        return False

    def _perform_live_action(self, action: Callable[[], object]) -> None:
        """Keep a full replay archive from turning a live shortcut into a crash."""
        try:
            action()
        except HistoryCapacityError as error:
            self.playing = False
            tick = self.gridworld_simulation.frame().tick
            self._ui_events.append(f"[{tick:04d}] HISTORY FULL / {error}")

    def _gridworld_snapshot(self) -> MissionSnapshot:
        if self.replay_mode and self._replay_timeline is not None:
            return self._replay_timeline.snapshot(self._replay_index)
        return self.gridworld_simulation.snapshot()

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
        telemetry: list[str] = []
        for drone in frame.drones:
            marker = "▶" if drone.identifier == self.selected_drone_id else " "
            telemetry.append(
                f" {marker} [{drone.identifier}] {drone.callsign}  {drone.mode.value}"
            )
            telemetry.append(
                f"   ({drone.position[0]:02d},{drone.position[1]:02d})  "
                f"MOVES {drone.moves:03d}"
            )
        self.query_one("#agents", Static).update("\n".join(telemetry))
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
        if self.replay_mode:
            self.query_one("#events", Static).update("\n".join(frame.events))
        else:
            for event in frame.events:
                if event not in self._seen_provider_events:
                    self._ui_events.append(event)
            self._seen_provider_events = set(frame.events)
            self.query_one("#events", Static).update("\n".join(self._ui_events[-8:]))
        if decision is None:
            planner_summary = " PLAN: READY"
        else:
            action_label = decision.action.type.value.upper()
            if decision.action.direction is not None:
                action_label += f" {decision.action.direction.value.upper()}"
            if decision.target is not None:
                action_label += (
                    f" → ({decision.target[0]:02d},{decision.target[1]:02d})"
                )
            planner_summary = f" PLAN: {action_label}"
            if decision.expected_information_gain_bits is not None:
                planner_summary += (
                    f"\n IG {decision.expected_information_gain_bits:.4f} bits"
                )
            if decision.travel_cost is not None:
                planner_summary += f" / COST {decision.travel_cost} ticks"
        state = "RUNNING" if self.playing else "PAUSED"
        replay_label = (
            f"REPLAY {self._replay_index + 1}/{len(self._replay_timeline.snapshots)} / READ ONLY"
            if self.replay_mode and self._replay_timeline is not None
            else state
        )
        self.query_one("#timeline", Static).update(
            f" GRIDWORLD  /  TICK {frame.tick:04d}\n"
            f" {replay_label}\n"
            " [dim]R replay / live  ← / → seek[/dim]\n"
            f" {snapshot.search_strategy.label}\n"
            f"{planner_summary}\n"
            f" STATUS: {frame.status.value}"
        )

    def action_toggle_play(self) -> None:
        if self.mode == "gridworld":
            if self._replay_blocks_mutation():
                return
            selected = self.gridworld_simulation.frame().drone(self.selected_drone_id)
            if selected.mode.value != "AUTO":
                self._ui_events.append(
                    f"[{self.tick:04d}] AUTO RUN DENIED / SELECTED DRONE NOT AUTO"
                )
                self.playing = False
                self._refresh_screen()
                return
            if self.gridworld_simulation.frame().status is not MissionStatus.ACTIVE:
                self.playing = False
                return
            self.playing = not self.playing
            self._refresh_screen()
            return
        self.replay_mode = False
        if self.tick >= MAX_TICK:
            self.tick = 0
        self.playing = not self.playing
        self._refresh_screen()

    def action_step(self) -> None:
        if self.mode == "gridworld":
            if self._replay_blocks_mutation():
                return
            self.playing = False
            selected = self.gridworld_simulation.frame().drone(self.selected_drone_id)
            if selected.mode.value == "AUTO":
                self._perform_live_action(
                    lambda: self.gridworld_simulation.autonomous_step(
                        self.selected_drone_id
                    )
                )
                self._refresh_screen()
                return
            if selected.mode.value != "MANUAL":
                self._ui_events.append(
                    f"[{self.tick:04d}]  {selected.identifier} {selected.callsign} "
                    "MOVEMENT DENIED / NOT MANUAL"
                )
                self._refresh_screen()
                return
            self._perform_live_action(
                lambda: self.gridworld_simulation.step(drone_id=self.selected_drone_id)
            )
            self._refresh_screen()
            return
        self.playing = False
        self.tick = min(MAX_TICK, self.tick + 1)
        self._refresh_screen()

    def action_move(self, direction: str) -> None:
        if self.mode == "gridworld":
            if self._replay_blocks_mutation():
                return
            selected = self.gridworld_simulation.frame().drone(self.selected_drone_id)
            if selected.mode.value != "MANUAL":
                self._ui_events.append(
                    f"[{self.tick:04d}]  {selected.identifier} {selected.callsign} "
                    "MOVEMENT DENIED / NOT MANUAL"
                )
                self._refresh_screen()
                return
            self._perform_live_action(
                lambda: self.gridworld_simulation.step(
                    Direction(direction), drone_id=self.selected_drone_id
                )
            )
            self._refresh_screen()

    def action_scan(self) -> None:
        if self.mode != "gridworld" or self._replay_blocks_mutation():
            return
        frame = self.gridworld_simulation.frame()
        selected = frame.drone(self.selected_drone_id)
        if selected.mode.value != "MANUAL":
            self._ui_events.append(
                f"[{frame.tick:04d}] SCAN DENIED / SELECTED DRONE NOT MANUAL"
            )
            self._refresh_screen()
            return
        if frame.status is not MissionStatus.ACTIVE:
            self._ui_events.append(f"[{frame.tick:04d}] SCAN DENIED / MISSION INACTIVE")
            self._refresh_screen()
            return
        self._perform_live_action(
            lambda: self.gridworld_simulation.scan(self.selected_drone_id)
        )
        self._refresh_screen()

    def action_select_drone(self, drone_id: str) -> None:
        if self.mode == "gridworld":
            frame = self._gridworld_snapshot().frame
            try:
                drone = frame.drone(drone_id)
            except KeyError:
                return
            if drone.identifier != self.selected_drone_id:
                self.selected_drone_id = drone.identifier
                if not self.replay_mode:
                    self._ui_events.append(
                        f"[{frame.tick:04d}]  SELECTED {drone.identifier} {drone.callsign}"
                    )
                self._refresh_screen()
        else:
            index = int(drone_id) - 1
            if 0 <= index < 3:
                self.selected_agent = index
                self._refresh_screen()

    def action_layer(self, layer: str) -> None:
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
        if self.mode == "gridworld":
            drones = self._gridworld_snapshot().frame.drones
            identifiers = [drone.identifier for drone in drones]
            next_index = (identifiers.index(self.selected_drone_id) + 1) % len(
                identifiers
            )
            self.action_select_drone(identifiers[next_index])
            return
        self.selected_agent = (self.selected_agent + 1) % 3
        self._refresh_screen()

    def action_toggle_replay(self) -> None:
        if self.mode == "gridworld":
            self.playing = False
            if self.replay_mode:
                self.replay_mode = False
                self._replay_timeline = None
            else:
                self._replay_timeline = self.gridworld_simulation.history
                self._replay_index = len(self._replay_timeline.snapshots) - 1
                self.replay_mode = True
            self._refresh_screen()
            return
        self.replay_mode = not self.replay_mode
        self.playing = False
        self._refresh_screen()

    def action_seek(self, direction: int) -> None:
        if (
            self.mode == "gridworld"
            and self.replay_mode
            and self._replay_timeline is not None
        ):
            self._replay_index = max(
                0,
                min(
                    len(self._replay_timeline.snapshots) - 1,
                    self._replay_index + direction,
                ),
            )
            self._refresh_screen()
            return
        if self.mode == "demo" and self.replay_mode:
            self.tick = max(0, min(MAX_TICK, self.tick + direction))
            self._refresh_screen()
