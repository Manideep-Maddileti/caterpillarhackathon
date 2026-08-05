"""One-shot seed of the dealer + a personalized 10-vehicle fleet, loaded
from the first 10 rows of the real CSV dataset in data/. This app is scoped
to one dealer who owns/manages exactly this fleet — not the full 350-row
dataset — so every screen (dashboard, map, agents) reasons about only these
machines. All site coordinates are real Indian cities (never outside India).

Ongoing "real-time" telemetry no longer comes from an in-process random
jitter — it's driven by the external live_telemetry_client.py script
POSTing to /api/telemetry/report every ~10s, exactly like a real IoT feed
would. See app/main.py for the (much lighter) internal safety-net loop that
just re-runs alert/anomaly/maintenance checks without touching telemetry.

Seeds 4 active rentals (one due tomorrow, one overdue, two comfortably
on-time) out of the 10 vehicles, so the dealer's "what's out right now"
view has a realistic mix the moment the app starts.
"""
import csv
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session

from app import models

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "synthetic_rental_tracking_data.csv"

FLEET_SIZE = 10

# Real Indian city coordinates — every site (and therefore every equipment
# position/jitter around it) is anchored to one of these, so the fleet never
# renders outside India. Kept generous beyond the seeded sites so the
# AI assistant's "equipment near <city>" tool has a useful reference set.
INDIAN_CITIES = {
    "Bangalore": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Hyderabad": (17.3850, 78.4867),
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Delhi": (28.7041, 77.1025),
    "Kolkata": (22.5726, 88.3639),
    "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873),
    "Kochi": (9.9312, 76.2673),
}

# Which real Indian city each seeded site code is placed in.
SITE_CITY = {
    "S002": "Chennai",
    "S012": "Hyderabad",
    "S006": "Mumbai",
    "S011": "Pune",
    "S007": "Delhi",
    "S004": "Kolkata",
}

# How far a machine's designated spot can sit from its site's centroid, so
# equipment sharing a site don't all render on top of each other on the map.
DESIGNATED_SPREAD_DEG = 0.05


def _designated_offset(equipment_code: str) -> tuple[float, float]:
    """Deterministic per-equipment jitter (stable across restarts, unlike
    random.uniform) so each machine gets a distinct designated spot within
    its site instead of stacking exactly on the site centroid."""
    digest = hashlib.md5(equipment_code.encode()).hexdigest()
    dx = (int(digest[:4], 16) / 0xFFFF - 0.5) * 2 * DESIGNATED_SPREAD_DEG
    dy = (int(digest[4:8], 16) / 0xFFFF - 0.5) * 2 * DESIGNATED_SPREAD_DEG
    return dx, dy


def _engine_health(idle_hours: float) -> float:
    # Deliberately mild at seed time (real degradation comes from live simulation
    # over time) so the anomaly feed isn't flooded the instant the app starts.
    return round(max(55.0, min(100.0, 100 - idle_hours * 1.5)), 1)


def _get_or_create_site(db: Session, sites_cache: dict, site_code: str) -> models.Site | None:
    if not site_code or site_code.upper() == "NULL":
        return None
    if site_code in sites_cache:
        return sites_cache[site_code]
    city = SITE_CITY.get(site_code, "Bangalore")
    lat, lng = INDIAN_CITIES[city]
    site = models.Site(site_code=site_code, name=f"Site {site_code} ({city})", lat=lat, lng=lng)
    db.add(site)
    db.flush()
    sites_cache[site_code] = site
    return site


