"""Pure telemetry update functions — the "laws of physics" this simulated
fleet obeys.

Every function here takes the current MachineState, how much time elapsed,
and config, and mutates only the field(s) it owns. No function performs
I/O, logs, or knows anything about HTTP/events — that separation is what
lets events.py layer occasional anomalies on top without physics.py ever
needing to know they exist.

Randomness is passed in explicitly as a `random.Random` instance (one per
machine, owned by state_manager) rather than using the `random` module's
global state — keeps each machine's sequence independent and testable.
"""
from __future__ import annotations

import math
import random

from .config import SimulatorConfig
from .machine import MachineState, OperatingState, utcnow

EARTH_METERS_PER_DEGREE_LAT = 111_320.0


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _offset_by_heading(lat: float, distance_m: float, heading_degrees: float) -> tuple[float, float]:
    """Convert a distance + compass heading into a (dlat, dlng) offset,
    using a local flat-earth approximation — accurate enough for the small
    per-tick distances this simulator moves a machine."""
    heading_rad = math.radians(heading_degrees)
    dlat = (distance_m * math.cos(heading_rad)) / EARTH_METERS_PER_DEGREE_LAT
    meters_per_degree_lng = EARTH_METERS_PER_DEGREE_LAT * math.cos(math.radians(lat))
    dlng = (distance_m * math.sin(heading_rad)) / meters_per_degree_lng if meters_per_degree_lng else 0.0
    return dlat, dlng


# ---------------- Hours (engine / runtime / idle) ----------------

def update_hours(state: MachineState, elapsed_hours: float, config: SimulatorConfig) -> None:
    """Engine hours accrue whenever the engine is on (RUNNING or IDLE) —
    exactly like a real hour-meter. runtime_hours only accrues under load
    (RUNNING); idle_hours only while idling. All three are monotonic by
    construction: we only ever add to them."""
    if state.operating_state == OperatingState.RUNNING:
        state.runtime_hours += elapsed_hours
        state.engine_hours += elapsed_hours
    elif state.operating_state == OperatingState.IDLE:
        state.idle_hours += elapsed_hours
        state.engine_hours += elapsed_hours
    # OFF / MAINTENANCE: engine not running — nothing accrues.


# ---------------- Fuel ----------------

def update_fuel(state: MachineState, elapsed_hours: float, config: SimulatorConfig) -> None:
    """Fuel only decreases here — refueling is modeled as an event
    (events.py), never as baseline physics, so the "only increases via a
    refuel event" invariant is trivially true by construction."""
    if state.operating_state == OperatingState.RUNNING:
        burn = config.fuel_burn_pct_per_hour_running * elapsed_hours
    elif state.operating_state == OperatingState.IDLE:
        burn = config.fuel_burn_pct_per_hour_idle * elapsed_hours
    else:
        burn = 0.0
    state.fuel_level = clamp(state.fuel_level - burn, 0.0, 100.0)


# ---------------- Engine temperature ----------------

def update_engine_temperature(
    state: MachineState, elapsed_hours: float, config: SimulatorConfig, rng: random.Random
) -> None:
    """Drifts toward a state-dependent target at a bounded rate, so it
    rises under load, falls when idle/off, and never jumps — plus a small
    amount of sensor noise."""
    if state.operating_state == OperatingState.RUNNING:
        target = config.engine_temp_operating_c
        rate = config.engine_temp_rise_rate_c_per_hour
    elif state.operating_state == OperatingState.IDLE:
        # Still warm from running, but cooling toward a point between
        # ambient and full operating temperature.
        target = (config.engine_temp_operating_c + config.ambient_temperature_c) / 2
        rate = config.engine_temp_fall_rate_c_per_hour * 0.5
    else:  # OFF or MAINTENANCE
        target = config.ambient_temperature_c
        rate = config.engine_temp_fall_rate_c_per_hour

    max_delta = rate * elapsed_hours
    diff = target - state.engine_temperature
    delta = clamp(diff, -max_delta, max_delta)
    noise = rng.gauss(0.0, 0.3)
    new_temp = state.engine_temperature + delta + noise
    state.engine_temperature = clamp(new_temp, config.engine_temp_min_c, config.engine_temp_max_c)


# ---------------- Engine health ----------------

def update_engine_health(state: MachineState, elapsed_hours: float, config: SimulatorConfig) -> None:
    """Slow, cumulative wear — only while the engine is on, faster while
    overheating. Maintenance events (events.py) are the only thing that
    restores it; baseline physics only ever degrades it."""
    if not state.is_operating:
        return
    multiplier = (
        config.engine_health_decay_multiplier_when_hot
        if state.engine_temperature > config.overheating_threshold_c
        else 1.0
    )
    decay = config.engine_health_decay_pct_per_hour * multiplier * elapsed_hours
    state.engine_health = clamp(state.engine_health - decay, 0.0, 100.0)


# ---------------- Battery ----------------

