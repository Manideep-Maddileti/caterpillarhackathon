import base64
import io
from datetime import datetime, timedelta

import qrcode
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import alert_service, anomaly_service

router = APIRouter(prefix="/api/rentals", tags=["rentals"])


def _generate_qr_data_url(payload: str) -> str:
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


@router.get("", response_model=list[schemas.RentalOut])
def list_rentals(db: Session = Depends(get_db)):
    return db.query(models.Rental).order_by(models.Rental.created_at.desc()).all()


@router.post("", response_model=schemas.RentalOut)
def create_rental(payload: schemas.RentalCreate, db: Session = Depends(get_db)):
    equipment = db.query(models.Equipment).get(payload.equipment_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="Equipment not found")
    if equipment.status == "rented":
        raise HTTPException(status_code=400, detail="Equipment is already rented")

    return_date = payload.return_date or (datetime.utcnow() + timedelta(days=payload.rental_days or 7))

    rental = models.Rental(
        equipment_id=payload.equipment_id,
        customer_id=payload.customer_id,
        site_id=payload.site_id,
        status="created",
        return_date=return_date,
        rental_days=payload.rental_days,
    )
    db.add(rental)
    db.flush()

    rental.qr_code = _generate_qr_data_url(f"RENTAL:{rental.id}:{equipment.equipment_code}")
    db.commit()
    db.refresh(rental)
    return rental


@router.post("/{rental_id}/checkout", response_model=schemas.RentalOut)
def checkout_rental(rental_id: int, db: Session = Depends(get_db)):
    """Simulated QR/manual scan: equipment leaves the yard, rental becomes active."""
    rental = db.query(models.Rental).get(rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    if rental.status not in ("created",):
        raise HTTPException(status_code=400, detail=f"Cannot check out rental in status '{rental.status}'")

    rental.status = "active"
    rental.check_in_date = datetime.utcnow()

    equipment = rental.equipment
    equipment.status = "rented"
    equipment.assigned_customer_id = rental.customer_id
    if rental.site_id:
        equipment.assigned_site_id = rental.site_id
    equipment.return_date = rental.return_date

    db.commit()
    db.refresh(rental)
    return rental


@router.post("/{rental_id}/checkin", response_model=schemas.RentalOut)
def checkin_rental(rental_id: int, db: Session = Depends(get_db)):
    """Simulated QR/manual scan: equipment returns, rental completed."""
    rental = db.query(models.Rental).get(rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    if rental.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot check in rental in status '{rental.status}'")

    rental.status = "completed"
    rental.check_out_date = datetime.utcnow()

    equipment = rental.equipment
    equipment.status = "available"
    equipment.assigned_customer_id = None

    db.commit()

    alert_service.run_overdue_check(db)
    anomaly_service.run_anomaly_detection(db)

    db.refresh(rental)
    return rental
