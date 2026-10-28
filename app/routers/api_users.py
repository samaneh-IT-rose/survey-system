# -*- coding: utf-8 -*-
"""مدیریت کاربران — فقط مدیر: ایجاد، ویرایش، فعال/غیرفعال، بازنشانی رمز."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import api_admin
from ..database import get_db
from ..models import User
from ..constants import ROLE_LABELS, ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER
from ..utils.activity import log_activity
from ..utils.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])

_VALID_ROLES = (ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER)
_VALID_USERNAME = re.compile(r"^[a-zA-Z0-9_.]{3,60}$")


def serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
        "role_label": ROLE_LABELS.get(u.role, u.role),
        "is_active": u.is_active,
        "must_change_password": u.must_change_password,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


def _count_active_admins(db: Session, exclude_id: int | None = None) -> int:
    stmt = select(User).where(User.role == ROLE_ADMIN, User.is_active.is_(True))
    rows = db.scalars(stmt).all()
    return sum(1 for u in rows if u.id != exclude_id)


@router.get("")
def list_users(admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.id)).all()
    return [serialize_user(u) for u in rows]


@router.post("")
def create_user(payload: dict, admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    username = str(payload.get("username") or "").strip().lower()
    full_name = str(payload.get("full_name") or "").strip()
    role = str(payload.get("role") or "").strip()
    password = str(payload.get("password") or "")

    if not _VALID_USERNAME.match(username):
        raise HTTPException(
            422,
            detail={"message": "نام کاربری باید ۳ تا ۶۰ نویسه و فقط حروف/رقم/نقطه/زیرخط لاتین باشد."},
        )
    if db.scalars(select(User).where(User.username == username)).first():
        raise HTTPException(422, detail={"message": "این نام کاربری قبلاً ثبت شده است."})
    if role not in _VALID_ROLES:
        raise HTTPException(422, detail={"message": "نقش معتبر نیست."})
    if len(password) < 6:
        raise HTTPException(422, detail={"message": "رمز عبور باید حداقل ۶ نویسه باشد."})

    user = User(
        username=username,
        full_name=full_name or username,
        role=role,
        password_hash=hash_password(password),
        must_change_password=bool(payload.get("must_change_password", True)),
    )
    db.add(user)
    db.commit()
    log_activity(db, None, admin, "user_create", f"ایجاد کاربر {username} با نقش {ROLE_LABELS[role]}")
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

    if "role" in payload:
        role = str(payload["role"]).strip()
        if role not in _VALID_ROLES:
            raise HTTPException(422, detail={"message": "نقش معتبر نیست."})
        if role != user.role:
            if user.id == admin.id:
                raise HTTPException(422, detail={"message": "نمی‌توانید نقش خودتان را تغییر دهید."})
            if user.role == ROLE_ADMIN and _count_active_admins(db, exclude_id=user.id) == 0:
                raise HTTPException(422, detail={"message": "حداقل یک مدیر فعال باید باقی بماند."})
            user.role = role
            changes.append(f"نقش → {ROLE_LABELS[role]}")

    if "is_active" in payload:
        active = bool(payload["is_active"])
        if active != user.is_active:
            if user.id == admin.id:
                raise HTTPException(422, detail={"message": "نمی‌توانید حساب خودتان را غیرفعال کنید."})
            if not active and user.role == ROLE_ADMIN and _count_active_admins(db, exclude_id=user.id) == 0:
                raise HTTPException(422, detail={"message": "حداقل یک مدیر فعال باید باقی بماند."})
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
