"""Safety-net checks only. Actual live telemetry (GPS/fuel/runtime/idle)
no longer changes here — that's driven externally by the telemetry_simulator
package POSTing to /api/telemetry/report every ~10s, like a real IoT feed.
This module just re-runs alert/anomaly/maintenance checks on an interval so
they stay fresh even if the external simulator isn't running (e.g. right
after seeding, or between simulator restarts).
"""
from sqlalchemy.orm import Session

from app.services import alert_service, anomaly_service, maintenance_service


def run_safety_net_checks(db: Session) -> None:
    alert_service.run_overdue_check(db)
    anomaly_service.run_anomaly_detection(db)
    maintenance_service.run_predictive_maintenance(db)
