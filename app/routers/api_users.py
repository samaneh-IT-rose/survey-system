# -*- coding: utf-8 -*-
"""مدیریت کاربران — فقط مدیر سامانه: ایجاد، ویرایش، فعال/غیرفعال، بازنشانی رمز،
تعیین سطح کاربری، نقش و سطوح دسترسی."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import api_admin
from ..constants import (
    LEVEL_ADMIN,
    LEVEL_LABELS,
    PERMISSIONS,
    ROLE_DEFAULT_PERMS,
    ROLE_DESCRIPTIONS,
    ROLE_LABELS,
    VALID_LEVELS,
    VALID_PERMISSIONS,
    VALID_ROLES,
)
from ..database import get_db
from ..models import User
from ..utils.activity import log_activity
from ..utils.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])

_VALID_USERNAME = re.compile(r"^[a-zA-Z0-9_.]{3,60}$")


def serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
        "role_label": ROLE_LABELS.get(u.role, u.role),
        "level": u.level,
        "level_label": LEVEL_LABELS.get(u.level, u.level),
        "is_admin_level": u.is_admin_level,
        "permissions": u.permission_keys,
        "effective_permissions": u.effective_permissions,
        "is_active": u.is_active,
        "must_change_password": u.must_change_password,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


@router.get("/meta")
def users_meta(admin: User = Depends(api_admin)):
    """گزینه‌های مجاز برای فرم مدیریت کاربران: سطوح، نقش‌ها و دسترسی‌ها."""
    return {
        "levels": [{"value": lv, "label": LEVEL_LABELS[lv]} for lv in VALID_LEVELS],
        "roles": [
            {
                "value": role,
                "label": ROLE_LABELS[role],
                "description": ROLE_DESCRIPTIONS[role],
                "default_permissions": list(ROLE_DEFAULT_PERMS[role]),
            }
            for role in VALID_ROLES
        ],
        "permissions": [{"value": key, "label": label} for key, label in PERMISSIONS],
    }


def _count_active_admins(db: Session, exclude_id: int | None = None) -> int:
    """تعداد کاربران فعال با سطح «مدیر سامانه» — برای حفاظت از آخرین مدیر."""
    stmt = select(User).where(User.is_active.is_(True))
    rows = db.scalars(stmt).all()
    return sum(1 for u in rows if u.is_admin_level and u.id != exclude_id)


def _clean_permissions(payload_permissions) -> list[str] | None:
    """اعتبارسنجی فهرست دسترسی‌های ارسالی — None یعنی در درخواست نیامده."""
    if payload_permissions is None:
        return None
    if not isinstance(payload_permissions, (list, tuple)):
        raise HTTPException(422, detail={"message": "سطوح دسترسی باید فهرست باشد."})
    keys: list[str] = []
    for p in payload_permissions:
        key = str(p).strip()
        if key not in VALID_PERMISSIONS:
            raise HTTPException(422, detail={"message": f"سطح دسترسی «{key}» معتبر نیست."})
        if key not in keys:
            keys.append(key)
    return keys


@router.get("")
def list_users(admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.id)).all()
    return [serialize_user(u) for u in rows]


@router.post("")
def create_user(payload: dict, admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    username = str(payload.get("username") or "").strip().lower()
    full_name = str(payload.get("full_name") or "").strip()
    role = str(payload.get("role") or "").strip()
    level = str(payload.get("level") or "user").strip()
    password = str(payload.get("password") or "")
    perms = _clean_permissions(payload.get("permissions"))

    if not _VALID_USERNAME.match(username):
        raise HTTPException(
            422,
            detail={"message": "نام کاربری باید ۳ تا ۶۰ نویسه و فقط حروف/رقم/نقطه/زیرخط لاتین باشد."},
        )
    if db.scalars(select(User).where(User.username == username)).first():
        raise HTTPException(422, detail={"message": "این نام کاربری قبلاً ثبت شده است."})
    if role not in VALID_ROLES:
        raise HTTPException(422, detail={"message": "نقش معتبر نیست."})
    if level not in VALID_LEVELS:
        raise HTTPException(422, detail={"message": "سطح کاربری معتبر نیست."})
    if len(password) < 6:
        raise HTTPException(422, detail={"message": "رمز عبور باید حداقل ۶ نویسه باشد."})

    user = User(
        username=username,
        full_name=full_name or username,
        role=role,
        level=level,
        permissions=",".join(perms) if perms is not None else "",
        password_hash=hash_password(password),
        must_change_password=bool(payload.get("must_change_password", True)),
    )
    db.add(user)
    db.commit()
    log_activity(
        db,
        None,
        admin,
        "user_create",
        f"ایجاد کاربر {username} — سطح {LEVEL_LABELS[level]}، نقش {ROLE_LABELS[role]}",
    )
    db.refresh(user)
    return {"message": f"کاربر «{user.username}» ساخته شد.", "record": serialize_user(user)}


@router.patch("/{user_id}")
def update_user(user_id: int, payload: dict, admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, detail={"message": "کاربر یافت نشد."})

    changes: list[str] = []

    if "full_name" in payload:
        user.full_name = str(payload["full_name"]).strip() or user.username
        changes.append("نام")

    if "level" in payload:
        level = str(payload["level"]).strip()
        if level not in VALID_LEVELS:
            raise HTTPException(422, detail={"message": "سطح کاربری معتبر نیست."})
        if level != user.level:
            if user.id == admin.id:
                raise HTTPException(422, detail={"message": "نمی‌توانید سطح دسترسی خودتان را تغییر دهید."})
            if user.is_admin_level and level != LEVEL_ADMIN and _count_active_admins(db, exclude_id=user.id) == 0:
                raise HTTPException(422, detail={"message": "حداقل یک مدیر سامانهٔ فعال باید باقی بماند."})
            user.level = level
            changes.append(f"سطح → {LEVEL_LABELS[level]}")

    if "role" in payload:
        role = str(payload["role"]).strip()
        if role not in VALID_ROLES:
            raise HTTPException(422, detail={"message": "نقش معتبر نیست."})
        if role != user.role:
            if user.id == admin.id:
                raise HTTPException(422, detail={"message": "نمی‌توانید نقش خودتان را تغییر دهید."})
            if user.is_admin_level and role != "admin" and _count_active_admins(db, exclude_id=user.id) == 0:
                raise HTTPException(422, detail={"message": "حداقل یک مدیر سامانهٔ فعال باید باقی بماند."})
            user.role = role
            changes.append(f"نقش → {ROLE_LABELS[role]}")

    if "permissions" in payload:
        perms = _clean_permissions(payload.get("permissions")) or []
        new_raw = ",".join(perms)
        if new_raw != (user.permissions or ""):
            user.permissions = new_raw
            names = "، ".join(
                label for key, label in PERMISSIONS if key in perms
            ) or "پیش‌فرض نقش"
            changes.append(f"سطوح دسترسی → {names}")

    if "is_active" in payload:
        active = bool(payload["is_active"])
        if active != user.is_active:
            if user.id == admin.id:
                raise HTTPException(422, detail={"message": "نمی‌توانید حساب خودتان را غیرفعال کنید."})
            if not active and user.is_admin_level and _count_active_admins(db, exclude_id=user.id) == 0:
                raise HTTPException(422, detail={"message": "حداقل یک مدیر سامانهٔ فعال باید باقی بماند."})
            user.is_active = active
            changes.append("فعال" if active else "غیرفعال")

    if "password" in payload:
        password = str(payload["password"] or "")
        if len(password) < 6:
            raise HTTPException(422, detail={"message": "رمز عبور باید حداقل ۶ نویسه باشد."})
        user.password_hash = hash_password(password)
        user.must_change_password = True
        changes.append("بازنشانی رمز")

    if not changes:
        raise HTTPException(422, detail={"message": "تغییری برای ذخیره ارسال نشده است."})

    db.commit()
    log_activity(db, None, admin, "user_update", f"کاربر {user.username}: {'، '.join(changes)}")
    db.refresh(user)
    return {"message": "تغییرات کاربر ذخیره شد.", "record": serialize_user(user)}
