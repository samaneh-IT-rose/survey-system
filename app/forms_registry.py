# -*- coding: utf-8 -*-
"""فهرست فرم‌های نظرسنجی سامانه — منوی «فرم‌های نظرسنجی» از همین فهرست ساخته می‌شود.

برای افزودن فرم جدید بعداً فقط کافی است یک مورد به SURVEY_FORMS اضافه شود
(و الگوی پیش‌فرضش در seed_data/defaults.py تعریف شود)؛ منوی ناوبری، صفحهٔ ثبت،
نمای چاپ، آرشیو و داشبورد به‌صورت خودکار آن را می‌شناسند.

هر فرم:
  key              — شناسهٔ یکتا (در ستون form_key رکوردها و form_keys الگوها)
  title            — عنوان رسمی کامل فرم (عین فایل نمونه) — در منو و سربرگ چاپ
  short_title      — برچسب کوتاه برای فیلترها و نمودارها
  url              — مسیر صفحهٔ ثبت (نسبت به پیشوند /app)
  sheet_template   — قالب نمای چاپ (عین فایل نمونهٔ همان فرم)
  subject_label    — عنوان بخش مشخصات (عین نمونهٔ همان فرم)
  phone_label      — برچسب فیلد شماره تماس (عین نمونه)
  service_date_label — برچسب تاریخ دریافت خدمت (عین نمونه)
  section4_title   — عنوان بخش ۴ فرم ثبت (عین نمونه)
  has_strengths    — آیا بخش «نقاط قوت و پیشنهاد بهبود» دارد؟ (فرم تلفنی: بله)
  overall_question — سؤال «رضایت کل» آن فرم برای تحلیل تلفیقی بین‌فرمی
  enabled          — اگر False شود، فرم از منو/ثبت/گزارش‌ها حذف می‌شود
"""
from __future__ import annotations

SURVEY_FORMS: list[dict] = [
    {
        "key": "tel",
        "title": "فرم رضایت‌سنجی مراجعین مشاوره تلفنی",
        "short_title": "مشاورهٔ تلفنی",
        "url": "/form/tel",
        "sheet_template": "sheet_tel.html",
        "subject_label": "مشخصات مصاحبه‌شونده",
        "phone_label": "شماره تماس",
        "service_date_label": "تاریخ دریافت خدمت (شمسی)",
        "section4_title": "نقاط قوت، پیشنهاد بهبود و نظارت حرفه‌ای",
        "has_strengths": True,
        "overall_question": "رضایت کلی از جلسه مشاوره",
        "enabled": True,
    },
    {
        "key": "individual",
        "title": "فرم ثبت نظرسنجی مراجعین خدمات مشاوره فردی",
        "short_title": "مشاورهٔ فردی",
        "url": "/form/individual",
        "sheet_template": "sheet.html",
        "subject_label": "مشخصات مراجع",
        "phone_label": "شماره تماس مراجع",
        "service_date_label": "تاریخ دریافت خدمت",
        "section4_title": "نظارت حرفه‌ای",
        "has_strengths": False,
        "overall_question": "به طور کلی رضایت شما از کیفیت کلی جلسه مشاوره چقدر بود؟",
        "enabled": True,
    },
    # فرم‌های بعدی (مثلاً مشاورهٔ گروهی) همین‌جا اضافه می‌شوند — منو و گزارش‌ها خودکار به‌روز می‌شوند.
]

FORM_KEYS: tuple[str, ...] = tuple(f["key"] for f in SURVEY_FORMS)

# فرم پیش‌فرض — مسیر /app/ به آن پرت می‌شود و رکوردهای بدون form_key به آن تعلق می‌گیرند
DEFAULT_FORM_KEY = "tel"


def enabled_forms() -> list[dict]:
    """فهرست فرم‌های فعال برای نمایش در منوی ناوبری و صفحه‌های گزارش."""
    return [dict(f) for f in SURVEY_FORMS if f.get("enabled")]


def all_forms() -> list[dict]:
    """همهٔ فرم‌های ثبت‌شده در ریجستری (حتی غیرفعال)."""
    return [dict(f) for f in SURVEY_FORMS]


def form_by_key(key: str | None) -> dict | None:
    """یافتن فرم با شناسهٔ یکتا؛ کلید نامعتبر → None."""
    if not key:
        return None
    return next((f for f in SURVEY_FORMS if f["key"] == key), None)


def form_title(key: str | None) -> str:
    """عنوان رسمی فرم؛ کلید ناشناخته → کلید خودش برمی‌گردد."""
    f = form_by_key(key)
    return f["title"] if f else (key or "")


def form_short_title(key: str | None) -> str:
    f = form_by_key(key)
    return f["short_title"] if f else (key or "")


def matches_form(form_keys_raw: str | None, key: str) -> bool:
    """آیا یک ردیف الگو (سؤال/وضعیت تماس) متعلق به فرم key است؟

    ستون form_keys به‌صورت «tel,individual» ذخیره می‌شود تا یک سؤال/وضعیت
    مشترک بتواند هم‌زمان به چند فرم تعلق داشته باشد.
    """
    if not form_keys_raw:
        return False
    return key in [k.strip() for k in str(form_keys_raw).split(",") if k.strip()]
