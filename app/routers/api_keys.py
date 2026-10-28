# -*- coding: utf-8 -*-
"""مدیریت کلیدهای وب‌سرویس — فقط مدیر.

کلید کامل فقط هنگام ساخت یک‌بار نمایش داده می‌شود؛ در دیتابیس فقط هش آن
ذخیره می‌شود (مثل رمز عبور).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import api_admin
from ..database import get_db
from ..models import ApiKey, User
from ..utils.activity import log_activity
from ..utils.security import generate_api_key

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


def serialize_key(k: ApiKey) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "key_prefix": k.key_prefix,
        "is_active": k.is_active,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
    }


@router.get("")
def list_keys(admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(ApiKey).order_by(ApiKey.id)).all()
    return [serialize_key(k) for k in rows]


@router.post("")
def create_key(payload: dict, admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    name = str(payload.get("name") or "").strip()
    if not (2 <= len(name) <= 120):
        raise HTTPException(422, detail={"message": "نام سیستم متصل باید بین ۲ تا ۱۲۰ نویسه باشد."})

    key, key_hash, key_prefix = generate_api_key()
    item = ApiKey(name=name, key_hash=key_hash, key_prefix=key_prefix)
    db.add(item)
    db.commit()
    log_activity(db, None, admin, "apikey_create", f"کلید جدید برای «{name}»")
    db.refresh(item)
    return {
        "message": "کلید ساخته شد. این کلید فقط همین یک‌بار نمایش داده می‌شود — همین حالا کپی کن!",
        "key": key,
        "record": serialize_key(item),
    }


@router.patch("/{key_id}")
def update_key(key_id: int, payload: dict, admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    item = db.get(ApiKey, key_id)
    if item is None:
        raise HTTPException(404, detail={"message": "کلید یافت نشد."})
    if "is_active" not in payload:
        raise HTTPException(422, detail={"message": "پارامتری برای تغییر ارسال نشده است."})
    item.is_active = bool(payload["is_active"])
    db.commit()
    log_activity(
        db,
        None,
        admin,
        "apikey_revoke" if not item.is_active else "apikey_create",
        f"کلید «{item.name}» {'غیرفعال' if not item.is_active else 'فعال'} شد",
    )
    db.refresh(item)
    return {"message": "وضعیت کلید به‌روزرسانی شد.", "record": serialize_key(item)}
