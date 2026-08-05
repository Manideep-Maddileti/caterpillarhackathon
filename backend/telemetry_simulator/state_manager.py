"""Owns the fleet's state lifecycle: load -> (scheduler drives updates) ->
save -> repeat.

On first run there's no local snapshot, so the fleet is bootstrapped from
the real backend's GET /api/equipment — reusing whatever real data already
exists (GPS, engine health, rental status, tenure/geofence anchor) instead
of starting from arbitrary constants. Every subsequent run resumes from the
local snapshot instead of re-bootstrapping, so restarting the simulator
doesn't reset the fleet's simulated life.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from pathlib import Path
from typing import Optional

import httpx
from pydantic import ValidationError

from .config import SimulatorConfig
from .machine import MachineState, OperatingState

logger = logging.getLogger(__name__)

# Backend rental `status` -> a reasonable initial guess at engine
# operating_state. Only used at bootstrap; the duty-cycle state machine in
# events.py owns everything after that.
_STATUS_TO_INITIAL_OPERATING_STATE = {
    "rented": OperatingState.RUNNING,
    "overdue": OperatingState.IDLE,
}

# Fallback GPS position (roughly the geographic center of India) used only
# if a piece of equipment somehow has no GPS at all yet.
_FALLBACK_LAT, _FALLBACK_LNG = 22.5, 78.9


class StateManager:
    """Loads/bootstraps and persists the fleet's MachineState collection."""

    def __init__(self, config: SimulatorConfig):
        self._config = config
        self._snapshot_path = Path(config.state_snapshot_path)

    # ---------------- Public API ----------------

    async def load_or_bootstrap(
        self, http_client: httpx.AsyncClient, rng: Optional[random.Random] = None
    ) -> dict[str, MachineState]:
        """Resume from the local snapshot if one exists; otherwise
        bootstrap fresh from the backend and write the first snapshot."""
        rng = rng or random.Random()

        snapshot = self._load_snapshot()
        if snapshot is not None:
            logger.info("Resuming %d machine(s) from local snapshot: %s", len(snapshot), self._snapshot_path)
            return snapshot

        logger.info("No local snapshot found — bootstrapping fleet from %s", self._config.equipment_list_url)
        machines = await self._bootstrap_from_backend(http_client, rng)
        self.save(machines)
        return machines

    def save(self, machines: dict[str, MachineState]) -> None:
        """Atomically write the current fleet state to the local snapshot
        file (write to a temp file, then replace — never leaves a
        partially-written snapshot on disk if interrupted)."""
        payload = {machine_id: machine.model_dump(mode="json") for machine_id, machine in machines.items()}
        tmp_path = self._snapshot_path.with_suffix(self._snapshot_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, self._snapshot_path)

    # ---------------- Bootstrap ----------------

    async def _bootstrap_from_backend(
        self, http_client: httpx.AsyncClient, rng: random.Random
    ) -> dict[str, MachineState]:
        raw_list = await self._fetch_equipment_with_retry(http_client)
        raw_list = raw_list[: self._config.number_of_machines]

        machines: dict[str, MachineState] = {}
        for raw in raw_list:
            machine = self._map_equipment_to_machine(raw, rng)
            machines[machine.machine_id] = machine

        logger.info("Bootstrapped %d machine(s) from backend", len(machines))
        return machines

    async def _fetch_equipment_with_retry(self, http_client: httpx.AsyncClient) -> list[dict]:
        last_error: Optional[Exception] = None
        max_attempts = self._config.http_max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                response = await http_client.get(
                    self._config.equipment_list_url, timeout=self._config.http_timeout_seconds
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == max_attempts:
                    break
                wait = self._config.http_retry_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Bootstrap fetch failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt, max_attempts, exc, wait,
                )
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"Could not bootstrap fleet from {self._config.equipment_list_url} "
            f"after {max_attempts} attempt(s)"
        ) from last_error

    def _map_equipment_to_machine(self, raw: dict, rng: random.Random) -> MachineState:
        tenure = raw.get("tenure") or {}
        site = raw.get("assigned_site") or {}

        gps_lat = raw.get("gps_lat")
        gps_lng = raw.get("gps_lng")
        home_lat = tenure.get("designated_lat")
        home_lng = tenure.get("designated_lng")

        if gps_lat is None or gps_lng is None:
            gps_lat = home_lat if home_lat is not None else _FALLBACK_LAT
            gps_lng = home_lng if home_lng is not None else _FALLBACK_LNG
        if home_lat is None or home_lng is None:
            home_lat, home_lng = gps_lat, gps_lng

        backend_status = raw.get("status") or "available"
        operating_state = _STATUS_TO_INITIAL_OPERATING_STATE.get(backend_status, OperatingState.OFF)

        runtime_hours = float(raw.get("runtime_hours") or 0.0)
        idle_hours = float(raw.get("idle_hours") or 0.0)

        # See module docstring: the backend's fuel_usage is litres/day, not
        # a true 0-100% gauge yet. Reused as an approximate seed, clamped
        # into range, rather than an arbitrary constant.
        fuel_seed = raw.get("fuel_usage")
        fuel_level = (
            min(100.0, max(5.0, float(fuel_seed))) if fuel_seed is not None else rng.uniform(40.0, 90.0)
        )

        engine_health = float(raw["engine_health"]) if raw.get("engine_health") is not None else 95.0
        starting_temp = self._config.ambient_temperature_c + (10.0 if operating_state != OperatingState.OFF else 0.0)

        return MachineState(
            machine_id=raw["equipment_code"],
            equipment_type=raw.get("type", "Unknown"),
            assigned_site=site.get("site_code"),
            status=backend_status,
            operating_state=operating_state,
            fuel_level=fuel_level,
            engine_temperature=starting_temp,
            engine_hours=runtime_hours + idle_hours,
            idle_hours=idle_hours,
            runtime_hours=runtime_hours,
            latitude=gps_lat,
            longitude=gps_lng,
            engine_health=engine_health,
            battery_voltage=self._config.battery_nominal_voltage + rng.uniform(-0.2, 0.2),
            hydraulic_pressure=0.0,
            rpm=0.0,
            home_latitude=home_lat,
            home_longitude=home_lng,
            heading_degrees=rng.uniform(0.0, 360.0),
        )

    # ---------------- Local snapshot ----------------

    def _load_snapshot(self) -> Optional[dict[str, MachineState]]:
        if not self._snapshot_path.exists():
            return None
        try:
            raw = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
            return {machine_id: MachineState.model_validate(data) for machine_id, data in raw.items()}
        except (json.JSONDecodeError, ValidationError, OSError) as exc:
            logger.warning(
                "Could not read snapshot at %s (%s) — ignoring and re-bootstrapping from backend",
                self._snapshot_path, exc,
            )
            return None
