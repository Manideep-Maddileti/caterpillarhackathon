"""Entrypoint for the telemetry simulator.

Run from the backend/ directory (relative imports require module
execution, not running this file directly):

    python -m telemetry_simulator.simulator
    python -m telemetry_simulator.simulator --interval 5 --machines 5

All configuration is env-driven (see config.py / backend/.env) — the CLI
flags below are convenience overrides for quick experimentation, not a
replacement for the env-based config.

Replaces the old live_telemetry_client.py: same job (POST realistic
telemetry to /api/telemetry/report on an interval), rebuilt as a modular,
physics- and event-driven simulator instead of pure random jitter.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import httpx

from .config import SimulatorConfig, get_config
from .scheduler import Scheduler
from .sender import TelemetrySender
from .state_manager import StateManager


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Realistic fleet telemetry simulator.")
    parser.add_argument("--url", dest="backend_base_url", default=None,
                         help="Backend base URL (overrides BACKEND_BASE_URL)")
    parser.add_argument("--interval", dest="update_interval_seconds", type=float, default=None,
                         help="Seconds between updates (overrides UPDATE_INTERVAL_SECONDS)")
    parser.add_argument("--machines", dest="number_of_machines", type=int, default=None,
                         help="Max machines to simulate (overrides NUMBER_OF_MACHINES)")
    parser.add_argument("--log-level", dest="log_level", default=None,
                         help="Logging level (overrides LOG_LEVEL)")
    parser.add_argument("--no-gps", dest="enable_gps_movement", action="store_false", default=None,
                         help="Disable GPS movement")
    parser.add_argument("--no-events", dest="enable_failure_events", action="store_false", default=None,
                         help="Disable failure/anomaly events")
    return parser.parse_args()


def _build_config(args: argparse.Namespace) -> SimulatorConfig:
    overrides = {name: value for name, value in vars(args).items() if value is not None}
    return get_config(overrides=overrides)


def _configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    # httpx/httpcore log every single request at INFO, which drowns out
    # our own event logs — quiet them unless the user explicitly wants
    # full DEBUG output.
    if level_name.upper() != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


async def run(config: SimulatorConfig) -> None:
    async with httpx.AsyncClient() as http_client:
        state_manager = StateManager(config)
        machines = await state_manager.load_or_bootstrap(http_client)

        sender = TelemetrySender(config)
        scheduler = Scheduler(config, sender, state_manager)
        await scheduler.run(machines, http_client)


def main() -> int:
    args = _parse_args()
    config = _build_config(args)
    _configure_logging(config.log_level)

    logger = logging.getLogger(__name__)
    logger.info(
        "Telemetry simulator starting — backend=%s, machines<=%d, interval=%.0fs (jitter ±%.0fs)",
        config.backend_base_url, config.number_of_machines,
        config.update_interval_seconds, config.update_jitter_seconds,
    )

    try:
        asyncio.run(run(config))
    except KeyboardInterrupt:
        # Fallback for Windows' known asyncio + Ctrl+C edge case, where a
        # raw KeyboardInterrupt can occasionally bypass scheduler.py's
        # signal.signal()-based graceful shutdown. In that case state is
        # current as of the last periodic snapshot (see
        # scheduler.MIN_SNAPSHOT_INTERVAL_SECONDS) rather than the exact
        # instant of the interrupt — a few seconds stale at worst, never a
        # crash or corrupt snapshot.
        logger.info("Interrupted — exiting (state saved as of the last periodic snapshot).")
        return 0
    except Exception:
        logger.exception("Simulator crashed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
