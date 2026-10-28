# -*- coding: utf-8 -*-
"""ثبت رویدادهای فعالیت (لاگ) — چه‌کسی، چه‌زمانی، چه‌کرد."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from ..models import ActivityLog, User

# برچسب فارسی رویدادها برای نمایش در پنل مدیر
ACTION_LABELS: dict[str, str] = {
    "login_success": "ورود موفق",
    "login_failed": "ورود ناموفق",
    "logout": "خروج",
    "password_changed": "تغییر رمز عبور",
    "password_changed_forced": "تغییر رمز اجباری (اولین ورود)",
    "password_reset": "بازنشانی رمز توسط مدیر",
    "survey_create": "ثبت فرم نظرسنجی",
    "survey_update": "ویرایش فرم نظرسنجی",
    "survey_delete": "حذف فرم نظرسنجی",
    "excel_export": "خروجی اکسل",
    "user_create": "ایجاد کاربر",
    "user_update": "ویرایش کاربر",
    "apikey_create": "ایجاد کلید وب‌سرویس",
    "apikey_revoke": "لغو کلید وب‌سرویس",
    "template_question_create": "افزودن سؤال",
    "template_question_update": "ویرایش سؤال",
    "template_contact_update": "ویرایش وضعیت تماس",
    "v1_survey_create": "ثبت فرم از وب‌سرویس",
    "system_bootstrap": "راه‌اندازی اولیه سامانه",
}


def log_activity(
    db: Session,
    request: Request | None,
    user: User | None,
    action: str,
    detail: str = "",
    username_override: str = "",
) -> None:
    """یک رویداد ثبت می‌کند — هرگز نباید جریان اصلی را بشکند."""
    try:
        ip = ""
        if request is not None and request.client:
            ip = request.client.host or ""
        entry = ActivityLog(
            user_id=user.id if user else None,
            username=username_override or (user.username if user else ""),
            action=action,
            detail=detail[:500],
            ip=ip,
        )
        db.add(entry)
        db.commit()
    except Exception:  # noqa: BLE001 — لاگ هرگز نباید عملیات اصلی را خراب کند
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
