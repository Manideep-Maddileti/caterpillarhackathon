"""LangChain tool wrappers around the existing service layer. Every tool
opens its own short-lived DB session (tool calls arrive from the LLM as
plain JSON args, not a request-scoped session) and stays READ-ONLY /
advisory — agents analyze and recommend, they don't mutate rentals or
equipment directly, so a model's tool-calling mistake can't corrupt data.
"""
import math
from typing import Optional

from langchain_core.tools import tool

from app.database import SessionLocal
from app import models
from app.seed import INDIAN_CITIES
from app.services import forecast_service, anomaly_service, maintenance_service


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


# ---------- Fleet Agent ----------

@tool
def get_fleet_overview() -> dict:
    """Get a high-level count of the fleet: total equipment, how many are
    available, rented, overdue, or unassigned to any site."""
    db = SessionLocal()
    try:
        equipment = db.query(models.Equipment).all()
        return {
            "total": len(equipment),
            "available": sum(1 for e in equipment if e.status == "available"),
            "rented": sum(1 for e in equipment if e.status == "rented"),
            "overdue": sum(1 for e in equipment if e.status == "overdue"),
            "unassigned_site": sum(1 for e in equipment if e.assigned_site_id is None),
        }
    finally:
        db.close()


@tool
def get_equipment_status(equipment_code: str) -> dict:
    """Get full live status for one equipment by its code (e.g. EQX1001):
    status, site, GPS, tenure/designated location, and compliance."""
    db = SessionLocal()
    try:
        e = db.query(models.Equipment).filter(models.Equipment.equipment_code == equipment_code).first()
        if not e:
            return {"error": f"No equipment found with code {equipment_code}"}
        tenure = db.query(models.EquipmentTenure).filter(models.EquipmentTenure.equipment_id == e.id).first()
        return {
            "equipment_code": e.equipment_code,
            "type": e.type,
            "status": e.status,
            "site": e.assigned_site.site_code if e.assigned_site else None,
            "gps": {"lat": e.gps_lat, "lng": e.gps_lng},
            "runtime_hours": e.runtime_hours,
            "idle_hours": e.idle_hours,
            "fuel_usage": e.fuel_usage,
            "engine_health": e.engine_health,
            "tenure_days": tenure.tenure_days if tenure else None,
            "designated_coords": {"lat": tenure.designated_lat, "lng": tenure.designated_lng} if tenure else None,
            "geofence_compliant": tenure.last_compliant if tenure else None,
        }
    finally:
        db.close()


@tool
def list_geofence_violations() -> dict:
    """List every equipment currently outside its designated coordinates
    (geofence violation) — use this to check for possible theft or
    unauthorized movement across the whole fleet."""
    db = SessionLocal()
    try:
        violations = []
        tenures = (
            db.query(models.EquipmentTenure)
            .filter(models.EquipmentTenure.last_compliant.is_(False))
            .all()
        )
        for t in tenures:
            e = t.equipment
            if not e:
                continue
            violations.append({
                "equipment_code": e.equipment_code,
                "type": e.type,
                "site": e.assigned_site.site_code if e.assigned_site else None,
                "designated_coords": {"lat": t.designated_lat, "lng": t.designated_lng},
                "live_coords": {"lat": e.gps_lat, "lng": e.gps_lng},
                "tenure_days": t.tenure_days,
            })
        return {"count": len(violations), "violations": violations}
    finally:
        db.close()


@tool
def search_equipment(query: str) -> dict:
    """Search equipment by code, type, status, or site code (partial, case
    insensitive match). Returns up to 20 matches."""
    db = SessionLocal()
    try:
        q = f"%{query.lower()}%"
        matches = (
            db.query(models.Equipment)
            .filter(
                (models.Equipment.equipment_code.ilike(q))
                | (models.Equipment.type.ilike(q))
                | (models.Equipment.status.ilike(q))
            )
            .limit(20)
            .all()
        )
        results = [
            {
                "equipment_code": e.equipment_code,
                "type": e.type,
                "status": e.status,
                "site": e.assigned_site.site_code if e.assigned_site else None,
            }
            for e in matches
        ]
        return {"count": len(results), "matches": results}
    finally:
        db.close()


