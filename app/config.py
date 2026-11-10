# -*- coding: utf-8 -*-
"""پیکربندی سامانه نظرسنجی — تنظیمات از متغیر محیطی خوانده می‌شود."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # survey-system/

APP_TITLE = "سامانه فرم نظرسنجی تلفنی"
# نسخهٔ برنامه — در فوتر صفحهٔ ورود و در healthz نمایش داده می‌شود تا
# بعد از هر به‌روزرسانی بتوان مطمئن شد نسخهٔ جدید واقعاً روی سرور است
APP_VERSION = "1.2.3"
ORG_NAME = os.environ.get("SURVEY_ORG_NAME", "راه زندگی")
LOGO_URL = os.environ.get("SURVEY_LOGO_URL", "/app/static/logo/logo.png")

# کد فرم — در سربرگ نسخهٔ چاپی کنار تاریخ نمایش داده می‌شود
# پیش‌فرض: کد فرم فایل نمونه (RS-PS-09-01). برای تغییر: در run-server.bat
# خط «set SURVEY_FORM_CODE=کد_مورد_نظر» را اضافه کنید
FORM_CODE = os.environ.get("SURVEY_FORM_CODE", "RS-PS-09-01")

# دیتابیس — به‌صورت پیش‌فرض PostgreSQL محلی
DATABASE_URL = os.environ.get(
    "SURVEY_DATABASE_URL",
    "postgresql+psycopg2://survey:survey@127.0.0.1:5432/surveydb",
)

# منطقه زمانی رسمی سامانه
TZ_NAME = "Asia/Tehran"

# مسیر پایهٔ همهٔ صفحات و APIها (برای سازگاری با پروکسی گیت‌وی)
APP_PREFIX = "/app"

# نشانی خودِ سرویس برای رندر PDF (نمای چاپ از همین سرور خوانده می‌شود)
SELF_BASE_URL = os.environ.get("SURVEY_SELF_URL", "http://127.0.0.1:3030")

# حداکثر اندازه فایل‌های ورودی (بایت) — برای سازگاری آینده
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
