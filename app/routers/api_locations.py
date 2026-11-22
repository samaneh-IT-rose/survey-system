# -*- coding: utf-8 -*-
"""API استان‌ها و شهرستان‌ها — تغذیه کمبوباکس‌های وابسته.

نسخهٔ 1.8.0: کاربرِ دارای محدودیت استانی فقط استان خودش را می‌بیند —
در کمبوباکس ثبت فرم، فیلتر آرشیو، فیلتر داشبورد و استخراج داده فقط همان
استان ظاهر می‌شود و شهرستان‌های استان دیگر قابل دریافت نیستند.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import api_user
from ..database import get_db
from ..models import County, Province, User
from ..services.scope import province_scope_id, user_province

router = APIRouter(prefix="/api", tags=["locations"], dependencies=[Depends(api_user)])


@router.get("/provinces")
def list_provinces(user: User = Depends(api_user), db: Session = Depends(get_db)):
    """فهرست استان‌ها — برای کاربرِ دارای استان فقط استان خودش."""
    scoped = user_province(user, db)
    if scoped is not None:
        return [{"id": scoped.id, "name": scoped.name}]
    rows = db.scalars(select(Province).order_by(Province.id)).all()
    return [{"id": p.id, "name": p.name} for p in rows]


@router.get("/counties")
def list_counties(
    province_id: int,
    user: User = Depends(api_user),
    db: Session = Depends(get_db),
):
    """شهرستان‌های یک استان — کاربرِ دارای استان فقط استان خودش را می‌تواند بگیرد."""
    scoped_pid = province_scope_id(user, db)
    if scoped_pid is not None and province_id != scoped_pid:
        raise HTTPException(403, detail={"message": "شما فقط به شهرستان‌های استان خودتان دسترسی دارید."})
    rows = db.scalars(
        select(County).where(County.province_id == province_id).order_by(County.name)
    ).all()
    return [{"id": c.id, "name": c.name, "province_id": c.province_id} for c in rows]
