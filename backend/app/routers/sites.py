from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/sites", tags=["sites"])


@router.get("", response_model=list[schemas.SiteOut])
def list_sites(db: Session = Depends(get_db)):
    return db.query(models.Site).all()


@router.post("", response_model=schemas.SiteOut)
def create_site(payload: schemas.SiteCreate, db: Session = Depends(get_db)):
    if db.query(models.Site).filter(models.Site.site_code == payload.site_code).first():
        raise HTTPException(status_code=400, detail="Site code already exists")
    site = models.Site(**payload.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site
