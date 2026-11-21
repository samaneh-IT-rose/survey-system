# -*- coding: utf-8 -*-
"""API مدیریت نقش‌ها — فقط مدیر سامانه (نسخهٔ 1.6.0).

- GET    /api/roles            فهرست نقش‌ها با تعداد کاربران
- POST   /api/roles            ثبت نقش جدید (کلید خودکار role_<id>)
- PATCH  /api/roles/{id}       ویرایش نام/توضیح/سطح/دسترسی‌های پیش‌فرض
- DELETE /api/roles/{id}       حذف نقش سفارشیِ بدون کاربر
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import api_admin
from ..constants import VALID_LEVELS
from ..database import get_db
from ..models import Role, User
from ..services.roles import (
    clean_role_permissions,
    serialize_role,
)
from ..utils.activity import log_activity

router = APIRouter(prefix="/api/roles", tags=["roles"], dependencies=[Depends(api_admin)])


@router.get("")
def list_all(db: Session = Depends(get_db), admin: User = Depends(api_admin)):
    from ..services.roles import list_roles

    rows = list_roles(db)
    return [serialize_role(db, r) for r in rows]


@router.post("")
def create_role(payload: dict, admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    level = str(payload.get("level") or "user").strip()
    perms = clean_role_permissions(payload.get("permissions"))

    if not (2 <= len(name) <= 80):
        raise HTTPException(422, detail={"message": "نام نقش باید بین ۲ تا ۸۰ نویسه باشد."})
    if level not in VALID_LEVELS:
        raise HTTPException(422, detail={"message": "سطح کاربری نقش معتبر نیست."})
    if db.scalars(select(Role).where(Role.name == name)).first():
        raise HTTPException(422, detail={"message": "نقشی با این نام از قبل ثبت شده است."})

    role = Role(
        key="pending",
        name=name,
        description=description,
        level=level,
        permissions=",".join(perms),
        is_system=False,
        display_order=200,
    )
    db.add(role)
    db.flush()
    # کلید خودکار بر اساس شناسه — کوتاه، یکتا و امن برای ستون String(40) جدول users
    role.key = f"role_{role.id}"
    db.commit()
    log_activity(db, None, admin, "role_create", f"نقش جدید «{name}» (سطح {level})")
    db.refresh(role)
    return {"message": f"نقش «{role.name}» ساخته شد.", "record": serialize_role(db, role)}


def _get_role(db: Session, role_id: int) -> Role:
    r = db.get(Role, role_id)
    if r is None:
        raise HTTPException(404, detail={"message": "نقش یافت نشد."})
    return r


@router.patch("/{role_id}")
def update_role(role_id: int, payload: dict, admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    role = _get_role(db, role_id)
    changes: list[str] = []

    if "name" in payload:
        name = str(payload["name"]).strip()
        if not (2 <= len(name) <= 80):
            raise HTTPException(422, detail={"message": "نام نقش باید بین ۲ تا ۸۰ نویسه باشد."})
        other = db.scalars(select(Role).where(Role.name == name, Role.id != role.id)).first()
        if other:
            raise HTTPException(422, detail={"message": "نقشی با این نام از قبل ثبت شده است."})
        if name != role.name:
            role.name = name
            changes.append("نام")

    if "description" in payload:
        d = str(payload["description"]).strip()
        if d != (role.description or ""):
            role.description = d
            changes.append("توضیح")

    if "level" in payload:
        lv = str(payload["level"]).strip()
        if lv not in VALID_LEVELS:
            raise HTTPException(422, detail={"message": "سطح کاربری نقش معتبر نیست."})
        if lv != role.level:
            if role.is_system:
                raise HTTPException(422, detail={"message": "سطح نقش‌های سیستمی قابل تغییر نیست."})
            role.level = lv
            changes.append("سطح")

    if "permissions" in payload:
        perms = clean_role_permissions(payload.get("permissions"))
        new_raw = ",".join(perms)
        if new_raw != (role.permissions or ""):
            role.permissions = new_raw
            changes.append("دسترسی‌های پیش‌فرض")

    if not changes:
        raise HTTPException(422, detail={"message": "تغییری برای ذخیره ارسال نشده است."})

    db.commit()
    log_activity(db, None, admin, "role_update", f"نقش «{role.name}»: {'، '.join(changes)}")
    db.refresh(role)
    return {"message": "نقش ذخیره شد.", "record": serialize_role(db, role)}


@router.delete("/{role_id}")
def delete_role(role_id: int, admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    role = _get_role(db, role_id)
    if role.is_system:
        raise HTTPException(422, detail={"message": "نقش‌های سیستمی حذف نمی‌شوند."})
    users_count = db.scalar(
        select(User.id).where(User.role == role.key).limit(1)
    )
    if users_count is not None:
        raise HTTPException(422, detail={"message": "این نقش به کاربرانی تخصیص یافته؛ اول نقش آن‌ها را عوض کنید."})
    detail = f"نقش «{role.name}» ({role.key}) حذف شد"
    db.delete(role)
    db.commit()
    log_activity(db, None, admin, "role_delete", detail)
    return {"message": "نقش حذف شد.", "id": role_id}
