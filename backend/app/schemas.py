from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_code: str
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    company: Optional[str] = None
    contact: Optional[str] = None


class CustomerCreate(BaseModel):
    name: str
    company: Optional[str] = None
    contact: Optional[str] = None


class SiteCreate(BaseModel):
    site_code: str
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class EquipmentCreate(BaseModel):
    equipment_code: str
    name: Optional[str] = None
    type: str
    assigned_site_id: Optional[int] = None


class TenureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    designated_lat: Optional[float] = None
    designated_lng: Optional[float] = None
    assigned_since: Optional[datetime] = None
    tenure_days: Optional[int] = None
    last_compliant: Optional[bool] = None
    last_compliance_check: Optional[datetime] = None


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipment_code: str
    name: Optional[str] = None
    type: str
    status: str
    assigned_customer_id: Optional[int] = None
    assigned_site_id: Optional[int] = None
    runtime_hours: float
    fuel_usage: float
    idle_hours: float
    engine_health: float
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    last_operator_id: Optional[str] = None
    return_date: Optional[datetime] = None
    assigned_customer: Optional[CustomerOut] = None
    assigned_site: Optional[SiteOut] = None
    tenure: Optional[TenureOut] = None


class RentalCreate(BaseModel):
    equipment_id: int
    customer_id: Optional[int] = None
    site_id: Optional[int] = None
    return_date: Optional[datetime] = None
    rental_days: Optional[int] = None


class RentalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipment_id: int
    customer_id: Optional[int] = None
    site_id: Optional[int] = None
    status: str
    qr_code: Optional[str] = None
    check_in_date: Optional[datetime] = None
    check_out_date: Optional[datetime] = None
    return_date: Optional[datetime] = None
    rental_days: Optional[int] = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    severity: str
    message: str
    equipment_id: Optional[int] = None
    rental_id: Optional[int] = None
    recommended_action: Optional[str] = None
    created_at: datetime
    read: bool


class ForecastOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_id: Optional[int] = None
    equipment_type: str
    predicted_demand: Optional[float] = None
    window: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TelemetryReport(BaseModel):
    equipment_code: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    fuel_usage: Optional[float] = None
    runtime_hours: Optional[float] = None
    idle_hours: Optional[float] = None
