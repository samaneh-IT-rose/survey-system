# -*- coding: utf-8 -*-
"""API داشبورد — آمار با فیلتر (بخش ۱۲ و ۱۴ سند)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.dashboard import build_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(
    q: str | None = None,
    province_id: int | None = None,
    county_id: int | None = None,
    contact_option_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
):
    return build_dashboard(
        db,
        q=q,
        province_id=province_id,
        county_id=county_id,
        contact_option_id=contact_option_id,
        date_from=date_from,
        date_to=date_to,
    )
