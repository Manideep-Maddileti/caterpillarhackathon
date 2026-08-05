"""Overdue-return alerting. Standalone callable service (agent-tool-ready).
Real email sending is out of scope for the MVP — notifications are
logged/persisted as if sent.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app import models

DUE_SOON_WINDOW_HOURS = 24


def run_overdue_check(db: Session) -> list[dict]:
    db.query(models.Notification).filter(
        models.Notification.type.in_(["overdue", "due_soon"])
    ).delete(synchronize_session=False)

    now = datetime.utcnow()
    results = []

    active_rentals = (
        db.query(models.Rental)
        .filter(models.Rental.status.in_(["checked_out", "active"]))
        .all()
    )

    for rental in active_rentals:
        if not rental.return_date:
            continue
        equipment = rental.equipment
        if rental.return_date < now:
            kind, severity, msg = (
                "overdue",
                "critical",
                f"{equipment.equipment_code if equipment else 'Equipment'} is overdue "
                f"(was due {rental.return_date.date()})",
            )
        elif rental.return_date < now + timedelta(hours=DUE_SOON_WINDOW_HOURS):
            kind, severity, msg = (
                "due_soon",
                "warning",
                f"{equipment.equipment_code if equipment else 'Equipment'} is due back tomorrow "
                f"({rental.return_date.date()})",
            )
        else:
            continue

        note = models.Notification(
            type=kind,
            severity=severity,
            message=msg,
            equipment_id=rental.equipment_id,
            rental_id=rental.id,
            recommended_action="Contact customer to confirm return" if kind == "overdue"
            else "Send reminder to customer",
            created_at=now,
        )
        db.add(note)
        results.append({
            "rental_id": rental.id,
            "equipment_id": rental.equipment_id,
            "type": kind,
            "severity": severity,
            "message": msg,
        })

        if equipment and kind == "overdue":
            equipment.status = "overdue"

    db.commit()
    return results
