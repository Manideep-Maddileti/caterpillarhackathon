"""Rule-based anomaly detection.

Kept as a standalone, callable service (not inlined in routes) so it can
later be exposed as a tool for an AI agent, or invoked from a cron/webhook.
"""
import math
from datetime import datetime
from sqlalchemy.orm import Session

from app import models

IDLE_HOURS_THRESHOLD = 15.0
ENGINE_HEALTH_THRESHOLD = 50.0
GEOFENCE_RADIUS_KM = 5.0
HIGH_FUEL_THRESHOLD = 70.0
MOVEMENT_THRESHOLD_KM = 1.0


def _haversine_km(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def check_geofence_compliance(db: Session, equipment: models.Equipment) -> dict | None:
    """Compare an equipment's live GPS to its designated tenure coordinates
    (app.models.EquipmentTenure), which is the per-asset "home" location —
    more precise than the shared Site centroid. Updates the tenure row's
    last_compliance_check/last_compliant as a side effect. Returns a finding
    dict if it's outside the geofence, else None.

    Exposed as its own function (not just inlined below) so the Fleet Agent
    can call it directly as a tool, independent of full anomaly detection.
    """
    tenure = (
        db.query(models.EquipmentTenure)
        .filter(models.EquipmentTenure.equipment_id == equipment.id)
        .first()
    )
    if not tenure or tenure.designated_lat is None or equipment.gps_lat is None:
        return None

    dist = _haversine_km(equipment.gps_lat, equipment.gps_lng, tenure.designated_lat, tenure.designated_lng)
    compliant = dist is None or dist <= GEOFENCE_RADIUS_KM
    tenure.last_compliance_check = datetime.utcnow()
    tenure.last_compliant = compliant

    if not compliant:
        since = tenure.assigned_since.date().isoformat() if tenure.assigned_since else "unknown"
        return {
            "reason": (
                f"Equipment is {dist:.1f}km from its designated coordinates "
                f"(assigned there since {since}, tenure {tenure.tenure_days or 0} days)"
            ),
            "severity": "critical",
            "recommended_action": "Verify equipment location; possible unauthorized movement — alert dealer",
        }
    return None


def detect_anomalies_for_equipment(db: Session, equipment: models.Equipment) -> list[dict]:
    """Pure function: given one equipment row, return list of anomaly dicts."""
    findings = []

    if equipment.idle_hours is not None and equipment.idle_hours > IDLE_HOURS_THRESHOLD:
        findings.append({
            "reason": f"Long idle hours ({equipment.idle_hours}h/day)",
            "severity": "warning",
            "recommended_action": "Investigate underutilization; consider reallocating equipment",
        })

    if equipment.assigned_site_id is None:
        findings.append({
            "reason": "Equipment has no assigned site",
            "severity": "warning",
            "recommended_action": "Assign equipment to a site or return it to the yard",
        })

    if equipment.status == "rented" and not equipment.last_operator_id:
        findings.append({
            "reason": "Rented equipment has no assigned operator",
            "severity": "warning",
            "recommended_action": "Confirm operator assignment for active rental",
        })

    geofence_finding = check_geofence_compliance(db, equipment)
    if geofence_finding:
        findings.append(geofence_finding)

    recent = (
        db.query(models.Telemetry)
        .filter(models.Telemetry.equipment_id == equipment.id)
        .order_by(models.Telemetry.timestamp.desc())
        .limit(2)
        .all()
    )
    if len(recent) == 2 and equipment.status != "rented":
        dist = _haversine_km(recent[0].lat, recent[0].lng, recent[1].lat, recent[1].lng)
        if dist is not None and dist > MOVEMENT_THRESHOLD_KM:
            findings.append({
                "reason": "Unexpected movement detected while equipment is not on an active rental",
                "severity": "critical",
                "recommended_action": "Investigate possible theft or unauthorized use",
            })

    if equipment.fuel_usage is not None:
        if equipment.fuel_usage == 0 and (equipment.runtime_hours or 0) > 0:
            findings.append({
                "reason": "Zero fuel usage despite logged engine runtime",
                "severity": "warning",
                "recommended_action": "Check fuel sensor / telemetry feed for this asset",
            })
        elif equipment.fuel_usage > HIGH_FUEL_THRESHOLD:
            findings.append({
                "reason": f"Unusually high fuel consumption ({equipment.fuel_usage}L)",
                "severity": "warning",
                "recommended_action": "Inspect for fuel leakage or misreporting",
            })

    active_rental = (
        db.query(models.Rental)
        .filter(models.Rental.equipment_id == equipment.id, models.Rental.status == "active")
        .first()
    )
    if active_rental and (equipment.runtime_hours or 0) == 0 and (equipment.idle_hours or 0) == 0:
        findings.append({
            "reason": "Rental is active but zero usage has been recorded",
            "severity": "warning",
            "recommended_action": "Verify equipment is powered on and reporting telemetry",
        })

    if equipment.engine_health is not None and equipment.engine_health < ENGINE_HEALTH_THRESHOLD:
        findings.append({
            "reason": f"Engine health degrading ({equipment.engine_health:.0f}%)",
            "severity": "critical",
            "recommended_action": "Schedule a maintenance inspection",
        })

    return findings


def run_anomaly_detection(db: Session) -> list[dict]:
    """Recompute anomalies for all equipment and persist as notifications."""
    db.query(models.Notification).filter(models.Notification.type == "anomaly").delete()

    results = []
    for equipment in db.query(models.Equipment).all():
        for finding in detect_anomalies_for_equipment(db, equipment):
            note = models.Notification(
                type="anomaly",
                severity=finding["severity"],
                message=finding["reason"],
                equipment_id=equipment.id,
                recommended_action=finding["recommended_action"],
                created_at=datetime.utcnow(),
            )
            db.add(note)
            results.append({
                "equipment_id": equipment.id,
                "equipment_code": equipment.equipment_code,
                **finding,
            })
    db.commit()
    return results
