from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services.telemetry_ingest import report_telemetry

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.post("/report")
def report(payload: schemas.TelemetryReport, db: Session = Depends(get_db)):
    """Ingest one live telemetry reading for one equipment — this is the
    endpoint live_telemetry_client.py calls every ~10s. Reusable by any
    future real IoT feed or webhook with the same payload shape."""
    return report_telemetry(
        db,
        equipment_code=payload.equipment_code,
        lat=payload.lat,
        lng=payload.lng,
        fuel_usage=payload.fuel_usage,
        runtime_hours=payload.runtime_hours,
        idle_hours=payload.idle_hours,
    )