@tool
def find_equipment_near_city(city: str, radius_km: float = 50) -> dict:
    """Find equipment whose live GPS position is within radius_km of a named
    Indian city — e.g. 'Bangalore', 'Chennai', 'Mumbai', 'Delhi', 'Hyderabad',
    'Pune', 'Kolkata', 'Ahmedabad', 'Jaipur', 'Kochi'. Use this for any
    'how many vehicles are near/around <place>' style question. All fleet
    coordinates are within India."""
    db = SessionLocal()
    try:
        match = next((coords for name, coords in INDIAN_CITIES.items() if name.lower() == city.strip().lower()), None)
        if not match:
            return {"error": f"Unknown city '{city}'. Known cities: {', '.join(INDIAN_CITIES.keys())}"}
        city_lat, city_lng = match

        results = []
        for e in db.query(models.Equipment).all():
            if e.gps_lat is None or e.gps_lng is None:
                continue
            dist = _haversine_km(e.gps_lat, e.gps_lng, city_lat, city_lng)
            if dist <= radius_km:
                results.append({
                    "equipment_code": e.equipment_code,
                    "type": e.type,
                    "status": e.status,
                    "distance_km": round(dist, 1),
                })
        results.sort(key=lambda r: r["distance_km"])
        return {"city": city, "radius_km": radius_km, "count": len(results), "equipment": results}
    finally:
        db.close()


# ---------- Rental Scheduling Agent ----------

@tool
def check_availability(equipment_type: Optional[str] = None, site_code: Optional[str] = None) -> dict:
    """Check which equipment is currently available to rent, optionally
    filtered by type (e.g. 'Excavator') and/or site code (e.g. 'S003').
    Does NOT create a rental — this is advisory only; the dealer still
    creates the rental themselves in the app after choosing a machine."""
    db = SessionLocal()
    try:
        query = db.query(models.Equipment).filter(models.Equipment.status == "available")
        if equipment_type:
            query = query.filter(models.Equipment.type.ilike(f"%{equipment_type}%"))
        if site_code:
            query = query.join(models.Site).filter(models.Site.site_code == site_code)
        results = [
            {"equipment_code": e.equipment_code, "type": e.type, "site": e.assigned_site.site_code if e.assigned_site else None}
            for e in query.limit(30).all()
        ]
        return {"count": len(results), "available_equipment": results}
    finally:
        db.close()


@tool
def get_rental_history(equipment_code: str) -> dict:
    """Get the rental history (past and active) for one equipment by code."""
    db = SessionLocal()
    try:
        e = db.query(models.Equipment).filter(models.Equipment.equipment_code == equipment_code).first()
        if not e:
            return {"error": f"No equipment found with code {equipment_code}"}
        rentals = db.query(models.Rental).filter(models.Rental.equipment_id == e.id).all()
        history = [
            {
                "status": r.status,
                "customer": r.customer.name if r.customer else None,
                "check_in_date": r.check_in_date.isoformat() if r.check_in_date else None,
                "return_date": r.return_date.isoformat() if r.return_date else None,
                "rental_days": r.rental_days,
            }
            for r in rentals
        ]
        return {"equipment_code": equipment_code, "count": len(history), "history": history}
    finally:
        db.close()


@tool
def get_overdue_rentals() -> dict:
    """List all rentals that are overdue or due back within 24 hours."""
    db = SessionLocal()
    try:
        notes = (
            db.query(models.Notification)
            .filter(models.Notification.type.in_(["overdue", "due_soon"]))
            .all()
        )
        results = [{"type": n.type, "message": n.message, "severity": n.severity} for n in notes]
        return {"count": len(results), "overdue_or_due_soon": results}
    finally:
        db.close()


# ---------- Demand Forecast Agent ----------

@tool
def get_demand_forecast(site_code: Optional[str] = None) -> dict:
    """Get the rule-based demand forecast ranking equipment types by
    historical rental volume, optionally filtered to one site code."""
    db = SessionLocal()
    try:
        results = forecast_service.run_demand_forecast(db)
        if site_code:
            results = [r for r in results if r.get("site_code") == site_code]
        return {"count": len(results), "forecast": results}
    finally:
        db.close()


