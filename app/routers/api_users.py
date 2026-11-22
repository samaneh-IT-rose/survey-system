# -*- coding: utf-8 -*-
"""مدیریت کاربران — فقط مدیر سامانه: ایجاد، ویرایش، فعال/غیرفعال، بازنشانی رمز،
تعیین سطح کاربری، نقش و سطوح دسترسی + ورود گروهی کاربران از فایل اکسل (نسخهٔ 1.7.0).

منطق ورود اکسل در app/services/users_import.py است — همان منطق را دستور
seed سرور (python -m app.seed_users) هم استفاده می‌کند تا رفتار یکسان باشد.
"""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import api_admin
from ..constants import (
    LEVEL_ADMIN,
    LEVEL_LABELS,
    PERMISSIONS,
    VALID_LEVELS,
    VALID_PERMISSIONS,
)
from ..database import get_db
from ..forms_registry import form_by_key
from ..models import User
from ..services.roles import role_default_perms, role_row, valid_role_keys
from ..services.users_import import (
    VALID_USERNAME_RE as _VALID_USERNAME,
    import_users_from_bytes,
    norm_digits as _norm_digits,
    norm_text as _norm_text,
    validate_forms_csv as _validate_forms_csv,
)
from ..utils.activity import log_activity
from ..utils.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _profile_from_payload(payload: dict, target: User | None = None) -> tuple[dict, list[str]]:
    """استخراج فیلدهای مشخصات سازمانی از payload — فقط کلیدهای ارسال‌شده.

    خروجی: (values، نام فیلدهای تغییرکرده) — برای ثبت در لاگ تغییرات.
    """
    values: dict[str, str] = {}
    labels: dict[str, str] = {
        "national_id": "کد ملی",
        "province_name": "استان",
        "phone": "شماره همراه",
        "position": "سمت",
        "notes": "توضیحات",
    }
    changed: list[str] = []
    for key, label in labels.items():
        if key not in payload:
            continue
        if key == "national_id":
            v = _norm_digits(payload.get(key), zfill=10)[:10]
        elif key == "phone":
            v = _norm_digits(payload.get(key), zfill=11)[:15]
        elif key == "notes":
            v = _norm_text(payload.get(key), 1000)
        else:
            v = _norm_text(payload.get(key), 80)
        values[key] = v
        if target is None or getattr(target, key) != v:
            changed.append(label)
    return values, changed


def serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
        "role_label": u.role_label,
        "level": u.level,
        "level_label": LEVEL_LABELS.get(u.level, u.level),
        "is_admin_level": u.is_admin_level,
        "permissions": u.permission_keys,
        "effective_permissions": u.effective_permissions,
        "allowed_forms": u.allowed_form_keys,
        "national_id": u.national_id,
        "province_name": u.province_name,
        "phone": u.phone,
        "position": u.position,
        "notes": u.notes,
        "is_active": u.is_active,
        "must_change_password": u.must_change_password,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


