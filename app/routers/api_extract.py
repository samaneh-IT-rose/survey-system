# -*- coding: utf-8 -*-
"""API استخراج آزاد داده از تمام فرم‌ها (نسخهٔ 1.7.0).

- GET /api/extract/schema        — فرم‌های مجاز کاربر + سؤال‌های هر فرم + ستون‌های پایه
- GET /api/extract               — ردیف‌ها با ستون‌های انتخابی (دسترسی «فقط خواندنی»)
- GET /api/extract/excel         — همان خروجی در قالب اکسل (دسترسی «خروجی اکسل»)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..auth import api_require_perm
from ..constants import PERM_EXPORT, PERM_VIEW
from ..database import get_db
from ..models import User
from ..services.extract import build_extract, build_extract_excel, extract_schema
from ..utils.activity import log_activity

router = APIRouter(prefix="/api/extract", tags=["extract"])


def _params(
    forms: str | None = None,
    fields: str | None = None,
    q: str | None = None,
    province_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """پارس پارامترهای مشترک کوئری — فهرست‌ها با کاما جدا می‌شوند."""
    return {
        "forms": [f for f in (forms or "").split(",") if f.strip()],
        "fields": [f for f in (fields or "").split(",") if f.strip()],
        "q": q,
        "province_id": province_id,
        "date_from": date_from,
        "date_to": date_to,
    }


@router.get("/schema")
def get_schema(user: User = Depends(api_require_perm(PERM_VIEW)), db: Session = Depends(get_db)):
    return extract_schema(db, user)


@router.get("")
def extract_data(
    forms: str | None = None,
    fields: str | None = None,
    q: str | None = None,
    province_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: User = Depends(api_require_perm(PERM_VIEW)),
    db: Session = Depends(get_db),
):
    return build_extract(db, user, **_params(forms, fields, q, province_id, date_from, date_to))


@router.get("/excel")
def extract_excel(
    request: Request,
    forms: str | None = None,
    fields: str | None = None,
    q: str | None = None,
    province_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: User = Depends(api_require_perm(PERM_EXPORT)),
    db: Session = Depends(get_db),
):
    content, filename = build_extract_excel(db, user, **_params(forms, fields, q, province_id, date_from, date_to))
    log_activity(db, request, user, "extract_excel", f"استخراج داده — {filename}")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
