"""The only module that knows HTTP exists. Builds the outgoing payload from
a MachineState (mapping the simulator's rich internal fields down to
whatever the live POST /api/telemetry/report endpoint currently accepts)
and sends it with retry/backoff — structurally identical to what a real
telematics unit's radio firmware would do, and indistinguishable to the
backend from a real device.

KNOWN MAPPING COMPROMISE: the backend's only fuel field, `fuel_usage`, has
historically meant litres/day. This sender writes `fuel_level` (our 0-100%
gauge) into it, because that's the only fuel slot the live endpoint has.
Anything downstream still assuming fuel_usage means litres will misread it
as a percentage — flagged here, in state_manager.py, and in the original
architecture writeup. A real fix is adding a dedicated fuel_level column to
the backend; out of scope for this module.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from .config import SimulatorConfig
from .machine import MachineState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SendResult:
    """Outcome of one send() call — never raises, callers check .success."""

    success: bool
    status_code: Optional[int]
    error: Optional[str]
    attempts: int


class TelemetrySender:
    """Builds and POSTs one machine's telemetry payload per call. Stateless
    aside from config — safe to share across concurrently-ticking machine
    tasks (each call is independent)."""

    def __init__(self, config: SimulatorConfig):
        self._config = config

    def build_payload(self, state: MachineState) -> dict:
        """Map the simulator's rich internal MachineState down to the
        existing backend contract: {equipment_code, lat, lng, fuel_usage,
        runtime_hours, idle_hours}. See module docstring for the fuel_usage
        caveat. engine_temperature/battery/hydraulic_pressure/rpm are
        computed but not sent — the live endpoint has nowhere to put them
        yet."""
        return {
            "equipment_code": state.machine_id,
            "lat": round(state.latitude, 6),
            "lng": round(state.longitude, 6),
            "fuel_usage": round(state.fuel_level, 1),
            "runtime_hours": round(state.runtime_hours, 2),
            "idle_hours": round(state.idle_hours, 2),
        }

    async def send(self, http_client: httpx.AsyncClient, state: MachineState) -> SendResult:
        """POST one machine's telemetry, retrying with exponential backoff
        on failure. Never raises — returns a SendResult either way, so a
        single machine's transient network blip can't take down the
        fleet's tick loop."""
        payload = self.build_payload(state)
        max_attempts = self._config.http_max_retries + 1
        last_error: Optional[Exception] = None
        last_status: Optional[int] = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = await http_client.post(
                    self._config.telemetry_report_url,
                    json=payload,
                    timeout=self._config.http_timeout_seconds,
                )
                response.raise_for_status()
                logger.debug("Sent telemetry for %s (attempt %d): %s", state.machine_id, attempt, payload)
                return SendResult(success=True, status_code=response.status_code, error=None, attempts=attempt)

            except httpx.HTTPStatusError as exc:
                last_error = exc
                last_status = exc.response.status_code
            except httpx.HTTPError as exc:
                last_error = exc
                last_status = None

            if attempt == max_attempts:
                break
            wait = self._config.http_retry_backoff_seconds * (2 ** (attempt - 1))
            logger.warning(
                "Telemetry POST failed for %s (attempt %d/%d): %s - retrying in %.1fs",
                state.machine_id, attempt, max_attempts, last_error, wait,
            )
            await asyncio.sleep(wait)

        logger.error(
            "Telemetry POST permanently failed for %s after %d attempt(s): %s",
            state.machine_id, max_attempts, last_error,
        )
        return SendResult(success=False, status_code=last_status, error=str(last_error), attempts=max_attempts)