@router.get("/meta")
def users_meta(admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    """گزینه‌های مجاز برای فرم مدیریت کاربران: سطوح، نقش‌ها، دسترسی‌ها و فرم‌ها.

    نقش‌ها از جدول roles می‌آیند (سیستمی + سفارشی)؛ default_permissions هر نقش
    همان دسترسی‌هایی است که هنگام انتخاب نقش در فرم کاربر تیک می‌خورد.
    """
    from ..forms_registry import enabled_forms
    from ..services.roles import list_roles

    return {
        "levels": [{"value": lv, "label": LEVEL_LABELS[lv]} for lv in VALID_LEVELS],
        "roles": [
            {
                "value": r.key,
                "label": r.name,
                "description": r.description or "",
                "default_permissions": role_default_perms(db, r.key) or ["view"],
                "is_system": bool(r.is_system),
            }
            for r in list_roles(db)
        ],
        "permissions": [{"value": key, "label": label} for key, label in PERMISSIONS],
        "forms": enabled_forms(),
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


def _clean_allowed_forms(payload_forms) -> list[str] | None:
    """اعتبارسنجی «فرم‌های مجاز» ارسالی — None یعنی در درخواست نیامده."""
    if payload_forms is None:
        return None
    if not isinstance(payload_forms, (list, tuple)):
        raise HTTPException(422, detail={"message": "فرم‌های مجاز باید فهرست باشد."})
    keys: list[str] = []
    for f in payload_forms:
        key = str(f).strip()
        if form_by_key(key) is None:
            raise HTTPException(422, detail={"message": f"فرم «{key}» معتبر نیست."})
        if key not in keys:
            keys.append(key)
    return keys


@router.get("")
def list_users(admin: User = Depends(api_admin), db: Session = Depends(get_db)):
    from ..services.roles import attach_role

    rows = db.scalars(select(User).order_by(User.id)).all()
    return [serialize_user(attach_role(u, db)) for u in rows]


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
    if role not in valid_role_keys(db):
        raise HTTPException(422, detail={"message": "نقش معتبر نیست."})
    if level not in VALID_LEVELS:
        raise HTTPException(422, detail={"message": "سطح کاربری معتبر نیست."})
    if len(password) < 6:
        raise HTTPException(422, detail={"message": "رمز عبور باید حداقل ۶ نویسه باشد."})
    allowed_forms = _clean_allowed_forms(payload.get("allowed_forms"))
    profile, _ = _profile_from_payload(payload)

    user = User(
        username=username,
        full_name=full_name or username,
        role=role,
        level=level,
        permissions=",".join(perms) if perms is not None else "",
        allowed_forms=",".join(allowed_forms) if allowed_forms is not None else "",
        password_hash=hash_password(password),
        must_change_password=bool(payload.get("must_change_password", True)),
        national_id=profile.get("national_id", ""),
        province_name=profile.get("province_name", ""),
        phone=profile.get("phone", ""),
        position=profile.get("position", ""),
        notes=profile.get("notes", ""),
    )
    db.add(user)
    db.commit()
    role_label = role_row(db, role).name if role_row(db, role) else role
    log_activity(
        db,
        None,
        admin,
        "user_create",
        f"ایجاد کاربر {username} — سطح {LEVEL_LABELS[level]}، نقش {role_label}",
    )
    db.refresh(user)
    from ..services.roles import attach_role

    attach_role(user, db)
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

    profile, profile_changed = _profile_from_payload(payload, target=user)
    for key, val in profile.items():
        setattr(user, key, val)
    if profile_changed:
        changes.append("مشخصات (" + "، ".join(profile_changed) + ")")

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
        if role not in valid_role_keys(db):
            raise HTTPException(422, detail={"message": "نقش معتبر نیست."})
        if role != user.role:
            if user.id == admin.id:
                raise HTTPException(422, detail={"message": "نمی‌توانید نقش خودتان را تغییر دهید."})
            if user.is_admin_level and role != "admin" and _count_active_admins(db, exclude_id=user.id) == 0:
                raise HTTPException(422, detail={"message": "حداقل یک مدیر سامانهٔ فعال باید باقی بماند."})
            user.role = role
            _rr = role_row(db, role)
            changes.append(f"نقش → {_rr.name if _rr else role}")

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

    if "allowed_forms" in payload:
        forms = _clean_allowed_forms(payload.get("allowed_forms")) or []
        new_raw = ",".join(forms)
        if new_raw != (user.allowed_forms or ""):
            user.allowed_forms = new_raw
            if forms:
                titles = "، ".join(form_by_key(k)["short_title"] for k in forms if form_by_key(k))
                changes.append(f"فرم‌های مجاز → {titles}")
            else:
                changes.append("فرم‌های مجاز → همه")

    if not changes:
        raise HTTPException(422, detail={"message": "تغییری برای ذخیره ارسال نشده است."})

    db.commit()
    log_activity(db, None, admin, "user_update", f"کاربر {user.username}: {'، '.join(changes)}")
    db.refresh(user)
    from ..services.roles import attach_role

    attach_role(user, db)
    return {"message": "تغییرات کاربر ذخیره شد.", "record": serialize_user(user)}


# ---------- ورود گروهی کاربران از فایل اکسل (نسخهٔ 1.7.0) ----------
# منطق کامل در app/services/users_import.py — این endpoint فقط اعتبارسنجی
# ورودی‌های مدیر، خواندن فایل و ثبت لاگ را انجام می‌دهد.


@router.post("/import-excel")
async def import_users_excel(
    request: Request,
    file: UploadFile = File(...),
    level: str = Form("user"),
    role: str = Form("viewer"),
    password_mode: str = Form("national_id"),
    fixed_password: str = Form(""),
    allowed_forms: str = Form(""),
    admin: User = Depends(api_admin),
    db: Session = Depends(get_db),
):
    """ساخت گروهی کاربران از فایل اکسل — هر شیت یک گروه سازمانی (سمت = نام شیت)."""
    if level not in VALID_LEVELS:
        raise HTTPException(422, detail={"message": "سطح کاربری معتبر نیست."})
    if role not in valid_role_keys(db):
        raise HTTPException(422, detail={"message": "نقش معتبر نیست."})
    if password_mode == "fixed" and len(fixed_password.strip()) < 6:
        raise HTTPException(422, detail={"message": "رمز یکسان باید حداقل ۶ نویسه باشد."})
    try:
        forms_csv = _validate_forms_csv(allowed_forms)
    except ValueError as exc:
        raise HTTPException(422, detail={"message": str(exc)})

    data = await file.read()
    try:
        result = import_users_from_bytes(
            db,
            data,
            level=level,
            role=role,
            password_mode=password_mode,
            fixed_password=fixed_password,
            forms_csv=forms_csv,
        )
    except ValueError as exc:
        raise HTTPException(422, detail={"message": str(exc)})

    created = result["created"]
    skipped = result["skipped"]
    log_activity(
        db,
        request,
        admin,
        "users_import",
        f"ورود گروهی از اکسل: {len(created)} کاربر ساخته شد، {len(skipped)} ردیف رد شد",
    )
    return {
        "message": f"{len(created)} کاربر ساخته شد؛ {len(skipped)} ردیف رد شد.",
        "created": created,
        "skipped": skipped,
        "total_rows": result["total_rows"],
    }


@router.get("/import-template")
def import_template(admin: User = Depends(api_admin)):
    """دانلود قالب نمونهٔ اکسل — همان ساختار فایل رسمی (دو شیت نمونه)."""
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    headers = ["استان", "نام و نام خانوادگی", "کد ملی", "شماره همراه", "توضیحات"]
    sample = ["تهران", "نام نمونه", "0012345678", "09121234567", "*"]
    for title in ("مسئولین اجرایی", "مدیران کلینیک"):
        ws = wb.create_sheet(title)
        ws.append(headers)
        ws.append(sample)
        ws.sheet_view.rightToLeft = True
    buf = io.BytesIO()
    wb.save(buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="users-import-template.xlsx"'},
    )