def update_battery(state: MachineState, config: SimulatorConfig, rng: random.Random) -> None:
    """Drifts toward a state-dependent target voltage (charging while
    RUNNING, slow drain while OFF) with small random noise — models an
    alternator + battery, not an independent random reading."""
    if state.operating_state == OperatingState.RUNNING:
        target = config.battery_max_voltage - 0.2
    elif state.operating_state == OperatingState.IDLE:
        target = config.battery_nominal_voltage
    else:
        target = config.battery_nominal_voltage - 0.3

    smoothing = 0.3
    new_voltage = state.battery_voltage + (target - state.battery_voltage) * smoothing
    new_voltage += rng.gauss(0.0, config.battery_noise_stddev)
    state.battery_voltage = clamp(new_voltage, config.battery_min_voltage, config.battery_max_voltage)


# ---------------- Hydraulic pressure ----------------

def update_hydraulic_pressure(state: MachineState, config: SimulatorConfig, rng: random.Random) -> None:
    """Depends on activity: a real hydraulic system only pressurizes under
    active use. Smoothed toward a jittering in-range target rather than
    jumping to a fresh random value each tick."""
    if state.operating_state == OperatingState.RUNNING:
        lo, hi = config.hydraulic_pressure_running_min, config.hydraulic_pressure_running_max
    elif state.operating_state == OperatingState.IDLE:
        lo, hi = config.hydraulic_pressure_idle_min, config.hydraulic_pressure_idle_max
    else:
        lo, hi = 0.0, 0.0

    target = rng.uniform(lo, hi) if hi > lo else lo
    smoothing = 0.4
    new_pressure = state.hydraulic_pressure + (target - state.hydraulic_pressure) * smoothing
    state.hydraulic_pressure = clamp(new_pressure, 0.0, config.hydraulic_pressure_running_max)


# ---------------- RPM ----------------

def update_rpm(state: MachineState, config: SimulatorConfig, rng: random.Random) -> None:
    """Same smoothed-toward-target pattern as hydraulic pressure — RPM
    depends directly on whether/how the machine is being used."""
    if state.operating_state == OperatingState.RUNNING:
        lo, hi = config.rpm_running_min, config.rpm_running_max
    elif state.operating_state == OperatingState.IDLE:
        lo, hi = config.rpm_idle_min, config.rpm_idle_max
    else:
        lo, hi = 0.0, 0.0

    target = rng.uniform(lo, hi) if hi > lo else lo
    smoothing = 0.5
    new_rpm = state.rpm + (target - state.rpm) * smoothing
    state.rpm = clamp(new_rpm, 0.0, config.rpm_running_max)


# ---------------- GPS ----------------

def update_gps(
    state: MachineState, elapsed_seconds: float, config: SimulatorConfig, rng: random.Random
) -> None:
    """Moves the machine a small distance along a slowly-drifting heading.
    gps_step_meters_* is calibrated per the *configured* update interval
    (not per hour) so changing UPDATE_INTERVAL_SECONDS doesn't silently
    change how fast machines appear to travel.
    """
    if state.operating_state == OperatingState.RUNNING:
        step_meters = config.gps_step_meters_running
    elif state.operating_state == OperatingState.IDLE:
        step_meters = config.gps_step_meters_idle
    else:
        # Stationary, but real GPS receivers still jitter a little at rest.
        step_meters = config.gps_step_meters_idle * 0.05

    heading_delta = rng.uniform(-config.gps_heading_drift_degrees, config.gps_heading_drift_degrees)
    state.heading_degrees = (state.heading_degrees + heading_delta) % 360.0

    tick_fraction = elapsed_seconds / config.update_interval_seconds
    distance = step_meters * rng.uniform(0.4, 1.0) * tick_fraction

    dlat, dlng = _offset_by_heading(state.latitude, distance, state.heading_degrees)
    state.latitude = clamp(state.latitude + dlat, -90.0, 90.0)
    # Wrap longitude properly (not clamp) in case of antimeridian crossing.
    state.longitude = ((state.longitude + dlng + 180.0) % 360.0) - 180.0


# ---------------- Orchestrator ----------------

def step(
    state: MachineState, elapsed_seconds: float, config: SimulatorConfig, rng: random.Random
) -> MachineState:
    """Advance one machine's state by elapsed_seconds. Mutates and returns
    the same MachineState instance (caller owns persistence)."""
    elapsed_hours = elapsed_seconds / 3600.0

    update_hours(state, elapsed_hours, config)
    update_fuel(state, elapsed_hours, config)
    update_engine_temperature(state, elapsed_hours, config, rng)
    update_engine_health(state, elapsed_hours, config)
    update_battery(state, config, rng)
    update_hydraulic_pressure(state, config, rng)
    update_rpm(state, config, rng)
    if config.enable_gps_movement:
        update_gps(state, elapsed_seconds, config, rng)

    state.timestamp = utcnow()
    return state
