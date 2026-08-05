"""Central, environment-driven configuration for the telemetry simulator.

Every tunable constant lives here — physics.py and events.py never hardcode
a rate, threshold, or probability. This mirrors how a real fleet-management
deployment externalizes device firmware/config rather than baking constants
into logic, and makes the whole simulator reproducible/tunable without
touching code (just override env vars or backend/.env).

This module has no dependency on the FastAPI app — the simulator is a
standalone client of the HTTP API, the same way a real telematics unit
would be.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

# Load backend/.env if present (same convention as app/agents/llm.py) so a
# single .env file can hold both the API's secrets and the simulator's
# overrides. Real environment variables always take precedence over it.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw is not None else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw is not None else default


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


class SimulatorConfig(BaseModel):
    """Immutable simulator configuration, loaded once at startup via
    `SimulatorConfig.from_env()`."""

    model_config = ConfigDict(frozen=True)

    # ---------------- Backend connectivity ----------------
    backend_base_url: str = Field(
        default="http://127.0.0.1:8000",
        description="Base URL of the FastAPI backend.",
    )
    telemetry_report_path: str = Field(default="/api/telemetry/report")
    equipment_list_path: str = Field(
        default="/api/equipment",
        description="Used once at startup to bootstrap the fleet's initial state.",
    )
    http_timeout_seconds: float = Field(default=10.0, gt=0)
    http_max_retries: int = Field(default=3, ge=0)
    http_retry_backoff_seconds: float = Field(
        default=1.0, gt=0,
        description="Base delay for exponential backoff between retries.",
    )

    @property
    def telemetry_report_url(self) -> str:
        return f"{self.backend_base_url.rstrip('/')}{self.telemetry_report_path}"

    @property
    def equipment_list_url(self) -> str:
        return f"{self.backend_base_url.rstrip('/')}{self.equipment_list_path}"

    # ---------------- Timing ----------------
    update_interval_seconds: float = Field(
        default=10.0, gt=0,
        description="Nominal seconds between updates for a single machine.",
    )
    update_jitter_seconds: float = Field(
        default=2.0, ge=0,
        description=(
            "Max random +/- jitter applied to each machine's own interval, "
            "so machines never tick in lockstep — real devices don't share a clock."
        ),
    )

    # ---------------- Fleet sizing ----------------
    number_of_machines: int = Field(
        default=10, gt=0,
        description=(
            "Upper bound on how many machines to simulate. If the backend's "
            "fleet is larger, only the first N (by id) are simulated; if "
            "smaller, every real machine is simulated."
        ),
    )

    # ---------------- Feature flags ----------------
    enable_gps_movement: bool = Field(default=True)
    enable_failure_events: bool = Field(
        default=True,
        description="Master switch for LowFuel, Overheating, MaintenanceRequired, "
                     "GeofenceViolation, UnexpectedMovement, SensorFailure.",
    )
    enable_recovery_events: bool = Field(
        default=True,
        description="Master switch for Refuel and MaintenancePerformed events.",
    )
    enable_state_transitions: bool = Field(
        default=True,
        description="If False, every machine stays in its initial operating state forever.",
    )

    # ---------------- Local persistence ----------------
    state_snapshot_path: str = Field(
        default="telemetry_simulator_state.json",
        description=(
            "Crash-safe local snapshot of fleet state, written after every tick. "
            "On restart, state resumes from here instead of re-bootstrapping "
            "from the backend's seed values."
        ),
    )

    # ---------------- Fuel physics (percent of tank, 0-100) ----------------
    fuel_burn_pct_per_hour_running: float = Field(default=6.0, gt=0)
    fuel_burn_pct_per_hour_idle: float = Field(default=1.0, ge=0)
    fuel_low_threshold_pct: float = Field(
        default=15.0,
        description="Below this, the LowFuel event becomes eligible to fire.",
    )
    fuel_refuel_target_pct: float = Field(
        default=95.0,
        description="Fuel level a Refuel event restores the tank to (not always exactly 100 — realistic).",
    )

    # ---------------- Engine temperature physics (°C) ----------------
    ambient_temperature_c: float = Field(
        default=32.0,
        description="Baseline resting temperature the engine cools toward when OFF (fleet is in India).",
    )
    engine_temp_min_c: float = Field(default=45.0)
    engine_temp_max_c: float = Field(default=118.0)
    engine_temp_operating_c: float = Field(
        default=95.0,
        description="Steady-state temperature the engine drifts toward while RUNNING.",
    )
    engine_temp_rise_rate_c_per_hour: float = Field(default=40.0, gt=0)
    engine_temp_fall_rate_c_per_hour: float = Field(default=25.0, gt=0)
    overheating_threshold_c: float = Field(
        default=112.0,
        description="Above this, the Overheating event becomes eligible to fire.",
    )

    # ---------------- GPS / movement physics ----------------
    gps_step_meters_running: float = Field(default=25.0, ge=0)
    gps_step_meters_idle: float = Field(default=3.0, ge=0)
    gps_heading_drift_degrees: float = Field(
        default=20.0,
        description="Max change in heading per tick, so paths curve smoothly instead of zig-zagging.",
    )
    geofence_radius_km: float = Field(
        default=5.0,
        description="Matches the backend's own geofence radius (anomaly_service.GEOFENCE_RADIUS_KM).",
    )

    # ---------------- Engine health physics (percent, 0-100) ----------------
    engine_health_decay_pct_per_hour: float = Field(
        default=0.02, ge=0,
        description="Very slow — meant to matter over days/weeks of runtime, not minutes.",
    )
    engine_health_decay_multiplier_when_hot: float = Field(
        default=3.0, ge=1.0,
        description="Health degrades faster while temperature is above overheating_threshold_c.",
    )
    maintenance_required_threshold_pct: float = Field(default=40.0)
    maintenance_restored_health_pct: float = Field(default=97.0)

    # ---------------- Battery physics (volts) ----------------
    battery_nominal_voltage: float = Field(default=13.2)
    battery_noise_stddev: float = Field(default=0.15, ge=0)
    battery_min_voltage: float = Field(default=11.5)
    battery_max_voltage: float = Field(default=14.4)

    # ---------------- Hydraulic pressure physics (psi) ----------------
    hydraulic_pressure_running_min: float = Field(default=2000.0)
    hydraulic_pressure_running_max: float = Field(default=3200.0)
    hydraulic_pressure_idle_min: float = Field(default=150.0)
    hydraulic_pressure_idle_max: float = Field(default=450.0)

    # ---------------- RPM physics ----------------
    rpm_running_min: float = Field(default=1200.0)
    rpm_running_max: float = Field(default=2200.0)
    rpm_idle_min: float = Field(default=600.0)
    rpm_idle_max: float = Field(default=900.0)

    # ---------------- Operating-state duty cycle ----------------
    # Rough per-tick transition probabilities forming a simple duty-cycle
    # model (a machine doesn't run 24/7, nor idle forever). Tuned so a
    # machine's average "shift" lasts on the order of tens of minutes to a
    # couple of hours at the default 10s interval.
    prob_off_to_running_per_tick: float = Field(default=0.01, ge=0, le=1)
    prob_running_to_idle_per_tick: float = Field(default=0.015, ge=0, le=1)
    prob_idle_to_running_per_tick: float = Field(default=0.05, ge=0, le=1)
    prob_idle_to_off_per_tick: float = Field(default=0.01, ge=0, le=1)

    # ---------------- Event probabilities & cooldowns ----------------
    # Rare, edge/threshold-triggered events (LowFuel, Overheating,
    # MaintenanceRequired) are driven by physics crossing a threshold, not
    # raw probability — see events.py. These entries are for the genuinely
    # random ones.
    event_cooldown_seconds: float = Field(
        default=1800.0,
        description="Default minimum time between two firings of the same event type on the same machine.",
    )
    prob_geofence_violation_per_hour: float = Field(default=0.02, ge=0, le=1)
    prob_unexpected_movement_per_hour: float = Field(default=0.015, ge=0, le=1)
    prob_sensor_failure_per_hour: float = Field(default=0.03, ge=0, le=1)
    geofence_violation_duration_minutes: float = Field(default=15.0, gt=0)
    unexpected_movement_duration_minutes: float = Field(default=5.0, gt=0)
    sensor_failure_duration_ticks: int = Field(
        default=1, ge=1,
        description="How many consecutive ticks a sensor failure's garbled reading persists.",
    )

    # ---------------- Logging ----------------
    log_level: str = Field(default="INFO")

    @classmethod
    def from_env(cls) -> "SimulatorConfig":
        """Build config from environment variables (see field docs above
        for defaults). Env var names are the field names upper-cased."""
        values = {}
        for name, field_info in cls.model_fields.items():
            env_name = name.upper()
            if env_name not in os.environ:
                continue
            annotation = field_info.annotation
            if annotation is bool:
                values[name] = _env_bool(env_name, field_info.default)
            elif annotation is int:
                values[name] = _env_int(env_name, field_info.default)
            elif annotation is float:
                values[name] = _env_float(env_name, field_info.default)
            else:
                values[name] = _env_str(env_name, field_info.default)
        return cls(**values)


def get_config(overrides: Optional[dict] = None) -> SimulatorConfig:
    """Convenience factory: env-derived config, optionally overridden
    programmatically (useful for tests)."""
    config = SimulatorConfig.from_env()
    if overrides:
        config = config.model_copy(update=overrides)
    return config
