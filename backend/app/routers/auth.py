from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    dealer = (
        db.query(models.Dealer)
        .filter(models.Dealer.email == payload.email, models.Dealer.password == payload.password)
        .first()
    )
    if not dealer:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Hackathon-simple: no real session/JWT, frontend just stores dealer id.
    return {"dealer_id": dealer.id, "name": dealer.name, "email": dealer.email, "token": f"demo-token-{dealer.id}"}
