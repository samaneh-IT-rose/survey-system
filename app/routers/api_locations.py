# -*- coding: utf-8 -*-
"""API استان‌ها و شهرستان‌ها — تغذیه کمبوباکس‌های وابسته."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import County, Province

router = APIRouter(prefix="/api", tags=["locations"])


@router.get("/provinces")
def list_provinces(db: Session = Depends(get_db)):
    rows = db.scalars(select(Province).order_by(Province.id)).all()
    return [{"id": p.id, "name": p.name} for p in rows]


@router.get("/counties")
def list_counties(province_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(County).where(County.province_id == province_id).order_by(County.name)
    ).all()
    return [{"id": c.id, "name": c.name, "province_id": c.province_id} for c in rows]
