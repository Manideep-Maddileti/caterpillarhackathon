"""Rule-based demand forecasting: ranks equipment types by historical rental
frequency per site, no ML. Standalone callable service (agent-tool-ready).
"""
from collections import defaultdict
from sqlalchemy.orm import Session

from app import models


def run_demand_forecast(db: Session) -> list[dict]:
    """Rank equipment types by historical rental-day volume per site."""
    db.query(models.Forecast).delete()

    demand = defaultdict(float)  # (site_id, type) -> total rental days
    counts = defaultdict(int)    # (site_id, type) -> number of rentals

    equipment_by_id = {e.id: e for e in db.query(models.Equipment).all()}

    for usage in db.query(models.UsageLog).all():
        equipment = equipment_by_id.get(usage.equipment_id)
        if not equipment or not equipment.assigned_site_id:
            continue
        key = (equipment.assigned_site_id, equipment.type)
        demand[key] += usage.runtime_hours or 0
        counts[key] += 1

    for rental in db.query(models.Rental).all():
        equipment = equipment_by_id.get(rental.equipment_id)
        site_id = rental.site_id or (equipment.assigned_site_id if equipment else None)
        if not equipment or not site_id:
            continue
        key = (site_id, equipment.type)
        demand[key] += rental.rental_days or 0
        counts[key] += 1

    sites_by_id = {s.id: s for s in db.query(models.Site).all()}
    results = []
    for (site_id, eq_type), score in sorted(demand.items(), key=lambda kv: kv[1], reverse=True):
        forecast = models.Forecast(
            site_id=site_id,
            equipment_type=eq_type,
            predicted_demand=round(score, 1),
            window="next_30_days",
        )
        db.add(forecast)
        site = sites_by_id.get(site_id)
        results.append({
            "site_id": site_id,
            "site_code": site.site_code if site else None,
            "equipment_type": eq_type,
            "predicted_demand": round(score, 1),
            "rental_count": counts[(site_id, eq_type)],
            "window": "next_30_days",
        })

    db.commit()
    return results


def run_prepositioning_recommendations(db: Session, top_n: int = 5) -> list[dict]:
    """Turn the demand ranking into concrete pre-positioning actions: for
    each top-demand (site, equipment type) that doesn't already have a
    matching unit on-site, recommend moving the soonest-available matching
    unit there — 'now' if one's already free, or the date it next frees up
    from its current rental. This is what actually helps a dealer
    pre-position equipment, not just see a ranked list.
    """
    demand = run_demand_forecast(db)
    equipment = db.query(models.Equipment).all()
    sites_by_id = {s.id: s for s in db.query(models.Site).all()}

    recommendations = []
    for entry in demand[:top_n]:
        site_id, eq_type = entry["site_id"], entry["equipment_type"]

        already_present = any(e.type == eq_type and e.assigned_site_id == site_id for e in equipment)
        if already_present:
            continue

        candidates = [e for e in equipment if e.type == eq_type and e.assigned_site_id != site_id]
        if not candidates:
            continue

        available_now = [e for e in candidates if e.status == "available"]
        if available_now:
            pick, available_from = available_now[0], "now"
        else:
            with_return = [e for e in candidates if e.return_date]
            if not with_return:
                continue
            pick = min(with_return, key=lambda e: e.return_date)
            available_from = pick.return_date.date().isoformat()

        site = sites_by_id.get(site_id)
        recommendations.append({
            "site_code": site.site_code if site else None,
            "equipment_type": eq_type,
            "demand_score": entry["predicted_demand"],
            "recommend_moving": pick.equipment_code,
            "moving_from_site": pick.assigned_site.site_code if pick.assigned_site else "Unassigned",
            "available_from": available_from,
        })

    return recommendations
