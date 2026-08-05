"""Ingests one live telemetry reading for one equipment, exactly like a real
IoT device or field gateway would push. This is the sole source of ongoing
"real-time" data now — driven externally by the telemetry_simulator package
calling POST /api/telemetry/report every ~10s, not an in-process random
jitter.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app import models
from app.services import alert_service, anomaly_service, maintenance_service


def report_telemetry(
    db: Session,
    equipment_code: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    fuel_usage: Optional[float] = None,
    runtime_hours: Optional[float] = None,
    idle_hours: Optional[float] = None,
) -> dict:
    equipment = db.query(models.Equipment).filter(models.Equipment.equipment_code == equipment_code).first()
    if not equipment:
        return {"error": f"No equipment found with code {equipment_code}"}

    if lat is not None and lng is not None:
        equipment.gps_lat, equipment.gps_lng = lat, lng
    if fuel_usage is not None:
        equipment.fuel_usage = round(max(0.0, fuel_usage), 1)
    if runtime_hours is not None:
        equipment.runtime_hours = round(max(0.0, runtime_hours), 1)
    if idle_hours is not None:
        equipment.idle_hours = round(max(0.0, idle_hours), 1)
        equipment.engine_health = round(max(20.0, min(100.0, 100 - equipment.idle_hours * 3)), 1)

    db.add(models.Telemetry(
        equipment_id=equipment.id,
        timestamp=datetime.utcnow(),
        lat=lat,
        lng=lng,
        fuel=fuel_usage,
        status=equipment.status,
        engine_hours=runtime_hours,
        idle_hours=idle_hours,
    ))
    db.commit()

    alert_service.run_overdue_check(db)
    anomaly_service.run_anomaly_detection(db)
    maintenance_service.run_predictive_maintenance(db)

    return {
        "equipment_code": equipment_code,
        "gps_lat": equipment.gps_lat,
        "gps_lng": equipment.gps_lng,
        "fuel_usage": equipment.fuel_usage,
        "runtime_hours": equipment.runtime_hours,
        "idle_hours": equipment.idle_hours,
        "engine_health": equipment.engine_health,
    }
