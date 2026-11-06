"""Isolated matched-policy experiment and recorded common-tick viewing."""

import asyncio
import threading

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.events import Resize
from textual.screen import Screen
from textual.widgets import Button, Static

from nightjar.core.mission import MissionConfig
from nightjar.services.comparison import (
    ComparisonCancelled,
    ComparisonReport,
    ComparisonRun,
    compare_policies,
)
from nightjar.tui.map_widget import MapWidget
from nightjar.tui.presentation import coverage


def tick_samples(run: ComparisonRun, maximum_tick: int, count: int = 24):
    """Uniform tick coordinates, selecting committed states without interpolation."""
    return tuple(
        run.at_tick(round(index * maximum_tick / max(1, count - 1)))
        for index in range(count)
    )


def _spark(values, lower: float, upper: float) -> str:
    glyphs = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
    span = max(upper - lower, 1e-12)
    return "".join(
        glyphs[max(0, min(7, round((value - lower) / span * 7)))] for value in values
    )


class ComparisonScreen(Screen[None]):
    CSS_PATH = "comparison.tcss"
    BINDINGS = [
        Binding("enter", "run", "Run", priority=True),
        Binding("escape", "close", "Return", priority=True),
        Binding("q", "close", "Return", priority=True),
        Binding("v", "close", "Return", priority=True),
        Binding("tab", "switch_policy", "Switch policy", priority=True),
        Binding("1", "policy(0)", "Frontier", priority=True),
        Binding("2", "policy(1)", "Information gain", priority=True),
        Binding("left", "seek(-1)", "Back", priority=True),
        Binding("right", "seek(1)", "Forward", priority=True),
        Binding("home", "endpoint(False)", "Start", priority=True),
        Binding("end", "endpoint(True)", "End", priority=True),
        Binding("space", "play", "Play records", priority=True),
        Binding("h", "layer('belief')", "Belief", priority=True),
        Binding("c", "layer('coverage')", "Coverage", priority=True),
        Binding("p", "layer('paths')", "Paths", priority=True),
        Binding("pagedown", "scroll_map(0, 5)", "Scroll map down", priority=True),
        Binding("pageup", "scroll_map(0, -5)", "Scroll map up", priority=True),
        Binding("shift+right", "scroll_map(8, 0)", "Scroll map right", priority=True),
        Binding("shift+left", "scroll_map(-8, 0)", "Scroll map left", priority=True),
    ]

    def __init__(self, config: MissionConfig):
        super().__init__()
        self.config = config
        self.report: ComparisonReport | None = None
        self.cursor = 0
        self.selected_policy = 0
        self.map_layer = "belief"
        self.playing = False
        self.busy = False
        self._comparison_closing = False
        self._comparison_cancel = threading.Event()
        self._experiment_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Static("MATCHED POLICY LAB / ALL AUTO", id="comparison_title")
        yield Static(
            f"{self.config.scenario.value.replace('_', ' ').upper()} / "
            f"{self.config.width}x{self.config.height} / SEED {self.config.seed} / "
            f"{self.config.sensor_preset.value.upper()}\n"
            f"{self.config.drone_count} drones / {self.config.max_ticks} tick ceiling / "
            "fresh configured starts, not the live mission",
            id="comparison_config",
        )
        yield Static("", id="comparison_finals")
        yield Static(
            "READY / Enter or RUN starts two isolated experiments",
            id="comparison_status",
        )
        with Horizontal(id="comparison_maps"):
            for index in range(2):
                with Vertical(id=f"comparison_panel_{index}"):
                    yield Static(
                        "FRONTIER" if index == 0 else "INFORMATION GAIN",
                        id=f"comparison_label_{index}",
                    )
                    with ScrollableContainer(id=f"comparison_scroll_{index}"):
                        map_widget = MapWidget(id=f"comparison_map_{index}")
                        map_widget.styles.width = self.config.width * 2
                        map_widget.styles.height = self.config.height
                        yield map_widget
        yield Static(
            "Coverage and entropy traces appear after computation.\nNo winner or confirmed-discovery score.",
            id="comparison_traces",
        )
        yield Static(
            "Enter run / arrows seek / Home,End / Space play / Tab,1,2 policy\nH/C/P layers / PgUp,Dn map / Shift+arrows wide / Esc,Q return",
            id="comparison_controls",
        )
        with Horizontal(id="comparison_buttons"):
            yield Button("RUN PAIRED EXPERIMENT", id="comparison_run")
            yield Button("RETURN / CANCEL", id="comparison_close")

    def on_mount(self) -> None:
        self.set_interval(0.15, self._replay_tick)
        self._layout_maps()

    def on_resize(self, event: Resize) -> None:
        self._layout_maps()
        self._refresh_report()

    def _layout_maps(self) -> None:
        if not self.is_mounted:
            return
        dual = (
            self.size.width >= 2 * (self.config.width * 2 + 4) + 2
            and self.size.height >= 30
        )
        self.set_class(self.size.width < 100 or self.size.height < 30, "short")
        for index in range(2):
            self.query_one(f"#comparison_panel_{index}").display = (
                dual or index == self.selected_policy
            )

    @property
    def maximum_tick(self) -> int:
        return (
            max((run.final.frame.tick for run in self.report.runs), default=0)
            if self.report
            else 0
        )

    def action_run(self) -> None:
        if self.busy or self._comparison_closing:
            return
        self.busy = True
        self.playing = False
        self.report = None
        self._comparison_cancel = threading.Event()
        self.query_one("#comparison_run", Button).disabled = True
        self.query_one("#comparison_status", Static).update(
            "RUNNING / FRONTIER then INFORMATION GAIN / Esc cancels"
        )
        self.query_one("#comparison_finals", Static).update("")
        for index in range(2):
            self.query_one(f"#comparison_map_{index}", MapWidget).update("")
        self.query_one("#comparison_traces", Static).update(
            "Computing real all-AUTO traces off the UI loop.\nSame inputs do not imply identical sensor readings along different paths."
        )
        self._experiment_task = asyncio.create_task(self._compute())

    async def _compute(self) -> None:
        try:
            result = await compare_policies(
                self.config, cancel_event=self._comparison_cancel
            )
            if not self._comparison_cancel.is_set() and not self._comparison_closing:
                self.report = result
                self.cursor = self.maximum_tick
                self._refresh_report()
        except ComparisonCancelled:
            if self.is_mounted:
                self.query_one("#comparison_status", Static).update(
                    "CANCELLED / no partial comparison published"
                )
        except asyncio.CancelledError:
            self._comparison_cancel.set()
            raise
        except Exception as error:
            if self.is_mounted:
                self.query_one("#comparison_status", Static).update(
                    Text(f"ERROR / {error}")
                )
        finally:
            self.busy = False
            if self.is_mounted:
                self.query_one(
                    "#comparison_run", Button
                ).disabled = self._comparison_closing

    async def wait_for_run(self) -> None:
        if self._experiment_task is not None:
            await asyncio.shield(self._experiment_task)

    def action_close(self) -> None:
        if self._comparison_closing:
            return
        self._comparison_closing = True
        self.playing = False
        self._comparison_cancel.set()
        if self.busy:
            self.query_one("#comparison_status", Static).update(
                "CANCELLING / waiting for the current core round to finish"
            )
        self.run_worker(self._finish_close(), group="comparison-close")

    async def _finish_close(self) -> None:
        await self._join_task()
        self.dismiss(None)

    async def _join_task(self) -> None:
        if self._experiment_task is None:
            return
        while not self._experiment_task.done():
            try:
                await asyncio.shield(self._experiment_task)
            except asyncio.CancelledError:
                self._comparison_cancel.set()

    async def on_unmount(self) -> None:
        self._comparison_cancel.set()
        await self._join_task()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "comparison_run":
            self.action_run()
        elif event.button.id == "comparison_close":
            self.action_close()

    def action_switch_policy(self) -> None:
        self.action_policy(1 - self.selected_policy)

    def action_scroll_map(self, x: int, y: int) -> None:
        self.query_one(
            f"#comparison_scroll_{self.selected_policy}", ScrollableContainer
        ).scroll_relative(x=x, y=y, animate=False)

    def action_policy(self, index: int) -> None:
        self.selected_policy = index
        self._layout_maps()

    def action_layer(self, layer: str) -> None:
        self.map_layer = layer
        self._refresh_report()

    def action_seek(self, delta: int) -> None:
        self.playing = False
        self.cursor = max(0, min(self.maximum_tick, self.cursor + delta))
        self._refresh_report()

    def action_endpoint(self, end: bool) -> None:
        self.playing = False
        self.cursor = self.maximum_tick if end else 0
        self._refresh_report()

    def action_play(self) -> None:
        if self.report is None or self.maximum_tick == 0:
            return
        if self.cursor == self.maximum_tick:
            self.cursor = 0
        self.playing = not self.playing
        self._refresh_report()

    def _replay_tick(self) -> None:
        if self.playing:
            self.cursor = min(self.maximum_tick, self.cursor + 1)
            if self.cursor == self.maximum_tick:
                self.playing = False
            self._refresh_report()

    def _refresh_report(self) -> None:
        if self.report is None or not self.is_mounted:
            return
        final_lines = []
        short_view = self.size.width < 100 or self.size.height < 30
        trace_lines = []
        display_ticks = []
        traces = Text()
        maximum_entropy = max(
            run.timeline.snapshots[0].belief.stats.entropy_bits
            for run in self.report.runs
        )
        for index, run in enumerate(self.report.runs):
            final = run.final
            stats = final.belief.stats
            initial_entropy = run.timeline.snapshots[0].belief.stats.entropy_bits
            short = "FRONTIER" if index == 0 else "INFO GAIN"
            if short_view:
                final_lines.append(
                    f"{short} {final.frame.tick}t {len(final.observations)}s "
                    f"C{coverage(final):.1%} H{stats.entropy_bits:.2f} "
                    f"dH{stats.entropy_bits - initial_entropy:+.2f} {final.frame.status.value}"
                )
            else:
                final_lines.extend(
                    [
                        f"{short}: {final.frame.tick} ticks / {len(final.observations)} scans / coverage {coverage(final):.1%} / H {stats.entropy_bits:.2f} bits",
                        f"  {final.frame.status.value} / entropy change {stats.entropy_bits - initial_entropy:+.2f} bits",
                    ]
                )
            snapshot = run.at_tick(self.cursor)
            display_ticks.append(f"{short} {snapshot.frame.tick}")
            self.query_one(f"#comparison_label_{index}", Static).update(
                f"{run.strategy.label} / actual tick {snapshot.frame.tick} / {self.map_layer.upper()}"
            )
            self.query_one(f"#comparison_map_{index}", MapWidget).show_gridworld_frame(
                snapshot.frame,
                self.map_layer,
                "01",
                snapshot.belief,
                last_observation=snapshot.observations[-1]
                if snapshot.observations
                else None,
                planner_decision=snapshot.last_planner_decision,
            )
            samples = tick_samples(run, self.maximum_tick, 12 if short_view else 24)
            trace_lines.append(
                f"{short:<9} C "
                + _spark([coverage(item) for item in samples], 0, 1)
                + " H "
                + _spark(
                    [item.belief.stats.entropy_bits for item in samples],
                    0,
                    maximum_entropy,
                )
            )
            traces.append(
                f"{short:<9} C 0-100% "
                + _spark([coverage(item) for item in samples], 0, 1)
                + "\n",
                style="#89c998",
            )
            traces.append(
                f"{'':9} H 0-{maximum_entropy:.1f}b "
                + _spark(
                    [item.belief.stats.entropy_bits for item in samples],
                    0,
                    maximum_entropy,
                )
                + "\n",
                style="#e0b45c",
            )
        traces.append(
            f"Uniform tick axis: 0 -> {self.maximum_tick} / committed states only",
            style="#a7d4b4",
        )
        self.query_one("#comparison_finals", Static).update(
            Text("\n".join(final_lines), no_wrap=True, overflow="crop")
        )
        if short_view:
            traces = Text(
                f"Ticks 0..{self.maximum_tick} / C 0..100% / H 0..{maximum_entropy:.1f} bits\n"
                + "\n".join(trace_lines)
            )
        self.query_one("#comparison_traces", Static).update(traces)
        self.query_one("#comparison_status", Static).update(
            f"RECORDED {'PLAY' if self.playing else 'PAUSE'} / cursor tick {self.cursor}/{self.maximum_tick}\n"
            + "Displayed: "
            + " / ".join(display_ticks)
        )
        if short_view:
            self.query_one("#comparison_status", Static).update(
                f"{'PLAY' if self.playing else 'PAUSE'} cursor {self.cursor}/{self.maximum_tick} / "
                + " / ".join(display_ticks)
            )
            self.query_one("#comparison_config", Static).update(
                f"{self.config.scenario.value.replace('_', ' ').upper()} / {self.config.width}x{self.config.height} / seed {self.config.seed} / {self.config.sensor_preset.value.upper()}\n"
                f"ALL AUTO {self.config.drone_count} / ceiling {self.config.max_ticks} / fresh starts / t=ticks s=scans C=coverage H,dH=bits"
            )
