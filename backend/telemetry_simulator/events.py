"""Occasional anomalies and operating-state transitions layered on top of
physics.py's baseline drift.

Call order contract (enforced by scheduler.py, not by this module): for
each tick, physics.step() must run BEFORE apply_events() — threshold
events (LowFuel, Overheating, MaintenanceRequired) react to the CURRENT
tick's freshly-computed values.

Two families of events:

- Threshold/condition-triggered: fire when a physics value crosses a line
  (fuel low, temperature high, health critical). Cooldown-gated so they
  re-remind periodically instead of firing every tick while the condition
  persists — like a dashboard warning light, not a spam alert.
- Genuinely probabilistic: GeofenceViolation, UnexpectedMovement,
  SensorFailure. Per-hour probabilities, converted to a per-tick chance,
  each independently cooldown-gated.

Recovery events (Refuel, MaintenancePerformed) are the ONLY things that
ever move fuel_level up or engine_health up — keeping physics.py's
"only decreases" invariants honest by construction.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .config import SimulatorConfig
from .machine import MachineState, OperatingState, utcnow
from .physics import EARTH_METERS_PER_DEGREE_LAT, clamp

Severity = Literal["info", "warning", "critical"]

# Fields SensorFailure is allowed to corrupt — all target-seeking in
# physics.py, so a glitched value self-heals within a tick or two instead
# of permanently corrupting a cumulative counter (fuel/hours are excluded
# on purpose; see module docstring).
_SENSOR_FAILURE_CANDIDATE_FIELDS = ("engine_temperature", "rpm", "hydraulic_pressure", "battery_voltage")


class MachineEvent(BaseModel):
    """A single fired event, returned for logging (and, later, could be
    surfaced to the backend/UI)."""

    machine_id: str
    event_type: str
    severity: Severity
    message: str
    timestamp: datetime = Field(default_factory=utcnow)


def _km_offset(lat: float, lng: float, distance_km: float, bearing_degrees: float) -> tuple[float, float]:
    """Same local flat-earth approximation as physics.py's GPS helper, but
    taking an absolute distance in km and bearing — used to place a machine
    a known distance from a reference point (its home coordinates) for the
    geofence/movement events."""
    distance_m = distance_km * 1000.0
    bearing_rad = math.radians(bearing_degrees)
    dlat = (distance_m * math.cos(bearing_rad)) / EARTH_METERS_PER_DEGREE_LAT
    meters_per_degree_lng = EARTH_METERS_PER_DEGREE_LAT * math.cos(math.radians(lat))
    dlng = (distance_m * math.sin(bearing_rad)) / meters_per_degree_lng if meters_per_degree_lng else 0.0
    new_lat = clamp(lat + dlat, -90.0, 90.0)
    new_lng = ((lng + dlng + 180.0) % 360.0) - 180.0
    return new_lat, new_lng


def _per_tick_probability(prob_per_hour: float, config: SimulatorConfig) -> float:
    return prob_per_hour * (config.update_interval_seconds / 3600.0)


def _change_operating_state(state: MachineState, new_state: OperatingState, reason: str) -> MachineEvent:
    old_state = state.operating_state
    state.operating_state = new_state
    state.operating_state_since = utcnow()
    return MachineEvent(
        machine_id=state.machine_id,
        event_type="StateChange",
        severity="info",
        message=f"{reason} ({old_state.value} -> {new_state.value})",
    )


# ---------------- Duty-cycle state transitions ----------------

def maybe_transition_state(
    state: MachineState, elapsed_seconds: float, config: SimulatorConfig, rng: random.Random
) -> Optional[MachineEvent]:
    """OFF <-> RUNNING <-> IDLE duty cycle. MAINTENANCE is a separate
    excursion, entered only via maybe_maintenance_required and exited only
    via maybe_maintenance_performed — never touched here."""
    if not config.enable_state_transitions:
        return None
    if state.operating_state == OperatingState.MAINTENANCE:
        return None

    tick_fraction = elapsed_seconds / config.update_interval_seconds
    roll = rng.random()

    if state.operating_state == OperatingState.OFF:
        if roll < config.prob_off_to_running_per_tick * tick_fraction:
            return _change_operating_state(state, OperatingState.RUNNING, "Engine started")

    elif state.operating_state == OperatingState.RUNNING:
        if roll < config.prob_running_to_idle_per_tick * tick_fraction:
            return _change_operating_state(state, OperatingState.IDLE, "Machine now idling")

    elif state.operating_state == OperatingState.IDLE:
        p_to_running = config.prob_idle_to_running_per_tick * tick_fraction
        p_to_off = config.prob_idle_to_off_per_tick * tick_fraction
        if roll < p_to_running:
            return _change_operating_state(state, OperatingState.RUNNING, "Resumed active operation")
        if roll < p_to_running + p_to_off:
            return _change_operating_state(state, OperatingState.OFF, "Engine shut down")

    return None


# ---------------- Threshold-triggered events ----------------

def maybe_low_fuel(state: MachineState, config: SimulatorConfig) -> Optional[MachineEvent]:
    if not config.enable_failure_events:
        return None
    if state.fuel_level >= config.fuel_low_threshold_pct:
        return None
    if not state.can_fire_event("LowFuel", config.event_cooldown_seconds):
        return None
    state.mark_event_fired("LowFuel")
    return MachineEvent(
        machine_id=state.machine_id, event_type="LowFuel", severity="warning",
        message=f"Fuel low: {state.fuel_level:.1f}%",
    )


def maybe_overheating(state: MachineState, config: SimulatorConfig) -> Optional[MachineEvent]:
    if not config.enable_failure_events:
        return None
    if state.engine_temperature <= config.overheating_threshold_c:
        return None
    if not state.can_fire_event("Overheating", config.event_cooldown_seconds):
        return None
    state.mark_event_fired("Overheating")
    return MachineEvent(
        machine_id=state.machine_id, event_type="Overheating", severity="critical",
        message=f"Engine overheating: {state.engine_temperature:.1f}C",
    )


def maybe_maintenance_required(state: MachineState, config: SimulatorConfig) -> Optional[MachineEvent]:
    if not config.enable_failure_events:
        return None
    if state.operating_state == OperatingState.MAINTENANCE:
        return None
    if state.engine_health >= config.maintenance_required_threshold_pct:
        return None
    if not state.can_fire_event("MaintenanceRequired", config.event_cooldown_seconds):
        return None
    state.mark_event_fired("MaintenanceRequired")
    state.operating_state = OperatingState.MAINTENANCE
    state.operating_state_since = utcnow()
    return MachineEvent(
        machine_id=state.machine_id, event_type="MaintenanceRequired", severity="critical",
        message=f"Engine health critical ({state.engine_health:.1f}%) - entering maintenance",
    )


# ---------------- Recovery events ----------------

def maybe_refuel(state: MachineState, config: SimulatorConfig, rng: random.Random) -> Optional[MachineEvent]:
    """The only path by which fuel_level ever increases. More likely the
    closer to empty the tank is — models an operator/dealer responding to
    a low-fuel situation rather than refueling at random."""
    if not config.enable_recovery_events:
        return None
    if state.fuel_level >= config.fuel_low_threshold_pct:
        return None
    urgency = 1.0 - (state.fuel_level / config.fuel_low_threshold_pct)  # 0..1, higher when nearer empty
    prob = 0.05 * urgency
    if rng.random() >= prob:
        return None
    old_fuel = state.fuel_level
    state.fuel_level = config.fuel_refuel_target_pct
    return MachineEvent(
        machine_id=state.machine_id, event_type="Refuel", severity="info",
        message=f"Refueled: {old_fuel:.1f}% -> {state.fuel_level:.1f}%",
    )


def maybe_maintenance_performed(state: MachineState, config: SimulatorConfig, rng: random.Random) -> Optional[MachineEvent]:
    """The only path by which engine_health ever increases. Requires a
    minimum time in MAINTENANCE before it can complete, modeling real
    repair time (scaled down for a demo-friendly cadence)."""
    if not config.enable_recovery_events:
        return None
    if state.operating_state != OperatingState.MAINTENANCE:
        return None
    if state.seconds_in_current_state() < 60.0:
        return None
    if rng.random() >= 0.1:
        return None
    old_health = state.engine_health
    state.engine_health = config.maintenance_restored_health_pct
    state.operating_state = OperatingState.OFF
    state.operating_state_since = utcnow()
    return MachineEvent(
        machine_id=state.machine_id, event_type="MaintenancePerformed", severity="info",
        message=f"Maintenance complete: health {old_health:.1f}% -> {state.engine_health:.1f}%",
    )


# ---------------- Rare probabilistic anomalies ----------------

def maybe_geofence_violation(state: MachineState, config: SimulatorConfig, rng: random.Random) -> Optional[MachineEvent]:
    """Places the machine well outside its designated radius from home —
    models the machine being found somewhere it shouldn't be (unauthorized
    transport, misreported delivery, etc). Can happen regardless of
    operating state."""
    if not config.enable_failure_events:
        return None
    if not state.can_fire_event("GeofenceViolation", config.event_cooldown_seconds):
        return None
    if rng.random() >= _per_tick_probability(config.prob_geofence_violation_per_hour, config):
        return None

    state.mark_event_fired("GeofenceViolation")
    state.active_event = "GeofenceViolation"
    state.active_event_until = utcnow() + timedelta(minutes=config.geofence_violation_duration_minutes)

    bearing = rng.uniform(0.0, 360.0)
    distance_km = config.geofence_radius_km * rng.uniform(1.2, 1.8)
    state.latitude, state.longitude = _km_offset(state.home_latitude, state.home_longitude, distance_km, bearing)

    return MachineEvent(
        machine_id=state.machine_id, event_type="GeofenceViolation", severity="critical",
        message=f"Outside designated geofence: {distance_km:.1f}km from home",
    )


def maybe_unexpected_movement(state: MachineState, config: SimulatorConfig, rng: random.Random) -> Optional[MachineEvent]:
    """Movement while the machine SHOULD be stationary (OFF or
    MAINTENANCE) — a theft/tamper-style signal, distinct from
    GeofenceViolation which can occur at any operating state."""
    if not config.enable_failure_events:
        return None
    if not state.expected_stationary:
        return None
    if not state.can_fire_event("UnexpectedMovement", config.event_cooldown_seconds):
        return None
    if rng.random() >= _per_tick_probability(config.prob_unexpected_movement_per_hour, config):
        return None

    state.mark_event_fired("UnexpectedMovement")
    state.active_event = "UnexpectedMovement"
    state.active_event_until = utcnow() + timedelta(minutes=config.unexpected_movement_duration_minutes)

    bearing = rng.uniform(0.0, 360.0)
    distance_km = rng.uniform(0.5, 2.0)
    state.latitude, state.longitude = _km_offset(state.latitude, state.longitude, distance_km, bearing)

    return MachineEvent(
        machine_id=state.machine_id, event_type="UnexpectedMovement", severity="critical",
        message=f"Unexpected movement while {state.operating_state.value}: moved {distance_km:.1f}km",
    )


def _garble_value(field: str, state: MachineState, config: SimulatorConfig, rng: random.Random) -> float:
    if field == "engine_temperature":
        return rng.choice([config.engine_temp_min_c - 10.0, config.engine_temp_max_c + 30.0])
    if field == "rpm":
        return 0.0 if state.operating_state == OperatingState.RUNNING else rng.uniform(3000.0, 4000.0)
    if field == "hydraulic_pressure":
        return 0.0 if state.is_operating else rng.uniform(3500.0, 4500.0)
    if field == "battery_voltage":
        return rng.choice([0.0, config.battery_max_voltage + 1.0])
    return getattr(state, field)  # pragma: no cover — defensive fallback


def tick_sensor_failure_recovery(state: MachineState) -> None:
    """Counts down an in-progress sensor failure. Must be called once per
    tick, before maybe_sensor_failure, so a failure set to last N ticks
    actually clears after N ticks."""
    if state.sensor_failure_ticks_remaining > 0:
        state.sensor_failure_ticks_remaining -= 1


def maybe_sensor_failure(state: MachineState, config: SimulatorConfig, rng: random.Random) -> Optional[MachineEvent]:
    """Corrupts one self-correcting field for a short window — see module
    docstring for why fuel/hours are never candidates."""
    if not config.enable_failure_events:
        return None
    if state.sensor_failure_ticks_remaining > 0:
        return None  # already mid-failure; let it run its course
    if not state.can_fire_event("SensorFailure", config.event_cooldown_seconds):
        return None
    if rng.random() >= _per_tick_probability(config.prob_sensor_failure_per_hour, config):
        return None

    state.mark_event_fired("SensorFailure")
    field = rng.choice(_SENSOR_FAILURE_CANDIDATE_FIELDS)
    glitch_value = _garble_value(field, state, config, rng)
    setattr(state, field, glitch_value)
    state.sensor_failure_ticks_remaining = config.sensor_failure_duration_ticks

    return MachineEvent(
        machine_id=state.machine_id, event_type="SensorFailure", severity="warning",
        message=f"{field} sensor glitch: reported {glitch_value:.1f}",
    )


# ---------------- Orchestrator ----------------

def apply_events(
    state: MachineState, elapsed_seconds: float, config: SimulatorConfig, rng: random.Random
) -> list[MachineEvent]:
    """Run the full event pipeline for one tick. Must be called AFTER
    physics.step() for this tick — see module docstring."""
    events: list[MachineEvent] = []

    tick_sensor_failure_recovery(state)

    for fn in (
        maybe_transition_state,
    ):
        event = fn(state, elapsed_seconds, config, rng)
        if event:
            events.append(event)

    for fn in (maybe_low_fuel, maybe_overheating, maybe_maintenance_required):
        event = fn(state, config)
        if event:
            events.append(event)

    for fn in (maybe_refuel, maybe_maintenance_performed, maybe_geofence_violation,
               maybe_unexpected_movement, maybe_sensor_failure):
        event = fn(state, config, rng)
        if event:
            events.append(event)

    return events
