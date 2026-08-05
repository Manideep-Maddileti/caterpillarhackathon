from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import alert_service, anomaly_service, forecast_service, maintenance_service

router = APIRouter(prefix="/api", tags=["dashboard"])

# Rough daily rental rate by equipment type, for revenue estimation
# (no real Payments data in this MVP).
DAY_RATE = {"Excavator": 250, "Crane": 400, "Bulldozer": 300, "Grader": 220}


@router.get("/dashboard/summary")
def get_summary(db: Session = Depends(get_db)):
    equipment = db.query(models.Equipment).all()
    total = len(equipment) or 1
    rented = sum(1 for e in equipment if e.status == "rented")
    total_runtime = sum(e.runtime_hours or 0 for e in equipment)
    total_idle = sum(e.idle_hours or 0 for e in equipment)
    total_fuel = sum(e.fuel_usage or 0 for e in equipment)

    per_site = defaultdict(float)
    site_codes = {s.id: s.site_code for s in db.query(models.Site).all()}
    for e in equipment:
        key = site_codes.get(e.assigned_site_id, "Unassigned")
        per_site[key] += e.runtime_hours or 0

    revenue = 0.0
    for rental in db.query(models.Rental).all():
        eq = rental.equipment
        rate = DAY_RATE.get(eq.type, 200) if eq else 200
        revenue += (rental.rental_days or 0) * rate

    return {
        "total_equipment": len(equipment),
        "rented_equipment": rented,
        "utilization_pct": round(rented / total * 100, 1),
        "total_rented_hours": round(total_runtime, 1),
        "total_idle_hours": round(total_idle, 1),
        "idle_pct": round(total_idle / (total_runtime + total_idle) * 100, 1) if (total_runtime + total_idle) else 0,
        "downtime_equipment": sum(1 for e in equipment if e.status == "available"),
        "total_fuel_usage": round(total_fuel, 1),
        "usage_per_site": [{"site": k, "hours": round(v, 1)} for k, v in per_site.items()],
        "revenue_estimate": round(revenue, 2),
    }


@router.get("/alerts", response_model=list[schemas.NotificationOut])
def get_alerts(db: Session = Depends(get_db)):
    return (
        db.query(models.Notification)
        .order_by(models.Notification.severity.desc(), models.Notification.created_at.desc())
        .all()
    )


@router.post("/alerts/refresh")
def refresh_alerts(db: Session = Depends(get_db)):
    overdue = alert_service.run_overdue_check(db)
    anomalies = anomaly_service.run_anomaly_detection(db)
    return {"overdue_alerts": len(overdue), "anomalies": len(anomalies)}


@router.get("/forecast")
def get_forecast(db: Session = Depends(get_db)):
    return forecast_service.run_demand_forecast(db)


@router.get("/anomalies")
def get_anomalies(db: Session = Depends(get_db)):
    return anomaly_service.run_anomaly_detection(db)


@router.get("/maintenance")
def get_maintenance(db: Session = Depends(get_db)):
    return maintenance_service.run_predictive_maintenance(db)
