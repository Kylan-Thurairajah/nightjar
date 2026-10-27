"""Keyboard-first configuration and preflight screens for GridWorld missions."""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from nightjar.core.mission import (
    MapPreset,
    MissionConfig,
    ScenarioPreset,
    validate_mission_config,
)
from nightjar.core.provider import DRONE_CALLSIGNS, OperationalMode
from nightjar.core.sensor import SensorPreset


class DroneCountSlider(Static):
    BINDINGS = [
        Binding("left", "decrease", show=False, priority=True),
        Binding("right", "increase", show=False, priority=True),
        Binding("home", "minimum", show=False, priority=True),
        Binding("end", "maximum", show=False, priority=True),
    ]
    can_focus = True

    def __init__(
        self,
        value: int,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.value = value

    def render(self) -> Text:
        display = Text("1  ")
        for count in range(1, 11):
            if count == self.value:
                display.append("●", style="#e0b45c")
            elif count < self.value:
                display.append("━", style="#6aa778")
            else:
                display.append("─", style="#31543c")
        display.append("  10   ", style="#78a98c")
        display.append(f"{self.value:02d} DRONES", style="#e0b45c")
        return display

    def action_decrease(self) -> None:
        self.value = max(1, self.value - 1)
        self.refresh()

    def action_increase(self) -> None:
        self.value = min(10, self.value + 1)
        self.refresh()

    def action_minimum(self) -> None:
        self.value = 1
        self.refresh()

    def action_maximum(self) -> None:
        self.value = 10
        self.refresh()


class MissionConfigScreen(Screen[MissionConfig | None]):
    BINDINGS = [
        Binding("enter", "continue_to_preflight", "Review", priority=True),
        Binding("escape", "exit_configuration", "Back"),
        Binding("q", "exit_configuration", "Quit"),
    ]
    CSS_PATH = "mission.tcss"

    def __init__(self, config: MissionConfig | None = None) -> None:
        super().__init__()
        self.config = config or MissionConfig()

    def compose(self) -> ComposeResult:
        yield Static(" ◈ NIGHTJAR  /  MISSION CONFIGURATION", classes="mission_header")
        with VerticalScroll(id="config_scroll"):
            with Center():
                with Vertical(id="config_panel"):
                    yield Static("MISSION PARAMETERS", classes="group_title")
                    yield Label("Operation name")
                    yield Input(
                        self.config.operation_name,
                        id="operation_name",
                        max_length=40,
                    )
                    yield Label("Environment preset")
                    with RadioSet(id="scenario", classes="option_set"):
                        yield RadioButton(
                            "OPEN FIELD",
                            value=self.config.scenario is ScenarioPreset.OPEN_FIELD,
                            id="scenario-open",
                        )
                        yield RadioButton(
                            "OBSTACLE FIELD",
                            value=self.config.scenario is ScenarioPreset.OBSTACLE_FIELD,
                            id="scenario-obstacle",
                        )

                    yield Static("DEPLOYMENT CONFIGURATION", classes="group_title")
                    with Horizontal(classes="field_row"):
                        with Vertical(classes="half_field"):
                            yield Label("Drone count (1–10)")
                            yield DroneCountSlider(
                                self.config.drone_count,
                                id="drone_count",
                                classes="drone_slider",
                            )
                            yield Label("Use ← / → to adjust; Home / End jump to limits.")
                    yield Label("Map dimensions")
                    with RadioSet(id="map_preset", classes="option_set"):
                        yield RadioButton(
                            "COMPACT  16×12",
                            value=self.config.map_preset is MapPreset.COMPACT,
                            id="map-compact",
                        )
                        yield RadioButton(
                            "STANDARD  32×16",
                            value=self.config.map_preset is MapPreset.STANDARD,
                            id="map-standard",
                        )
                        yield RadioButton(
                            "EXTENDED  40×20",
                            value=self.config.map_preset is MapPreset.EXTENDED,
                            id="map-extended",
                        )
                    yield Label("Initial control policy")
                    with RadioSet(id="initial_control", classes="option_set"):
                        yield RadioButton(
                            "MANUAL · direct operator control",
                            value=self.config.initial_control is OperationalMode.MANUAL,
                            id="control-manual",
                        )
                        yield RadioButton(
                            "IDLE · hold position",
                            value=self.config.initial_control is OperationalMode.IDLE,
                            id="control-idle",
                        )
                    yield Label("Synthetic sensor reliability preset")
                    with RadioSet(id="sensor_preset", classes="option_set"):
                        yield RadioButton(
                            "HIGH RELIABILITY  98% / 2%",
                            value=self.config.sensor_preset is SensorPreset.HIGH_RELIABILITY,
                            id="sensor-high",
                        )
                        yield RadioButton(
                            "STANDARD  90% / 5%",
                            value=self.config.sensor_preset is SensorPreset.STANDARD,
                            id="sensor-standard",
                        )
                        yield RadioButton(
                            "DEGRADED  75% / 15%",
                            value=self.config.sensor_preset is SensorPreset.DEGRADED,
                            id="sensor-degraded",
                        )

                    yield Static("SIMULATION PARAMETERS", classes="group_title")
                    with Horizontal(classes="field_row"):
                        with Vertical(classes="half_field"):
                            yield Label("Maximum mission ticks")
                            yield Input(str(self.config.max_ticks), id="max_ticks")
                        with Vertical(classes="half_field"):
                            yield Label("Deterministic random seed")
                            yield Input(str(self.config.seed), id="seed")
        with Center():
            with Vertical(id="config_actions"):
                yield Static("", id="form_error")
                yield Button("NEXT: PREFLIGHT REVIEW  [ENTER]", id="next", variant="primary")
        yield Static(
            " Tab navigate  ·  ←/→ adjust slider or highlight  ·  Space select  ·  Q quit",
            classes="mission_footer",
        )

    def on_mount(self) -> None:
        self.query_one("#operation_name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            self.action_continue_to_preflight()

    def action_continue_to_preflight(self) -> None:
        try:
            config = self._read_config()
        except ValueError as error:
            self.query_one("#form_error", Static).update(f"[amber]INPUT ERROR: {error}[/amber]")
            return

        failures = [
            f"{check.label}: {check.detail}"
            for check in validate_mission_config(config)
            if not check.passed
        ]
        if failures:
            self.query_one("#form_error", Static).update(
                "[amber]CONFIGURATION INVALID: " + " | ".join(failures) + "[/amber]"
            )
            return
        self.config = config
        self.query_one("#form_error", Static).update("")
        self.app.push_screen(PreflightReviewScreen(config), self._preflight_result)

    def _read_config(self) -> MissionConfig:
        try:
            scenario_button = self.query_one("#scenario", RadioSet).pressed_button
            map_button = self.query_one("#map_preset", RadioSet).pressed_button
            control_button = self.query_one("#initial_control", RadioSet).pressed_button
            sensor_button = self.query_one("#sensor_preset", RadioSet).pressed_button
            if (
                scenario_button is None
                or map_button is None
                or control_button is None
                or sensor_button is None
                or scenario_button.id is None
                or map_button.id is None
                or control_button.id is None
                or sensor_button.id is None
            ):
                raise ValueError("choose a value for every option group")
            scenario = {
                "scenario-open": ScenarioPreset.OPEN_FIELD,
                "scenario-obstacle": ScenarioPreset.OBSTACLE_FIELD,
            }[scenario_button.id]
            map_preset = {
                "map-compact": MapPreset.COMPACT,
                "map-standard": MapPreset.STANDARD,
                "map-extended": MapPreset.EXTENDED,
            }[map_button.id]
            initial_control = {
                "control-manual": OperationalMode.MANUAL,
                "control-idle": OperationalMode.IDLE,
            }[control_button.id]
            sensor_preset = {
                "sensor-high": SensorPreset.HIGH_RELIABILITY,
                "sensor-standard": SensorPreset.STANDARD,
                "sensor-degraded": SensorPreset.DEGRADED,
            }[sensor_button.id]
            return MissionConfig(
                operation_name=self.query_one("#operation_name", Input).value.strip(),
                scenario=scenario,
                drone_count=self.query_one("#drone_count", DroneCountSlider).value,
                map_preset=map_preset,
                initial_control=initial_control,
                max_ticks=int(self.query_one("#max_ticks", Input).value),
                seed=int(self.query_one("#seed", Input).value),
                sensor_preset=sensor_preset,
            )
        except (ValueError, TypeError, KeyError) as error:
            raise ValueError("counts, tick budget, and seed must be valid integers/options") from error

    def _preflight_result(self, config: MissionConfig | None) -> None:
        if config is not None:
            self.dismiss(config)

    def action_exit_configuration(self) -> None:
        self.app.exit()


class PreflightReviewScreen(Screen[MissionConfig | None]):
    BINDINGS = [
        Binding("enter", "confirm_launch", "Launch", priority=True),
        Binding("escape", "return_to_configuration", "Back"),
        Binding("q", "return_to_configuration", "Back"),
    ]
    CSS_PATH = "mission.tcss"

    def __init__(self, config: MissionConfig) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Static(" ◈ NIGHTJAR  /  PREFLIGHT REVIEW", classes="mission_header")
        with VerticalScroll(id="preflight_scroll"):
            with Center():
                with Vertical(id="preflight_panel"):
                    yield Static("MISSION SUMMARY", classes="group_title")
                    yield Static(id="mission_summary")
                    yield Static("ALLOCATED CALLSIGNS", classes="group_title")
                    yield Static(id="callsigns")
                    yield Static("VALIDATION RESULTS", classes="group_title")
                    yield Static(id="validation_results")
        with Center():
            with Vertical(id="preflight_actions"):
                yield Static("", id="preflight_error")
                with Horizontal(classes="button_row"):
                    yield Button("BACK TO CONFIGURATION", id="back")
                    yield Button(
                        "CONFIRM AND LAUNCH  [ENTER]",
                        id="launch",
                        variant="primary",
                    )
        yield Static(
            " Enter launch  ·  Back button or Esc to edit configuration  ·  Q return",
            classes="mission_footer",
        )

    def on_mount(self) -> None:
        self.query_one("#mission_summary", Static).update(
            f" OPERATION     {self.config.operation_name}\n"
            f" MISSION ID    {self.config.mission_id}\n"
            f" SCENARIO      {self.config.scenario.value.replace('_', ' ').upper()}\n"
            f" MAP           {self.config.width} × {self.config.height}\n"
            f" DRONES        {self.config.drone_count:02d}\n"
            f" CONTROL       {self.config.initial_control.value}\n"
            f" SENSOR        {self.config.sensor_preset.value.replace('_', ' ').upper()}\n"
            f" DETECTION     3 cells / Manhattan\n"
            f" MODEL         {self.config.sensor_preset.probabilities[0]:.0%} sensitivity / "
            f"{self.config.sensor_preset.probabilities[1]:.0%} false positive\n"
            f" TICK BUDGET   {self.config.max_ticks}\n"
            f" RANDOM SEED   {self.config.seed}"
        )
        callsigns = [
            f" {index:02d}  {callsign}"
            for index, callsign in enumerate(DRONE_CALLSIGNS[: self.config.drone_count], 1)
        ]
        self.query_one("#callsigns", Static).update("   ".join(callsigns))
        checks = validate_mission_config(self.config)
        lines = [
            f"[green]PASS[/green] {check.label} — {check.detail}"
            if check.passed
            else f"[amber]FAIL[/amber] {check.label} — {check.detail}"
            for check in checks
        ]
        self.query_one("#validation_results", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_return_to_configuration()
        elif event.button.id == "launch":
            self.action_confirm_launch()

    def action_confirm_launch(self) -> None:
        failures = [
            check for check in validate_mission_config(self.config) if not check.passed
        ]
        if failures:
            self.query_one("#preflight_error", Static).update(
                "[amber]Launch blocked: resolve failed validation checks.[/amber]"
            )
            return
        self.dismiss(self.config)

    def action_return_to_configuration(self) -> None:
        self.dismiss(None)
