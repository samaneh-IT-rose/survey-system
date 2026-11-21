# -*- coding: utf-8 -*-
"""خروجی اکسل رکوردهای نظرسنجی با openpyxl — برگه راست‌به‌چپ و ستون‌های پویا."""
from __future__ import annotations

import io
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ORG_NAME
from ..constants import RATING_LABELS
from ..forms_registry import enabled_forms, form_short_title
from ..models import ContactOption, Question, Survey
from ..services.form_template import questions_for_form
from ..utils.jalali import gdate_to_jalali_str, today_jalali_str

HEADER_FILL = PatternFill("solid", fgColor="BA376D")
HEADER_FONT = Font(name="Vazirmatn", size=11, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Vazirmatn", size=10)
THIN = Side(style="thin", color="D9A9BF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=True)


def _qid_of(form_questions: dict[str, list[Question]], form_key: str, q_text: str) -> int | None:
    """شناسهٔ سؤال از بلوک سؤال‌های همان فرم — بر اساس متن."""
    for q in form_questions.get(form_key, []):
        if q.text.strip() == q_text.strip():
            return q.id
    return None


def _fetch_filtered(db: Session, filters: dict, user=None) -> list[Survey]:
    from sqlalchemy import or_

    from ..services.scope import apply_record_scope

    stmt = select(Survey).order_by(Survey.survey_date.desc(), Survey.id.desc())
    # قیدهای دسترسی کاربر (فقط داده‌های خودش + فرم‌های مجاز)
    if user is not None:
        stmt = apply_record_scope(stmt, user)
    if filters.get("form"):
        stmt = stmt.where(Survey.form_key == filters["form"])
    if filters.get("counselor"):
        stmt = stmt.where(Survey.counselor == filters["counselor"].strip())
    if filters.get("service_type"):
        stmt = stmt.where(Survey.service_type == filters["service_type"].strip())
    q = filters.get("q")
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Survey.first_name.ilike(needle),
                Survey.last_name.ilike(needle),
                Survey.national_code.ilike(needle),
                Survey.phone.ilike(needle),
            )
        )
    if filters.get("province_id"):
        stmt = stmt.where(Survey.province_id == filters["province_id"])
    if filters.get("county_id"):
        stmt = stmt.where(Survey.county_id == filters["county_id"])
    if filters.get("contact_option_id"):
        stmt = stmt.where(Survey.contact_option_id == filters["contact_option_id"])
    from ..utils.jalali import jalali_to_gregorian, parse_jalali_str
    import datetime as dt

    pf = parse_jalali_str(filters.get("date_from") or "")
    if pf:
        gy, gm, gd = jalali_to_gregorian(*pf)
        stmt = stmt.where(Survey.survey_date >= dt.date(gy, gm, gd))
    pt = parse_jalali_str(filters.get("date_to") or "")
    if pt:
        gy, gm, gd = jalali_to_gregorian(*pt)
        stmt = stmt.where(Survey.survey_date <= dt.date(gy, gm, gd))
    return list(db.scalars(stmt))


