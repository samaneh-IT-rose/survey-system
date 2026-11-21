# -*- coding: utf-8 -*-
"""مدیریت نقش‌ها (نسخهٔ 1.6.0) — نقش‌های سیستمی + نقش‌های تعریف‌شدهٔ جدید.

- جدول roles در شروع برنامه با ۶ نقش سیستمی seed می‌شود (idempotent).
- نقش سفارشی: مدیر سامانه در صفحهٔ «مدیریت نقش‌ها» می‌سازد؛ کلید آن
  به‌صورت خودکار «role_<id>» تعیین می‌شود و در ستون role جدول users ذخیره
  می‌شود.
- حذف فقط برای نقش‌های سفارشیِ بدون کاربر مجاز است.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import (
    LEVEL_ADMIN,
    LEVEL_USER,
    ROLE_ADMIN,
    ROLE_DATA_ENTRY,
    ROLE_OPERATOR,
    ROLE_REPORTER,
    ROLE_SUPERVISOR,
    ROLE_VIEWER,
    VALID_LEVELS,
    VALID_PERMISSIONS,
    parse_permissions,
)
from ..models import Role, User

# نقش‌های سیستمی — همان شش نقش همیشگی سامانه
SYSTEM_ROLES: list[dict] = [
    {"key": ROLE_ADMIN,       "name": "مدیر",             "description": "همهٔ دسترسی‌ها + مدیریت کاربران و الگو", "level": LEVEL_ADMIN, "permissions": "view,edit,print,export,delete", "display_order": 10},
    {"key": ROLE_OPERATOR,    "name": "کارشناس نظرسنجی",  "description": "ثبت و ویرایش فرم، چاپ و خروجی اکسل",     "level": LEVEL_USER,  "permissions": "view,edit,print,export",        "display_order": 20},
    {"key": ROLE_DATA_ENTRY,  "name": "ورود داده",        "description": "ثبت و ویرایش فرم و چاپ",                 "level": LEVEL_USER,  "permissions": "view,edit,print",               "display_order": 30},
    {"key": ROLE_SUPERVISOR,  "name": "ناظر حرفه‌ای",      "description": "ثبت و ویرایش فرم و چاپ (نظارت حرفه‌ای)", "level": LEVEL_USER,  "permissions": "view,edit,print",               "display_order": 40},
    {"key": ROLE_REPORTER,    "name": "گزارش‌گیر",         "description": "مشاهده، چاپ و خروجی اکسل (ثبت ندارد)",   "level": LEVEL_USER,  "permissions": "view,print,export",             "display_order": 50},
    {"key": ROLE_VIEWER,      "name": "مشاهده‌گر",         "description": "فقط مشاهدهٔ داشبورد و آرشیو",             "level": LEVEL_USER,  "permissions": "view",                          "display_order": 60},
]


def ensure_roles(db: Session) -> None:
    """درج نقش‌های سیستمی در استارت برنامه — فقط اگر وجود نداشته باشند."""
    for spec in SYSTEM_ROLES:
        exists = db.scalars(select(Role).where(Role.key == spec["key"])).first()
        if exists is None:
            db.add(Role(
                key=spec["key"],
                name=spec["name"],
                description=spec["description"],
                level=spec["level"],
                permissions=spec["permissions"],
                is_system=True,
                display_order=spec["display_order"],
            ))
    db.commit()


def serialize_role(db: Session, r: Role) -> dict:
    users_count = db.scalar(select(func.count()).select_from(User).where(User.role == r.key)) or 0
    return {
        "id": r.id,
        "key": r.key,
        "name": r.name,
        "description": r.description or "",
        "level": r.level,
        "permissions": parse_permissions(r.permissions),
        "permissions_raw": r.permissions or "",
        "is_system": bool(r.is_system),
        "users_count": users_count,
        "display_order": r.display_order,
    }


def list_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.display_order, Role.id)).all())


def role_row(db: Session, key: str) -> Role | None:
    if not key:
        return None
    return db.scalars(select(Role).where(Role.key == key)).first()


def valid_role_keys(db: Session) -> set[str]:
    """کلیدهای نقش معتبر — هر چه در جدول roles هست (سیستمی + سفارشی)."""
    return {r.key for r in list_roles(db)}


def role_default_perms(db: Session, key: str) -> list[str] | None:
    """دسترسی‌های پیش‌فرض نقش از جدول roles؛ ناشناخته → None (مکانیزم قدیمی)."""
    r = role_row(db, key)
    if r is None:
        return None
    perms = parse_permissions(r.permissions)
    return perms or None


def attach_role(user: User, db: Session) -> User:
    """ردیف نقش کاربر را به شیء کاربر می‌چسباند تا برچسب/دسترسی نقش دیده شود."""
    user._role_row = role_row(db, user.role)
    return user


def clean_role_permissions(payload_permissions) -> list[str]:
    """اعتبارسنجی فهرست دسترسی‌های نقش."""
    if payload_permissions is None:
        return []
    if not isinstance(payload_permissions, (list, tuple)):
        from fastapi import HTTPException

        raise HTTPException(422, detail={"message": "سطوح دسترسی باید فهرست باشد."})
    keys: list[str] = []
    for p in payload_permissions:
        k = str(p).strip()
        if k not in VALID_PERMISSIONS:
            from fastapi import HTTPException

            raise HTTPException(422, detail={"message": f"سطح دسترسی «{k}» معتبر نیست."})
        if k not in keys:
            keys.append(k)
    return keys
