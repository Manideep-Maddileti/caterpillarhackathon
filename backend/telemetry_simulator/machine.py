"""The machine data model: a single source of truth for one piece of
equipment's state, carried from tick to tick.

Two state concepts live side by side here and must not be confused:

- ``status`` — the *business/rental* status from the backend
  (available/rented/overdue). The simulator treats this as read-only
  context; it never changes it.
- ``operating_state`` — the *engine* state this simulator actually drives
  (RUNNING/IDLE/OFF/MAINTENANCE). physics.py and events.py operate on this.

A real telematics unit has no idea what your rental business is doing with
the machine — it only knows whether the engine is on. This model mirrors
that separation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    """Timezone-aware UTC now — used throughout this package so elapsed-time
    math never risks a naive/aware datetime comparison bug."""
    return datetime.now(timezone.utc)


class OperatingState(str, Enum):
    """The machine's engine state. Distinct from the backend's rental
    ``status`` — see module docstring."""

    RUNNING = "RUNNING"
    IDLE = "IDLE"
    OFF = "OFF"
    MAINTENANCE = "MAINTENANCE"


class MachineState(BaseModel):
    """Full state of one simulated machine.

    Fields are grouped into: identity, operating state, reported telemetry
    (everything a real sensor would measure), and internal-only bookkeeping
    (never transmitted — used purely to make physics/events realistic).
    """

    model_config = ConfigDict(validate_assignment=True)

    # ---------------- Identity ----------------
    machine_id: str
    equipment_type: str
    assigned_site: Optional[str] = None
    status: Optional[str] = Field(
        default=None,
        description="Backend rental status (available/rented/overdue). Read-only context.",
    )

    # ---------------- Operating state ----------------
    operating_state: OperatingState = OperatingState.OFF
    operating_state_since: datetime = Field(default_factory=utcnow)

    # ---------------- Reported telemetry ----------------
    fuel_level: float = Field(ge=0.0, le=100.0, description="Percent of tank, 0-100.")
    engine_temperature: float = Field(description="Degrees Celsius.")
    engine_hours: float = Field(ge=0.0, description="Cumulative — only ever increases.")
    idle_hours: float = Field(ge=0.0, description="Cumulative while idle — only ever increases.")
    runtime_hours: float = Field(ge=0.0, description="Cumulative while active — only ever increases.")
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    engine_health: float = Field(ge=0.0, le=100.0)
    battery_voltage: float = Field(ge=0.0)
    hydraulic_pressure: float = Field(ge=0.0, description="PSI.")
    rpm: float = Field(ge=0.0)
    timestamp: datetime = Field(default_factory=utcnow)

    # ---------------- Internal-only (never transmitted) ----------------
    home_latitude: float = Field(
        description="Geofence anchor — captured at bootstrap, used to detect drift."
    )
    home_longitude: float
    heading_degrees: float = Field(
        default=0.0, ge=0.0, lt=360.0,
        description="Current direction of travel — drifts gradually for smooth GPS paths.",
    )
    event_last_fired_at: dict[str, datetime] = Field(
        default_factory=dict,
        description="Event name -> last time it fired, for cooldown enforcement.",
    )
    active_event: Optional[str] = Field(
        default=None, description="Name of a currently in-progress timed event, if any."
    )
    active_event_until: Optional[datetime] = Field(
        default=None, description="When the active_event should end."
    )
    sensor_failure_ticks_remaining: int = Field(default=0, ge=0)

    # ---------------- Convenience properties ----------------
    @property
    def is_operating(self) -> bool:
        """True while the engine is on (RUNNING or IDLE)."""
        return self.operating_state in (OperatingState.RUNNING, OperatingState.IDLE)

    @property
    def expected_stationary(self) -> bool:
        """True when the machine should NOT be moving (OFF or MAINTENANCE) —
        used by events.py to detect UnexpectedMovement."""
        return self.operating_state in (OperatingState.OFF, OperatingState.MAINTENANCE)

    def seconds_in_current_state(self, now: Optional[datetime] = None) -> float:
        now = now or utcnow()
        return max(0.0, (now - self.operating_state_since).total_seconds())

    def can_fire_event(self, event_name: str, cooldown_seconds: float, now: Optional[datetime] = None) -> bool:
        """Cooldown check — an event can't re-fire on this machine until
        cooldown_seconds have passed since it last fired."""
        last_fired = self.event_last_fired_at.get(event_name)
        if last_fired is None:
            return True
        now = now or utcnow()
        return (now - last_fired).total_seconds() >= cooldown_seconds

    def mark_event_fired(self, event_name: str, now: Optional[datetime] = None) -> None:
        # Mutate the dict in place and re-assign so validate_assignment sees
        # a change (a bare in-place dict mutation wouldn't trigger it, but
        # we don't need re-validation here — this is just bookkeeping).
        self.event_last_fired_at = {**self.event_last_fired_at, event_name: now or utcnow()}

    def summary(self) -> str:
        """One-line human-readable snapshot, for logging."""
        return (
            f"{self.machine_id} [{self.operating_state.value}] "
            f"fuel={self.fuel_level:.1f}% temp={self.engine_temperature:.1f}C "
            f"health={self.engine_health:.1f}% rpm={self.rpm:.0f} "
            f"pos=({self.latitude:.4f},{self.longitude:.4f})"
        )