def build_excel(db: Session, filters: dict, user=None) -> tuple[bytes, str]:
    """ستون‌های سؤال به تفکیک فرم: هر فرم فعال بلوک سؤال‌های خودش را دارد و
    هر رکورد فقط در بلوک فرمِ خودش مقدار می‌گیرد (بقیه خالی می‌ماند).

    با قیدهای دسترسی کاربر هم محدود می‌شود (نسخهٔ 1.6.0).
    """
    forms = enabled_forms()
    # بلوک سؤال‌ها فقط برای فرم‌هایی که کاربر حق دیدنشان را دارد
    if user is not None:
        from ..services.scope import allowed_form_keys

        keys = allowed_form_keys(user)
        if keys is not None:
            forms = [f for f in forms if f["key"] in keys]
    if filters.get("form"):
        forms = [f for f in forms if f["key"] == filters["form"]]
    form_questions: dict[str, list[Question]] = {
        f["key"]: questions_for_form(db, f["key"]) for f in forms
    }
    rows = _fetch_filtered(db, filters, user=user)

    wb = Workbook()
    ws = wb.active
    ws.title = "نظرسنجی"
    ws.sheet_view.rightToLeft = True

    headers = [
        "ردیف", "فرم", "نام", "نام خانوادگی", "کد ملی", "شماره تماس مراجع",
        "استان", "شهرستان", "تاریخ نظرسنجی (شمسی)", "وضعیت تماس",
        "مشاور", "نوع خدمت", "تاریخ دریافت خدمت (شمسی)",
        "نقاط قوت مشاوره تلفنی", "پیشنهاد بهبود", "کارشناس نظارت حرفه‌ای",
    ]
    # بلوک سؤال‌های هر فرم — سرستون با برچسب کوتاه فرم شروع می‌شود
    question_columns: list[tuple[str, str]] = []  # (form_key, متن سؤال)
    for f in forms:
        for q in form_questions[f["key"]]:
            headers.append(f"{form_short_title(f['key'])} — سؤال {len(question_columns) + 1}: {q.text}")
            question_columns.append((f["key"], q.text))
    headers += ["زمان ثبت (شمسی)"]

    # سطر عنوان گزارش
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title_cell = ws.cell(row=1, column=1, value=f"{ORG_NAME} — خروجی فرم‌های نظرسنجی ({today_jalali_str()})")
    title_cell.font = Font(name="Vazirmatn", size=12, bold=True, color="BA376D")
    title_cell.alignment = CENTER
    ws.row_dimensions[1].height = 26

    # سطر سرستون
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=2, column=col, value=h)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = CENTER
        c.border = BORDER
    ws.row_dimensions[2].height = 34

    # داده‌ها
    for i, s in enumerate(rows, start=1):
        # تطبیق پاسخ‌ها: اول با شناسهٔ سؤال، و اگر رکورد قدیمی الگو عوض شده بود
        # با متن سؤالِ ذخیره‌شده (snapshot) — همان منطق نمای چاپ
        answers_by_id = {a.question_id: a.value_label for a in s.answers}
        answers_by_text = {a.question_text.strip(): a.value_label for a in s.answers if a.question_text}
        contact_text = s.contact_option.text if s.contact_option else "—"
        strengths = " ".join(x for x in [s.strengths or "", s.strengths_extra or ""] if x)
        improvement = " ".join(x for x in [s.improvement or "", s.improvement_extra or ""] if x)
        values = [
            i, form_short_title(s.form_key), s.first_name, s.last_name, s.national_code, s.phone,
            s.province.name, s.county.name, gdate_to_jalali_str(s.survey_date), contact_text,
            s.counselor or "", s.service_type or "", s.service_date or "",
            strengths, improvement, s.supervisor_name or "",
        ]
        # هر رکورد فقط در بلوک سؤال‌های فرم خودش مقدار می‌گیرد
        rec_form = s.form_key or ""
        for fq_key, q_text in question_columns:
            if fq_key != rec_form:
                values.append("")
            else:
                values.append(answers_by_id.get(_qid_of(form_questions, fq_key, q_text)) or answers_by_text.get(q_text, ""))
        values += [
            gdate_to_jalali_str(s.created_at.date()) if s.created_at else "",
        ]
        for col, v in enumerate(values, start=1):
            c = ws.cell(row=i + 2, column=col, value=v)
            c.font = BODY_FONT
            c.border = BORDER
            c.alignment = CENTER if col in (1, 4, 5, 8) else RIGHT

    # عرض ستون‌ها
    base_widths = [6, 16, 14, 16, 14, 14, 12, 14, 16, 24, 14, 14, 16, 30, 30, 18]
    for col, w in enumerate(base_widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = w
    for i in range(len(question_columns)):
        ws.column_dimensions[get_column_letter(len(base_widths) + i + 1)].width = 16
    ws.column_dimensions[get_column_letter(len(headers))].width = 16
    ws.freeze_panes = "D3"

    bio = io.BytesIO()
    wb.save(bio)
    filename = f"survey-export-{today_jalali_str().replace('/', '-')}.xlsx"
    return bio.getvalue(), filename
