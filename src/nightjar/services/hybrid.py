"""Serialized hybrid control and committed presentation state.

The provider has one owner: this controller's FIFO lock. Public presentation
properties contain immutable cached state and never read a running core thread.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from nightjar.core.provider import GridWorldSimulation, MissionStatus, OperationalMode
from nightjar.core.replay import MissionSnapshot, ReplayTimeline
from nightjar.core.world import Direction


class ControlDeniedError(ValueError):
    """A manual input targets a drone that is not under manual control."""


class HybridMissionController:
    """Own one mission, serializing explicit inputs and coalesced timer work.

    Callers must reserve their pending submissions synchronously before scheduling
    coroutine workers: ``busy`` covers commands once their coroutine starts.
    The provider must not be accessed externally while a command is in flight.
    """

    def __init__(self, simulation: GridWorldSimulation) -> None:
        self._simulation = simulation
        self._live_snapshot = simulation.snapshot()
        self._live_history = simulation.history
        self._selected_id = self._live_snapshot.frame.drones[0].identifier
        self._saved_live_selection = self._selected_id
        self._replay_history: ReplayTimeline | None = None
        self._replay_index = 0
        self._lock = asyncio.Lock()
        self._pending = 0

    @property
    def live_snapshot(self) -> MissionSnapshot:
        return self._live_snapshot

    @property
    def live_history(self) -> ReplayTimeline:
        return self._live_history

    @property
    def replay_history(self) -> ReplayTimeline | None:
        return self._replay_history

    @property
    def view_snapshot(self) -> MissionSnapshot:
        if self._replay_history is not None:
            return self._replay_history.snapshot(self._replay_index)
        return self._live_snapshot

    @property
    def selected_drone_id(self) -> str:
        return self._selected_id

    @property
    def replay_mode(self) -> bool:
        return self._replay_history is not None

    @property
    def replay_index(self) -> int:
        return self._replay_index

    @property
    def busy(self) -> bool:
        return self._pending != 0

    @asynccontextmanager
    async def _command(self) -> AsyncIterator[None]:
        self._pending += 1
        try:
            async with self._lock:
                yield
        finally:
            self._pending -= 1

    async def _core(
        self,
        operation: Callable[[], object],
        *,
        selection_after: str | None = None,
    ) -> None:
        def execute() -> tuple[MissionSnapshot, ReplayTimeline, Exception | None]:
            error = None
            try:
                operation()
            except Exception as failure:
                error = failure
            # Exceptions can follow earlier committed actions in a fleet round.
            # Publish their committed state as well, before propagating failure.
            return self._simulation.snapshot(), self._simulation.history, error

        # A Future rather than a to_thread Task survives asyncio's task-shutdown
        # cancellation. Cancelling an awaiter must not release ownership while
        # Python's non-cancellable core thread continues mutating the provider.
        future = asyncio.get_running_loop().run_in_executor(None, execute)
        cancelled = False
        while True:
            try:
                snapshot, history, error = await asyncio.shield(future)
                break
            except asyncio.CancelledError:
                cancelled = True
        self._live_snapshot = snapshot
        self._live_history = history
        if error is None and selection_after is not None:
            self._selected_id = selection_after
        if cancelled:
            raise asyncio.CancelledError
        if error is not None:
            raise error

    def _can_run(self) -> bool:
        return (
            not self.replay_mode
            and self._live_snapshot.frame.status is MissionStatus.ACTIVE
            and any(
                drone.mode is OperationalMode.AUTO
                for drone in self._live_snapshot.frame.drones
            )
        )

    async def can_run(self) -> bool:
        """Resolve run availability after earlier queued control requests."""
        async with self._command():
            return self._can_run()

    async def initialize(self) -> None:
        async with self._command():
            if not self.replay_mode:
                await self._core(
                    lambda: self._simulation.set_hybrid_control(self._selected_id)
                )

    async def fleet_round(self, should_run: Callable[[], bool] | None = None) -> None:
        async with self._command():
            if not self._can_run() or (should_run is not None and not should_run()):
                return
            await self._core(self._simulation.fleet_round)

    def _require_manual(self) -> None:
        selected = self._live_snapshot.frame.drone(self._selected_id)
        if selected.mode is not OperationalMode.MANUAL:
            raise ControlDeniedError("SELECTED DRONE NOT MANUAL")

    async def move(self, direction: Direction | str) -> None:
        async with self._command():
            if self.replay_mode:
                return
            self._require_manual()
            action = Direction(direction)
            await self._core(
                lambda: self._simulation.step(action, drone_id=self._selected_id)
            )

    async def scan(self) -> None:
        async with self._command():
            if self.replay_mode:
                return
            self._require_manual()
            await self._core(lambda: self._simulation.scan(self._selected_id))

    async def _select(self, identifier: str) -> None:
        self.view_snapshot.frame.drone(identifier)
        if self.replay_mode:
            self._selected_id = identifier
            return
        await self._core(
            lambda: self._simulation.set_hybrid_control(identifier),
            selection_after=identifier,
        )

    async def select(self, identifier: str) -> None:
        async with self._command():
            await self._select(identifier)

    async def next_drone(self) -> None:
        async with self._command():
            ids = [drone.identifier for drone in self.view_snapshot.frame.drones]
            identifier = ids[(ids.index(self._selected_id) + 1) % len(ids)]
            await self._select(identifier)

    async def set_control(self, mode: OperationalMode | str) -> None:
        async with self._command():
            if self.replay_mode:
                return
            requested = OperationalMode(mode)
            await self._core(
                lambda: self._simulation.set_hybrid_control(
                    self._selected_id, requested
                )
            )

    async def toggle_control(self) -> None:
        async with self._command():
            if self.replay_mode:
                return
            selected = self._live_snapshot.frame.drone(self._selected_id)
            mode = (
                OperationalMode.AUTO
                if selected.mode is OperationalMode.MANUAL
                else OperationalMode.MANUAL
            )
            await self._core(
                lambda: self._simulation.set_hybrid_control(self._selected_id, mode)
            )

    def _enter_replay(self) -> None:
        if not self.replay_mode:
            self._saved_live_selection = self._selected_id
            self._replay_history = self._live_history
            self._replay_index = len(self._live_history.snapshots) - 1

    def _exit_replay(self) -> None:
        if self.replay_mode:
            self._selected_id = self._saved_live_selection
            self._replay_history = None

    async def enter_replay(self) -> None:
        async with self._command():
            self._enter_replay()

    async def exit_replay(self) -> None:
        async with self._command():
            self._exit_replay()

    async def toggle_replay(self) -> None:
        async with self._command():
            if self.replay_mode:
                self._exit_replay()
            else:
                self._enter_replay()

    def seek(self, delta: int) -> None:
        if type(delta) is not int:
            raise ValueError("replay seek must be an integer")
        if self._replay_history is not None:
            self._replay_index = max(
                0,
                min(
                    len(self._replay_history.snapshots) - 1,
                    self._replay_index + delta,
                ),
            )