@tool
def get_prepositioning_recommendations() -> dict:
    """Get concrete pre-positioning recommendations: for each high-demand
    site/equipment-type combo that doesn't already have a matching unit
    on-site, which specific equipment (by code) should be moved there and
    when it becomes available ('now', or a date if it's still on a rental).
    An empty list means the fleet is already well-positioned for demand —
    that's a valid, good answer, not a failure.
    Use this for any 'where should I preposition equipment' question."""
    db = SessionLocal()
    try:
        results = forecast_service.run_prepositioning_recommendations(db)
        return {"count": len(results), "recommendations": results}
    finally:
        db.close()


# ---------- Smart Alert Agent ----------

@tool
def get_active_alerts(severity: Optional[str] = None, alert_type: Optional[str] = None) -> dict:
    """Get current alerts/notifications, optionally filtered by severity
    (info/warning/critical) or type (overdue/due_soon/anomaly/maintenance)."""
    db = SessionLocal()
    try:
        query = db.query(models.Notification)
        if severity:
            query = query.filter(models.Notification.severity == severity)
        if alert_type:
            query = query.filter(models.Notification.type == alert_type)
        notes = query.order_by(models.Notification.created_at.desc()).limit(50).all()
        results = [
            {"type": n.type, "severity": n.severity, "message": n.message, "recommended_action": n.recommended_action}
            for n in notes
        ]
        return {"count": len(results), "alerts": results}
    finally:
        db.close()


@tool
def run_anomaly_scan() -> dict:
    """Run a fresh rule-based anomaly scan across the whole fleet (idle
    hours, unassigned equipment, geofence violations, fuel anomalies, zero
    usage on active rentals, degrading engine health) and return findings.
    An empty result means no anomalies right now — that's a valid, good
    answer, not a failure."""
    db = SessionLocal()
    try:
        results = anomaly_service.run_anomaly_detection(db)
        return {"count": len(results), "anomalies": results}
    finally:
        db.close()


@tool
def check_geofence_for_equipment(equipment_code: str) -> dict:
    """Check one specific equipment's live position against its designated
    coordinates and report whether it's in compliance."""
    db = SessionLocal()
    try:
        e = db.query(models.Equipment).filter(models.Equipment.equipment_code == equipment_code).first()
        if not e:
            return {"error": f"No equipment found with code {equipment_code}"}
        finding = anomaly_service.check_geofence_compliance(db, e)
        db.commit()
        if finding:
            return {"compliant": False, **finding}
        return {"compliant": True, "message": f"{equipment_code} is within its designated geofence"}
    finally:
        db.close()


# ---------- Predictive Maintenance Agent ----------

@tool
def get_maintenance_risk(equipment_code: str) -> dict:
    """Get the predictive maintenance risk score (0-100) and reasons for one
    equipment by code."""
    db = SessionLocal()
    try:
        e = db.query(models.Equipment).filter(models.Equipment.equipment_code == equipment_code).first()
        if not e:
            return {"error": f"No equipment found with code {equipment_code}"}
        return maintenance_service.score_equipment(db, e)
    finally:
        db.close()


@tool
def get_high_risk_equipment(limit: int = 10) -> dict:
    """Get the top N equipment by predictive maintenance risk score, highest
    risk first. Use this to answer 'what needs maintenance soon' questions."""
    db = SessionLocal()
    try:
        results = maintenance_service.run_predictive_maintenance(db, persist_alerts=False)[:limit]
        return {"count": len(results), "risk_ranking": results}
    finally:
        db.close()


FLEET_TOOLS = [get_fleet_overview, get_equipment_status, list_geofence_violations, search_equipment, find_equipment_near_city]
RENTAL_SCHEDULING_TOOLS = [check_availability, get_rental_history, get_overdue_rentals]
DEMAND_FORECAST_TOOLS = [get_demand_forecast, get_prepositioning_recommendations]
SMART_ALERT_TOOLS = [get_active_alerts, run_anomaly_scan, check_geofence_for_equipment]
PREDICTIVE_MAINTENANCE_TOOLS = [get_maintenance_risk, get_high_risk_equipment]
