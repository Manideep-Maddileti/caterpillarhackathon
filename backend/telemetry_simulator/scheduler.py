"""Runs the fleet: one independent, jittered asyncio task per machine, plus
one periodic snapshot-saving task, until shutdown is requested.

Tick order contract for each machine, every interval:
    1. physics.step()   — advance monotonic/drifting fields
    2. apply_events()   — inject occasional anomalies/state transitions
    3. sender.send()    — POST the resulting telemetry to the backend

Machines never tick in lockstep — each has its own timer with independent
random jitter, exactly like real field devices that don't share a clock.

Windows note: graceful shutdown here uses signal.signal() (not
loop.add_signal_handler(), which raises NotImplementedError on Windows'
default event loop) and an interruptible wait instead of task cancellation,
so an in-flight tick always finishes its send before exiting. Windows'
asyncio + Ctrl+C handling has known edge cases where a raw KeyboardInterrupt
can bypass this entirely — simulator.py adds a top-level fallback so the
worst case is losing only the last few seconds since the previous periodic
snapshot, never a crash mid-write.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import signal

import httpx

from . import physics
from .config import SimulatorConfig
from .events import apply_events
from .machine import MachineState
from .sender import TelemetrySender
from .state_manager import StateManager

logger = logging.getLogger(__name__)

MIN_SNAPSHOT_INTERVAL_SECONDS = 20.0


def _stable_seed(machine_id: str) -> int:
    """Deterministic per-machine RNG seed (unlike Python's salted hash()) —
    same machine_id always gets the same sequence across restarts."""
    digest = hashlib.md5(machine_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


class Scheduler:
    """Owns the fleet's running loop: per-machine tick tasks, a periodic
    snapshot-saving task, and graceful shutdown."""

    def __init__(self, config: SimulatorConfig, sender: TelemetrySender, state_manager: StateManager):
        self._config = config
        self._sender = sender
        self._state_manager = state_manager
        self._shutdown_event = asyncio.Event()

    def request_shutdown(self) -> None:
        if not self._shutdown_event.is_set():
            logger.info("Shutdown requested — finishing in-flight ticks before exiting...")
        self._shutdown_event.set()

    async def run(self, machines: dict[str, MachineState], http_client: httpx.AsyncClient) -> None:
        """Run every machine's loop plus the snapshot saver until shutdown.
        Blocks until request_shutdown() is called (typically via Ctrl+C)."""
        self._install_signal_handlers()

        tasks = [
            asyncio.create_task(self._machine_loop(machine_id, machines, http_client), name=f"machine:{machine_id}")
            for machine_id in machines
        ]
        tasks.append(asyncio.create_task(self._snapshot_loop(machines), name="snapshot-saver"))

        logger.info(
            "Simulator running: %d machine(s), ~%.0fs interval (±%.0fs jitter). Press Ctrl+C to stop.",
            len(machines), self._config.update_interval_seconds, self._config.update_jitter_seconds,
        )

        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._state_manager.save(machines)
            logger.info("Final snapshot saved for %d machine(s). Shutdown complete.", len(machines))

    # ---------------- Internals ----------------

    def _install_signal_handlers(self) -> None:
        def _handler(signum, _frame):
            logger.info("Received signal %s", signum)
            self.request_shutdown()

        for sig_name in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                signal.signal(sig, _handler)
            except (OSError, ValueError, RuntimeError):
                logger.debug("Could not register a handler for %s on this platform", sig_name)

    async def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep up to `seconds`, waking immediately if shutdown is
        requested during the wait."""
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=max(0.0, seconds))
        except asyncio.TimeoutError:
            pass  # normal case: slept the full duration without a shutdown request

    async def _machine_loop(
        self, machine_id: str, machines: dict[str, MachineState], http_client: httpx.AsyncClient
    ) -> None:
        rng = random.Random(_stable_seed(machine_id))
        loop = asyncio.get_running_loop()
        last_tick = loop.time()

        # Stagger initial ticks so machines don't all send on the very
        # first iteration at once, even before jitter has a chance to act.
        await self._interruptible_sleep(rng.uniform(0.0, self._config.update_jitter_seconds))

        while not self._shutdown_event.is_set():
            now = loop.time()
            elapsed = now - last_tick
            last_tick = now

            state = machines[machine_id]
            physics.step(state, elapsed, self._config, rng)
            for event in apply_events(state, elapsed, self._config, rng):
                logger.info("[%s] %s: %s", event.machine_id, event.event_type, event.message)

            result = await self._sender.send(http_client, state)
            if not result.success:
                logger.warning("[%s] telemetry not delivered this tick: %s", machine_id, result.error)
            else:
                logger.debug("[%s] %s", machine_id, state.summary())

            if self._shutdown_event.is_set():
                break

            jitter = rng.uniform(-self._config.update_jitter_seconds, self._config.update_jitter_seconds)
            sleep_for = max(0.5, self._config.update_interval_seconds + jitter)
            await self._interruptible_sleep(sleep_for)

        logger.debug("[%s] machine loop exiting", machine_id)

    async def _snapshot_loop(self, machines: dict[str, MachineState]) -> None:
        interval = max(MIN_SNAPSHOT_INTERVAL_SECONDS, self._config.update_interval_seconds * 2)
        while not self._shutdown_event.is_set():
            await self._interruptible_sleep(interval)
            if self._shutdown_event.is_set():
                break
            self._state_manager.save(machines)
            logger.debug("Periodic snapshot saved (%d machines)", len(machines))
