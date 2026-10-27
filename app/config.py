# -*- coding: utf-8 -*-
"""پیکربندی سامانه نظرسنجی — تنظیمات از متغیر محیطی خوانده می‌شود."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # survey-system/

APP_TITLE = "سامانه فرم نظرسنجی تلفنی"
ORG_NAME = os.environ.get("SURVEY_ORG_NAME", "نام سازمان")
LOGO_URL = os.environ.get("SURVEY_LOGO_URL", "/app/static/logo/logo.svg")

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
