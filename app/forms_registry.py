# -*- coding: utf-8 -*-
"""فهرست فرم‌های نظرسنجی سامانه — منوی «فرم‌های نظرسنجی» از همین فهرست ساخته می‌شود.

برای افزودن فرم جدید بعداً فقط کافی است یک مورد به SURVEY_FORMS اضافه شود
(و مسیر صفحهٔ ثبت آن فرم در routers تعریف شود)؛ منوی ناوبری به‌صورت خودکار
همهٔ فرم‌های enabled را نشان می‌دهد و ترتیب نمایش همان ترتیب این فهرست است.

هر فرم:
  key      — شناسهٔ یکتا (برای data-nav و در آینده برای تفکیک رکوردها)
  title    — برچسب نمایشی در منو
  url      — مسیر صفحهٔ ثبت فرم (نسبت به پیشوند /app)
  enabled  — اگر False شود، فرم از منو حذف می‌شود (بدون حذف کد)
"""
from __future__ import annotations

SURVEY_FORMS: list[dict] = [
    {
        "key": "individual",
        "title": "نظرسنجی خدمات مشاورهٔ فردی",
        "url": "/",
        "enabled": True,
    },
    # فرم‌های بعدی همین‌جا اضافه می‌شوند — منو خودکار به‌روز می‌شود.
]


def enabled_forms() -> list[dict]:
    """فهرست فرم‌های فعال برای نمایش در منوی ناوبری."""
    return [dict(f) for f in SURVEY_FORMS if f.get("enabled")]


def form_by_key(key: str) -> dict | None:
    """یافتن فرم با شناسهٔ یکتا — برای مسیرهای چند-فرمی در آینده."""
    return next((f for f in SURVEY_FORMS if f["key"] == key), None)