def _load_fleet_from_csv(db: Session) -> dict[str, models.Equipment]:
    sites_cache: dict[str, models.Site] = {}
    equipment_by_code: dict[str, models.Equipment] = {}

    with open(DATA_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= FLEET_SIZE:
                break

            code = row["Equipment ID"].strip()
            eq_type = row["Type"].strip()
            site = _get_or_create_site(db, sites_cache, row["Site ID"].strip())

            check_in = datetime.strptime(row["Check-In Date"].strip(), "%Y-%m-%d")
            check_out = datetime.strptime(row["Check-Out Date"].strip(), "%Y-%m-%d")
            engine_h = float(row["Engine Hours/Day"])
            idle_h = float(row["Idle Hours/Day"])
            fuel = float(row["Fuel Usage (L/Day)"])
            rental_days = int(float(row["Rental Days"]))
            operator = row["Last Operator ID"].strip()
            operator = None if operator.upper() == "NULL" else operator

            designated_lat = designated_lng = None
            if site:
                dx, dy = _designated_offset(code)
                designated_lat, designated_lng = site.lat + dx, site.lng + dy

            equipment = models.Equipment(
                equipment_code=code,
                name=f"{eq_type} {code}",
                type=eq_type,
                status="available",
                assigned_site_id=site.id if site else None,
                runtime_hours=engine_h,
                fuel_usage=fuel,
                idle_hours=idle_h,
                engine_health=_engine_health(idle_h),
                last_operator_id=operator,
                return_date=check_out,
                gps_lat=designated_lat,
                gps_lng=designated_lng,
            )
            db.add(equipment)
            db.flush()
            equipment_by_code[code] = equipment

            db.add(models.EquipmentTenure(
                equipment_id=equipment.id,
                site_id=site.id if site else None,
                designated_lat=designated_lat,
                designated_lng=designated_lng,
                assigned_since=check_in,
                tenure_days=max(0, (datetime.utcnow() - check_in).days),
                last_compliance_check=datetime.utcnow(),
                last_compliant=True,
            ))

            db.add(models.UsageLog(
                equipment_id=equipment.id,
                date=check_in,
                runtime_hours=engine_h,
                engine_hours=engine_h,
                idle_hours=idle_h,
                fuel_usage=fuel,
                operator_id=operator,
            ))

            # Historical rental — no customer on record for these (the real
            # dataset only tracks equipment/usage, not who rented it), which
            # is exactly why the app's flow requires creating a customer
            # before a NEW rental can be made.
            db.add(models.Rental(
                equipment_id=equipment.id,
                customer_id=None,
                site_id=site.id if site else None,
                status="completed",
                check_in_date=check_in,
                check_out_date=check_out,
                return_date=check_out,
                rental_days=rental_days,
            ))

    return equipment_by_code


def seed_if_empty(db: Session):
    if db.query(models.Dealer).first():
        return  # already seeded

    dealer = models.Dealer(name="Demo Dealer", email="dealer@rental.com", password="demo123")
    db.add(dealer)
    db.flush()

    equipment_by_code = _load_fleet_from_csv(db)
    db.flush()

    # 4 of the 10 vehicles are actively rented right now, with a realistic
    # mix of due dates, so the dealer's live-status view isn't empty/uniform
    # the moment the app starts.
    now = datetime.utcnow()
    demo_customers = [
        models.Customer(name="Acme Construction", company="Acme Infra Pvt Ltd", contact="acme@example.com"),
        models.Customer(name="BuildRight Co", company="BuildRight Contractors", contact="buildright@example.com"),
        models.Customer(name="Metro Infra Works", company="Metro Infra Works Ltd", contact="metro@example.com"),
        models.Customer(name="Skyline Builders", company="Skyline Builders Pvt Ltd", contact="skyline@example.com"),
    ]
    db.add_all(demo_customers)
    db.flush()

    codes = list(equipment_by_code.keys())
    # (equipment code, checked out N days ago, return date, rental_days label)
    rental_plan = [
        (codes[0], 5, now + timedelta(hours=20), 6),    # due tomorrow
        (codes[1], 10, now - timedelta(days=2), 8),      # overdue
        (codes[2], 3, now + timedelta(days=5), 8),       # comfortably on-time
        (codes[3], 2, now + timedelta(days=10), 12),     # comfortably on-time
    ] if len(codes) >= 4 else []

    for i, (code, checked_out_days_ago, return_date, rental_days) in enumerate(rental_plan):
        eq = equipment_by_code[code]
        eq.status = "overdue" if return_date < now else "rented"
        eq.assigned_customer_id = demo_customers[i].id
        eq.return_date = return_date  # overwrite the stale historical check-out date from the CSV import
        db.add(models.Rental(
            equipment_id=eq.id,
            customer_id=demo_customers[i].id,
            site_id=eq.assigned_site_id,
            status="active",
            check_in_date=now - timedelta(days=checked_out_days_ago),
            return_date=return_date,
            rental_days=rental_days,
        ))

    db.commit()
