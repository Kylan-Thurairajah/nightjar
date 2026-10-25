"""Nightjar's first terminal application (Textual + Rich)."""

from typing import Literal

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static

from nightjar.core.demo import DemoSimulation, MAX_TICK
from nightjar.core.provider import GridWorldFrame, GridWorldSimulation
from nightjar.core.world import Direction
from nightjar.tui.map_widget import MapWidget


class NightjarApp(App[None]):
    TITLE = "NIGHTJAR"
    SUB_TITLE = "AUTONOMOUS SEARCH / SIM LAB / DEMO"
    CSS_PATH = "nightjar.tcss"

    BINDINGS = [
        Binding("space", "toggle_play", "Play / Pause"),
        Binding("n", "step", "Step"),
        Binding("w", "move('north')", "Move North"),
        Binding("a", "move('west')", "Move West"),
        Binding("s", "move('south')", "Move South"),
        Binding("d", "move('east')", "Move East"),
        Binding("h", "layer('belief')", "Heatmap"),
        Binding("c", "layer('coverage')", "Coverage"),
        Binding("p", "layer('paths')", "Paths"),
        Binding("tab", "next_agent", "Select agent", show=False),
        Binding("r", "toggle_replay", "Replay"),
        Binding("left", "seek(-1)", "Back", show=False),
        Binding("right", "seek(1)", "Forward", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        mode: Literal["demo", "gridworld"] = "demo",
        gridworld_simulation: GridWorldSimulation | None = None,
    ) -> None:
        super().__init__()
        if mode not in {"demo", "gridworld"}:
            raise ValueError(f"unsupported simulation mode: {mode!r}")
        self.mode = mode
        self.sim = DemoSimulation()
        self.gridworld_simulation = gridworld_simulation or GridWorldSimulation()
        self.tick = 0
        self.playing = False
        self.replay_mode = False
        self.layer = "terrain" if mode == "gridworld" else "belief"
        self.selected_agent = 0

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
                    f" ┌ SECTOR ALPHA / {map_label}                       32 × 16",
                    id="map_title",
                    classes="section_title",
                )
                yield MapWidget(id="map")
                legend = (
                    " ▓▓ OBSTACLE  01 AGENT  WASD MOVE  [H] TERRAIN  [C] COVER  [P] PATH"
                    if self.mode == "gridworld"
                    else " LOW  ░░  ▒▒  ██   ▓▓ WALL     01 DRONE     [H] HEAT  [C] COVER  [P] PATH"
                )
                yield Static(legend, id="legend")
            with Vertical(id="telemetry_panel"):
                yield Static("┌ AGENT TELEMETRY", classes="section_title")
                yield Static(id="agents")
                yield Static("┌ BELIEF STATE", classes="section_title")
                yield Static(id="metrics")
        with Horizontal(id="bottom_panels"):
            with Vertical(id="events_panel"):
                yield Static("┌ SYSTEM EVENT LOG", classes="section_title")
                yield Static(id="events")
            with Vertical(id="replay_panel"):
                yield Static("┌ MISSION REPLAY", classes="section_title")
                yield Static(id="timeline")
        mode_note = (
            " GRIDWORLD  •  Deterministic single-agent movement  •  No sensing or belief map"
            if self.mode == "gridworld"
            else " TERMINAL-FIRST PROTOTYPE  •  Synthetic belief field, scripted agent routes  •  No external sensors"
        )
        yield Static(mode_note, id="mode_note")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.22, self._timer_tick)
        self._refresh_screen()

    def _timer_tick(self) -> None:
        if self.playing:
            self.tick = min(MAX_TICK, self.tick + 1)
            if self.tick == MAX_TICK:
                self.playing = False
            self._refresh_screen()

    def _refresh_screen(self) -> None:
        if self.mode == "gridworld":
            self._refresh_gridworld_screen(self.gridworld_simulation.frame())
            return

        frame = self.sim.frame(self.tick)
        self.query_one("#map", MapWidget).show_frame(frame, self.layer, self.selected_agent)
        layer_labels = {"belief": "PROBABILITY GRID", "coverage": "VISITED CELLS", "paths": "TRAVEL HISTORY"}
        self.query_one("#map_title", Static).update(f" ┌ SECTOR ALPHA / {layer_labels[self.layer]}                      32 × 16")
        agent_lines = []
        for i, agent in enumerate(frame.agents):
            arrow = "▶" if i == self.selected_agent else " "
            bar = "▰" * (agent.energy // 10) + "▱" * (10 - agent.energy // 10)
            agent_lines.extend([
                f" {arrow} [{agent.identifier}] {agent.callsign}",
                f"   {agent.status:<10} {agent.energy:3d}%",
                f"   [green]{bar}[/green]",
                "",
            ])
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
        state = "REPLAY" if self.replay_mode else "RUNNING" if self.playing else "PAUSED"
        self.query_one("#timeline", Static).update(
            f" RUN 001  /  TICK {self.tick:04d}\n\n"
            f" [green]{track}[/green]\n"
            f" 0000                      {MAX_TICK:04d}\n\n"
            f" STATE: {state}\n"
            " [dim]R replay  ← / → seek  Space live[/dim]"
        )

    def _refresh_gridworld_screen(self, frame: GridWorldFrame) -> None:
        self.tick = frame.tick
        self.query_one("#map", MapWidget).show_gridworld_frame(frame, self.layer)
        layer_labels = {
            "terrain": "NEUTRAL TERRAIN",
            "coverage": "VISITED CELLS",
            "paths": "TRAVEL HISTORY",
        }
        self.query_one("#map_title", Static).update(
            f" ┌ SECTOR ALPHA / {layer_labels[self.layer]}                       "
            f"{frame.width} × {frame.height}"
        )
        self.query_one("#agents", Static).update(
            " ▶ AGENT 01 / GRID\n"
            f"   POSITION  ({frame.position[0]:02d},{frame.position[1]:02d})\n"
            "   STATUS    VIRTUAL"
        )
        if frame.last_result is None or frame.last_direction is None:
            movement = "NOT STARTED"
        elif frame.last_result.moved:
            movement = f"MOVED {frame.last_direction.value.upper()}"
        else:
            reason = frame.last_result.blocked_by
            if reason is None:
                raise RuntimeError("blocked GridWorld step did not include a reason")
            reason_label = "WALL" if reason.value == "obstacle" else reason.value.upper()
            movement = f"BLOCKED BY {reason_label}"
        self.query_one("#metrics", Static).update(
            f" GRID        {frame.width:3d} × {frame.height:<3d}\n"
            f" POSITION    ({frame.position[0]:02d},{frame.position[1]:02d})\n"
            f" OBSTACLES   {len(frame.obstacles):5d}\n"
            f" TICK        {frame.tick:5d}\n"
            f" RESULT      {movement}"
        )
        self.query_one("#events", Static).update("\n".join(frame.events))
        self.query_one("#timeline", Static).update(
            f" GRIDWORLD  /  TICK {frame.tick:04d}\n\n"
            f" LAST ACTION: {movement}\n\n"
            " [dim]WASD move  H terrain  C coverage  P path[/dim]"
        )

    def action_toggle_play(self) -> None:
        if self.mode == "gridworld":
            return
        self.replay_mode = False
        if self.tick >= MAX_TICK:
            self.tick = 0
        self.playing = not self.playing
        self._refresh_screen()

    def action_step(self) -> None:
        if self.mode == "gridworld":
            self.playing = False
            self.gridworld_simulation.step()
            self._refresh_screen()
            return
        self.playing = False
        self.tick = min(MAX_TICK, self.tick + 1)
        self._refresh_screen()

    def action_move(self, direction: str) -> None:
        if self.mode == "gridworld":
            self.gridworld_simulation.step(Direction(direction))
            self._refresh_screen()

    def action_layer(self, layer: str) -> None:
        if self.mode == "demo" and layer in {"belief", "coverage", "paths"}:
            self.layer = layer
            self._refresh_screen()
        elif self.mode == "gridworld":
            if layer == "belief":
                self.layer = "terrain"
            elif layer in {"coverage", "paths"}:
                self.layer = layer
            self._refresh_screen()

    def action_next_agent(self) -> None:
        if self.mode == "gridworld":
            return
        self.selected_agent = (self.selected_agent + 1) % 3
        self._refresh_screen()

    def action_toggle_replay(self) -> None:
        if self.mode == "gridworld":
            return
        self.replay_mode = not self.replay_mode
        self.playing = False
        self._refresh_screen()

    def action_seek(self, direction: int) -> None:
        if self.mode == "demo" and self.replay_mode:
            self.tick = max(0, min(MAX_TICK, self.tick + direction))
            self._refresh_screen()
