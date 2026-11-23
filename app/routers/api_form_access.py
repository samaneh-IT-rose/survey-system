# -*- coding: utf-8 -*-
"""API سطح دسترسی فرم‌ها — قواعد دو لایهٔ «سطح استان» و «ادارهٔ استان» (نسخهٔ 1.9.0).

فقط مدیر سامانه: خواندن قواعد فعلی هر فرم و ذخیرهٔ تغییرات.
الگوی گارد endpoint-level مثل بقیهٔ مسیرهای مدیریتی (api_admin).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import api_admin
from ..database import get_db
from ..models import User
from ..services.form_access import ensure_form_access_rules, save_rules, serialize_rules
from ..utils.activity import log_activity

router = APIRouter(prefix="/api/form-access", tags=["form-access"])


@router.get("")
def get_form_access(admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    """قواعد فعلی همهٔ فرم‌ها — ردیف غایب به‌صورت پیش‌فرض ساخته می‌شود."""
    ensure_form_access_rules(db)
    return {"rules": serialize_rules(db)}


@router.put("")
def put_form_access(
    payload: dict,
    request: Request,
    admin: User = Depends(api_admin),
    db: Session = Depends(get_db),
):
    """ذخیرهٔ قواعد لایه‌ها — ورودی: {"rules": [{form_key, visible_to_province, visible_to_department}]}."""
    items = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise HTTPException(422, detail={"message": "ورودی قواعد باید فهرست باشد."})
    try:
        changed = save_rules(db, items)
    except ValueError as exc:
        raise HTTPException(422, detail={"message": str(exc)})

    titles = {
        r["form_key"]: r["short_title"] or r["title"]
        for r in serialize_rules(db)
    }
    log_activity(
        db,
        request,
        admin,
        "form_access_update",
        "قواعد لایهٔ دسترسی فرم‌ها: "
        + ("، ".join(titles.get(k, k) for k in changed) if changed else "بدون تغییر"),
    )
    return {
        "message": (
            "قواعد ذخیره شد — " + "، ".join(titles.get(k, k) for k in changed) + " به‌روزرسانی شد."
            if changed
            else "تغییری در قواعد نبود."
        ),
        "changed": changed,
        "rules": serialize_rules(db),
    }
