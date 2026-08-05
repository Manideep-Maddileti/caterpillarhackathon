from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, ForeignKey, ForeignKeyConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class Dealer(Base):
    __tablename__ = "dealers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)  # hackathon: plaintext, swap for hash later


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    company = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Site(Base):
    __tablename__ = "sites"
    id = Column(Integer, primary_key=True, index=True)
    site_code = Column(String, unique=True, nullable=False)  # e.g. S003
    name = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)


class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(Integer, primary_key=True, index=True)
    equipment_code = Column(String, unique=True, nullable=False)  # e.g. EQX1001
    name = Column(String, nullable=True)
    type = Column(String, nullable=False)
    status = Column(String, default="available")  # available, rented, overdue, maintenance
    assigned_customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    assigned_site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    runtime_hours = Column(Float, default=0)
    fuel_usage = Column(Float, default=0)
    idle_hours = Column(Float, default=0)
    engine_health = Column(Float, default=100)  # 0-100 %
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    last_operator_id = Column(String, nullable=True)
    return_date = Column(DateTime, nullable=True)

    assigned_customer = relationship("Customer")
    assigned_site = relationship("Site")
    tenure = relationship("EquipmentTenure", uselist=False, viewonly=True)


class EquipmentTenure(Base):
    """Per-equipment 'home' assignment: the designated coordinates it should
    be operating at, and how long it's been assigned there. Decoupled from
    Site (which only has one centroid per site) so the geofence check and
    predictive-maintenance agent have a precise, per-asset reference point
    and a tenure duration to reason about — independent of the live,
    simulator-jittered GPS on Equipment itself.
    """
    __tablename__ = "equipment_tenure"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), unique=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    designated_lat = Column(Float, nullable=True)
    designated_lng = Column(Float, nullable=True)
    assigned_since = Column(DateTime, nullable=True)
    tenure_days = Column(Integer, nullable=True)  # how long it's been deployed at this location
    last_compliance_check = Column(DateTime, nullable=True)
    last_compliant = Column(Boolean, nullable=True)  # was it within geofence at last check

    equipment = relationship("Equipment")
    site = relationship("Site")


class Rental(Base):
    __tablename__ = "rentals"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    status = Column(String, default="created")  # created, checked_out, active, checked_in, completed
    qr_code = Column(String, nullable=True)  # base64 png
    check_in_date = Column(DateTime, nullable=True)   # rental start (checkout date)
    check_out_date = Column(DateTime, nullable=True)  # rental end (actual return)
    return_date = Column(DateTime, nullable=True)      # expected return
    rental_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment")
    customer = relationship("Customer")
    site = relationship("Site")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    rental_id = Column(Integer, ForeignKey("rentals.id"), nullable=True)
    amount = Column(Float, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


class Telemetry(Base):
    __tablename__ = "telemetry"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    fuel = Column(Float, nullable=True)
    status = Column(String, nullable=True)
    engine_hours = Column(Float, nullable=True)
    idle_hours = Column(Float, nullable=True)


class UsageLog(Base):
    __tablename__ = "usage_logs"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    runtime_hours = Column(Float, nullable=True)
    engine_hours = Column(Float, nullable=True)
    idle_hours = Column(Float, nullable=True)
    fuel_usage = Column(Float, nullable=True)
    operator_id = Column(String, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False)  # overdue, due_soon, anomaly
    severity = Column(String, default="info")  # info, warning, critical
    message = Column(String, nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=True)
    rental_id = Column(Integer, ForeignKey("rentals.id"), nullable=True)
    recommended_action = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)


class Forecast(Base):
    __tablename__ = "forecasts"
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    equipment_type = Column(String, nullable=False)
    predicted_demand = Column(Float, nullable=True)
    window = Column(String, nullable=True)  # e.g. "next_30_days"
    created_at = Column(DateTime, default=datetime.utcnow)


class Agreement(Base):
    """Stub table only — document storage out of scope for MVP."""
    __tablename__ = "agreements"
    id = Column(Integer, primary_key=True, index=True)
    rental_id = Column(Integer, ForeignKey("rentals.id"), nullable=True)
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
