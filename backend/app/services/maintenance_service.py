"""Rule-based predictive maintenance scoring. Deliberately explainable
(no ML model) so the Predictive Maintenance agent can cite exact reasons —
same design principle as anomaly_service and forecast_service. Standalone
callable service, agent-tool-ready.
"""
from datetime import datetime
from sqlalchemy.orm import Session

from app import models

HIGH_RISK_THRESHOLD = 60.0
MEDIUM_RISK_THRESHOLD = 35.0
LONG_TENURE_DAYS = 365


def score_equipment(db: Session, equipment: models.Equipment) -> dict:
    """Pure function: compute a 0-100 maintenance risk score for one asset."""
    reasons: list[str] = []
    score = 0.0

    health = equipment.engine_health if equipment.engine_health is not None else 100.0
    health_penalty = max(0.0, (100 - health)) * 0.6
    if health_penalty > 0:
        score += health_penalty
        reasons.append(f"engine health at {health:.0f}%")

    tenure = (
        db.query(models.EquipmentTenure)
        .filter(models.EquipmentTenure.equipment_id == equipment.id)
        .first()
    )
    tenure_days = tenure.tenure_days if tenure and tenure.tenure_days else 0
    if tenure_days > LONG_TENURE_DAYS:
        tenure_penalty = min(20.0, (tenure_days - LONG_TENURE_DAYS) / 30)
        score += tenure_penalty
        reasons.append(f"deployed continuously for {tenure_days} days without rotation")

    runtime = equipment.runtime_hours or 0
    idle = equipment.idle_hours or 0
    if idle > runtime * 2 and idle > 5:
        score += 10.0
        reasons.append(f"idle hours ({idle}h) far exceed active runtime ({runtime}h) — possible neglect")

    if (equipment.fuel_usage or 0) == 0 and runtime > 0:
        score += 15.0
        reasons.append("zero fuel usage despite logged runtime — sensor or engine fault likely")

    if tenure and tenure.last_compliant is False:
        score += 10.0
        reasons.append("currently outside its designated geofence")

    score = round(min(100.0, score), 1)
    if score >= HIGH_RISK_THRESHOLD:
        level, action = "high", "Schedule maintenance inspection within 48 hours"
    elif score >= MEDIUM_RISK_THRESHOLD:
        level, action = "medium", "Schedule a routine inspection this week"
    else:
        level, action = "low", "No action needed"

    return {
        "equipment_id": equipment.id,
        "equipment_code": equipment.equipment_code,
        "risk_score": score,
        "risk_level": level,
        "reasons": reasons,
        "recommended_action": action,
    }


def run_predictive_maintenance(db: Session, persist_alerts: bool = True) -> list[dict]:
    """Score the whole fleet, sorted by risk descending. High-risk assets are
    also persisted as notifications (type="maintenance") so they surface in
    the Alerts feed, same pattern as anomaly/overdue alerts.
    """
    if persist_alerts:
        db.query(models.Notification).filter(models.Notification.type == "maintenance").delete()

    results = []
    for equipment in db.query(models.Equipment).all():
        result = score_equipment(db, equipment)
        results.append(result)
        if persist_alerts and result["risk_level"] == "high":
            db.add(models.Notification(
                type="maintenance",
                severity="critical",
                message=f"{result['equipment_code']} is high maintenance risk ({result['risk_score']}/100): "
                        + "; ".join(result["reasons"]),
                equipment_id=equipment.id,
                recommended_action=result["recommended_action"],
                created_at=datetime.utcnow(),
            ))

    if persist_alerts:
        db.commit()

    return sorted(results, key=lambda r: r["risk_score"], reverse=True)
