# -*- coding: utf-8 -*-
"""اعتبارسنجی سمت سرور داده‌های فرم نظرسنجی.

همه کنترل‌ها مطابق سند انجام می‌شود؛ اعتبارسنجی مرورگر فقط برای بازخورد
سریع است و به‌تنهایی کافی نیست (بخش ۵ سند).
"""
from __future__ import annotations

import datetime as dt
import re

from sqlalchemy import select

from ..constants import RATING_LABELS, RATING_LABEL_TO_SCORE
from ..database import SessionLocal
from ..models import ContactOption, County, Province, Question
from ..utils.jalali import gregorian_to_jalali, jalali_to_gregorian, parse_jalali_str
from ..utils.national_code import normalize_national_code

DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

PHONE_RE = re.compile(r"^09[0-9]{9}$")


def normalize_digits(value: str) -> str:
    return value.translate(DIGIT_MAP) if isinstance(value, str) else ""


def validate_survey_payload(db: SessionLocal, data: dict) -> tuple[dict, dict[str, str]]:
    """داده خام را بررسی و پاک‌سازی می‌کند؛ خروجی: (داده پاک، خطاها به تفکیک فیلد)."""
    errors: dict[str, str] = {}
    clean: dict = {}

    if not isinstance(data, dict):
        return clean, {"_": "داده ارسالی نامعتبر است."}

    # ── نام و نام خانوادگی ──
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    if not first_name:
        errors["first_name"] = "نام را وارد کنید."
    elif len(first_name) < 2 or len(first_name) > 60:
        errors["first_name"] = "نام باید بین ۲ تا ۶۰ نویسه باشد."
    if not last_name:
        errors["last_name"] = "نام خانوادگی را وارد کنید."
    elif len(last_name) < 2 or len(last_name) > 60:
        errors["last_name"] = "نام خانوادگی باید بین ۲ تا ۶۰ نویسه باشد."
    clean["first_name"], clean["last_name"] = first_name, last_name

    # ── کد ملی ──
    raw_code = data.get("national_code") or ""
    code = normalize_national_code(raw_code)
    if code is None:
        errors["national_code"] = (
            "کد ملی معتبر نیست؛ فقط ارقام مجاز است و رقم کنترلی باید درست باشد."
        )
    clean["national_code"] = code or ""

    # ── شماره تماس ──
    phone = normalize_digits(str(data.get("phone") or "")).strip()
    if not PHONE_RE.fullmatch(phone):
        errors["phone"] = "شماره تماس باید به شکل ۱۱ رقمی و با ۰۹ آغاز شود."
    clean["phone"] = phone

    # ── استان و شهرستان ──
    province_id = data.get("province_id")
    county_id = data.get("county_id")
    try:
        province_id = int(province_id)
    except (TypeError, ValueError):
        province_id = None
    try:
        county_id = int(county_id)
    except (TypeError, ValueError):
        county_id = None

    province = db.get(Province, province_id) if province_id else None
    if province is None:
        errors["province_id"] = "استان را انتخاب کنید."
    county = db.get(County, county_id) if county_id else None
    if county is None:
        errors["county_id"] = "شهرستان را انتخاب کنید."
    elif province is not None and county.province_id != province.id:
        # ارتباط استان و شهرستان در بک‌اند نیز کنترل می‌شود
        errors["county_id"] = "شهرستان انتخاب‌شده با استان همخوان نیست."
    clean["province_id"] = province_id
    clean["county_id"] = county_id

    # ── تاریخ شمسی ──
    parsed = parse_jalali_str(str(data.get("survey_date") or ""))
    if parsed is None:
        errors["survey_date"] = (
            "تاریخ نامعتبر است؛ قالب درست مانند ۱۴۰۵/۰۸/۰۵ و مطابق تقویم شمسی باشد."
        )
        clean["survey_date"] = None
    else:
        jy, jm, jd = parsed
        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        try:
            clean["survey_date"] = dt.date(gy, gm, gd)
            clean["survey_date_jalali"] = f"{jy:04d}/{jm:02d}/{jd:02d}"
        except ValueError:
            errors["survey_date"] = "تاریخ نامعتبر است."
            clean["survey_date"] = None

    # ── وضعیت تماس ──
    contact_id = data.get("contact_option_id")
    try:
        contact_id = int(contact_id)
    except (TypeError, ValueError):
        contact_id = None
    contact = db.get(ContactOption, contact_id) if contact_id else None
    if contact is None or not contact.is_active:
        errors["contact_option_id"] = "وضعیت تماس را انتخاب کنید."
    clean["contact_option_id"] = contact.id if contact else None
    clean["contact_requires_answers"] = bool(contact.requires_answers) if contact else True

    # ── پاسخ‌های جدول نظرسنجی ──
    active_questions = db.scalars(
        select(Question).where(Question.is_active.is_(True)).order_by(Question.display_order, Question.id)
    ).all()
    raw_answers = data.get("answers")
    if not isinstance(raw_answers, list):
        raw_answers = []

    by_qid: dict[int, dict] = {}
    answer_errors: dict[str, str] = {}
    for item in raw_answers:
        if not isinstance(item, dict):
            continue
        try:
            qid = int(item.get("question_id"))
        except (TypeError, ValueError):
            continue
        label = str(item.get("value") or "").strip()
        if qid not in {q.id for q in active_questions}:
            continue  # پرسش غیرفعال یا ناموجود نادیده گرفته می‌شود
        if label not in RATING_LABEL_TO_SCORE:
            answer_errors[f"answers.{qid}"] = "مقدار پاسخ باید یکی از گزینه‌های جدول باشد."
            continue
        by_qid[qid] = {"question_id": qid, "value": label}

    requires = clean["contact_requires_answers"]
    missing = [q.id for q in active_questions if q.id not in by_qid]
    if requires and missing:
        # پاسخ خالی بدون مجوز به «متوسط» یا گزینه دیگری تبدیل نمی‌شود؛ خطا گزارش می‌شود
        errors["answers"] = (
            "برای وضعیت تماس انتخاب‌شده، تکمیل همه سؤال‌های جدول الزامی است."
            if not answer_errors
            else errors.get("answers", "")
        )
    clean["answers"] = [by_qid[q.id] for q in active_questions if q.id in by_qid]
    clean["active_questions"] = active_questions

    errors.update(answer_errors)
    return clean, errors
