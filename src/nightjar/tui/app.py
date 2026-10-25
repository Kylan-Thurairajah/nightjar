"""Nightjar's first terminal application (Textual + Rich)."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static

from nightjar.core.demo import DemoSimulation, MAX_TICK
from nightjar.tui.map_widget import MapWidget


class NightjarApp(App[None]):
    TITLE = "NIGHTJAR"
    SUB_TITLE = "AUTONOMOUS SEARCH / SIM LAB / DEMO"
    CSS_PATH = "nightjar.tcss"

    BINDINGS = [
        Binding("space", "toggle_play", "Play / Pause"),
        Binding("n", "step", "Step"),
        Binding("h", "layer('belief')", "Heatmap"),
        Binding("c", "layer('coverage')", "Coverage"),
        Binding("p", "layer('paths')", "Paths"),
        Binding("tab", "next_agent", "Select agent", show=False),
        Binding("r", "toggle_replay", "Replay"),
        Binding("left", "seek(-1)", "Back", show=False),
        Binding("right", "seek(1)", "Forward", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.sim = DemoSimulation()
        self.tick = 0
        self.playing = False
        self.replay_mode = False
        self.layer = "belief"
        self.selected_agent = 0

    def compose(self) -> ComposeResult:
        yield Static(" ◈ NIGHTJAR    /  01     AUTONOMOUS SEARCH SIMULATION     [DEMO MODE]", id="masthead")
        with Horizontal(id="workspace"):
            with Vertical(id="map_panel"):
                yield Static(" ┌ SECTOR ALPHA / PROBABILITY GRID                       32 × 16", id="map_title", classes="section_title")
                yield MapWidget(id="map")
                yield Static(" LOW  ░░  ▒▒  ██   ▓▓ WALL     01 DRONE     [H] HEAT  [C] COVER  [P] PATH", id="legend")
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
        yield Static(" TERMINAL-FIRST PROTOTYPE  •  Synthetic belief field, scripted agent routes  •  No external sensors", id="mode_note")
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

    def action_toggle_play(self) -> None:
        self.replay_mode = False
        if self.tick >= MAX_TICK:
            self.tick = 0
        self.playing = not self.playing
        self._refresh_screen()

    def action_step(self) -> None:
        self.playing = False
        self.tick = min(MAX_TICK, self.tick + 1)
        self._refresh_screen()

    def action_layer(self, layer: str) -> None:
        if layer in {"belief", "coverage", "paths"}:
            self.layer = layer
            self._refresh_screen()

    def action_next_agent(self) -> None:
        self.selected_agent = (self.selected_agent + 1) % 3
        self._refresh_screen()

    def action_toggle_replay(self) -> None:
        self.replay_mode = not self.replay_mode
        self.playing = False
        self._refresh_screen()

    def action_seek(self, direction: int) -> None:
        if self.replay_mode:
            self.tick = max(0, min(MAX_TICK, self.tick + direction))
            self._refresh_screen()
