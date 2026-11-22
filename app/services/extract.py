# -*- coding: utf-8 -*-
"""استخراج آزاد داده از «تمام فرم‌ها» (نسخهٔ 1.7.0).

کاربر فرم(های) موردنظر را انتخاب می‌کند، بعد هر ستونی که می‌خواهد:
- ستون‌های پایهٔ رکورد (نام، کد ملی، استان، تاریخ، وضعیت تماس، مشاور، ...)
- و هر سؤال از هر فرم به انتخاب خودش

همهٔ قیدهای دسترسی مثل بقیهٔ گزارش‌ها اعمال می‌شود:
- «فقط داده‌های خودش» (دسترسی own_data)
- «فرم‌های مجاز» کاربر (users.allowed_forms)
پس هیچ رکورد یا سؤالی خارج از محدودهٔ دسترسی فاش نمی‌شود.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import ORG_NAME
from ..forms_registry import enabled_forms, form_short_title
from ..models import Question, Survey
from ..utils.jalali import gdate_to_jalali_str, today_jalali_str

# ستون‌های پایهٔ هر رکورد — (کلید، برچسب)
BASE_FIELDS: list[tuple[str, str]] = [
    ("id", "شناسه"),
    ("form", "فرم"),
    ("first_name", "نام"),
    ("last_name", "نام خانوادگی"),
    ("national_code", "کد ملی"),
    ("phone", "شماره تماس"),
    ("province", "استان"),
    ("county", "شهرستان"),
    ("survey_date", "تاریخ نظرسنجی (شمسی)"),
    ("contact_option", "وضعیت تماس"),
    ("counselor", "مشاور"),
    ("service_type", "نوع خدمت"),
    ("service_date", "تاریخ دریافت خدمت"),
    ("created_at", "زمان ثبت"),
]

BASE_FIELD_KEYS = tuple(k for k, _ in BASE_FIELDS)
BASE_FIELD_LABELS = dict(BASE_FIELDS)

MAX_ROWS = 5000


def extract_schema(db: Session, user) -> dict:
    """ساختار انتخاب استخراج برای این کاربر: فرم‌های مجاز + سؤال‌های هر فرم."""
    from ..services.scope import allowed_form_keys

    forms = enabled_forms()
    keys = allowed_form_keys(user)
    if keys is not None:
        forms = [f for f in forms if f["key"] in keys]
    out_forms = []
    for f in forms:
        questions = db.scalars(
            select(Question)
            .where(Question.is_active.is_(True))
            .where(Question.form_keys.like(f"%{f['key']}%"))
            .order_by(Question.display_order, Question.id)
        ).all()
        out_forms.append(
            {
                "key": f["key"],
                "title": f["title"],
                "short_title": f["short_title"],
                "questions": [{"id": q.id, "text": q.text} for q in questions],
            }
        )
    return {
        "forms": out_forms,
        "base_fields": [{"key": k, "label": l} for k, l in BASE_FIELDS],
    }


def _resolve_columns(db: Session, field_tokens: list[str], selected_forms: list[str]) -> list[dict]:
    """تبدیل توکن‌های ستون («base:key» و «q:<id>») به تعریف ستون‌های خروجی.

    سؤال نامعتبر/غیرفعال نادیده گرفته می‌شود؛ سؤال بدون انتخاب ستون پایه هم
    فقط اگر به یکی از فرم‌های انتخابی تعلق داشته باشد می‌آید.
    """
    columns: list[dict] = []
    seen_q: set[int] = set()
    for token in field_tokens:
        token = str(token).strip()
        if not token:
            continue
        if token.startswith("base:"):
            key = token[5:]
            if key in BASE_FIELD_KEYS and all(c["key"] != key for c in columns):
                columns.append({"kind": "base", "key": key, "label": BASE_FIELD_LABELS[key]})
        elif token.startswith("q:"):
            try:
                qid = int(token[2:])
            except ValueError:
                continue
            if qid in seen_q:
                continue
            q = db.get(Question, qid)
            if q is None or not q.is_active:
                continue
            # سؤال باید به یکی از فرم‌های انتخابی تعلق داشته باشد
            q_keys = [k.strip() for k in (q.form_keys or "").split(",") if k.strip()]
            common = sorted(set(q_keys) & set(selected_forms)) if q_keys else []
            if selected_forms and not common:
                continue
            seen_q.add(qid)
            columns.append(
                {
                    "kind": "question",
                    "id": q.id,
                    "label": q.text,
                    "form_key": common[0] if common else "tel",
                }
            )
    return columns


def _default_columns(db: Session, selected_forms: list[str]) -> list[dict]:
    """وقتی ستونی انتخاب نشده: همهٔ ستون‌های پایه + همهٔ سؤال‌های فرم‌های انتخابی."""
    columns: list[dict] = [
        {"kind": "base", "key": k, "label": l} for k, l in BASE_FIELDS
    ]
    if selected_forms:
        q_rows = db.scalars(
            select(Question)
            .where(Question.is_active.is_(True))
            .order_by(Question.display_order, Question.id)
        ).all()
        for q in q_rows:
            q_keys = {k.strip() for k in (q.form_keys or "").split(",") if k.strip()}
            if q_keys & set(selected_forms):
                columns.append(
                    {
                        "kind": "question",
                        "id": q.id,
                        "label": q.text,
                        "form_key": sorted(q_keys & set(selected_forms))[0],
                    }
                )
    return columns


def _base_value(s: Survey, key: str) -> str:
    if key == "id":
        return str(s.id)
    if key == "form":
        return form_short_title(s.form_key)
    if key == "first_name":
        return s.first_name
    if key == "last_name":
        return s.last_name
    if key == "national_code":
        return s.national_code
    if key == "phone":
        return s.phone
    if key == "province":
        return s.province.name if s.province else ""
    if key == "county":
        return s.county.name if s.county else ""
    if key == "survey_date":
        return gdate_to_jalali_str(s.survey_date)
    if key == "contact_option":
        return s.contact_option.text if s.contact_option else ""
    if key == "counselor":
        return s.counselor or ""
    if key == "service_type":
        return s.service_type or ""
    if key == "service_date":
        return s.service_date or ""
    if key == "created_at":
        import zoneinfo

        from ..config import TZ_NAME

        if not s.created_at:
            return ""
        local = s.created_at.astimezone(zoneinfo.ZoneInfo(TZ_NAME))
        return gdate_to_jalali_str(local.date()) + " — " + local.strftime("%H:%M")
    return ""


def build_extract(
    db: Session,
    user,
    *,
    forms: list[str] | None = None,
    fields: list[str] | None = None,
    q: str | None = None,
    province_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """خروجی استخراج: ستون‌ها + ردیف‌ها — همهٔ رکوردها در محدودهٔ دسترسی کاربر."""
    from ..services.scope import allowed_form_keys, apply_record_scope

    enabled = {f["key"] for f in enabled_forms()}
    keys = allowed_form_keys(user)
    allowed = set(enabled) if keys is None else (set(keys) & enabled)
    requested = {str(f).strip() for f in (forms or []) if str(f).strip()}
    selected = sorted(allowed & requested) if requested else sorted(allowed)

    if fields:
        columns = _resolve_columns(db, [str(f) for f in fields], selected)
    else:
        columns = _default_columns(db, selected)
    if not columns:
        columns = [{"kind": "base", "key": k, "label": l} for k, l in BASE_FIELDS]

    stmt = select(Survey).order_by(Survey.survey_date.desc(), Survey.id.desc())
    if user is not None:
        stmt = apply_record_scope(stmt, user)
    if selected:
        stmt = stmt.where(Survey.form_key.in_(selected))
    if q and q.strip():
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Survey.first_name.ilike(needle),
                Survey.last_name.ilike(needle),
                Survey.national_code.ilike(needle),
                Survey.phone.ilike(needle),
            )
        )
    if province_id:
        stmt = stmt.where(Survey.province_id == province_id)

    from ..utils.jalali import jalali_to_gregorian, parse_jalali_str

    pf = parse_jalali_str(date_from or "")
    if pf:
        gy, gm, gd = jalali_to_gregorian(*pf)
        stmt = stmt.where(Survey.survey_date >= dt.date(gy, gm, gd))
    pt = parse_jalali_str(date_to or "")
    if pt:
        gy, gm, gd = jalali_to_gregorian(*pt)
        stmt = stmt.where(Survey.survey_date <= dt.date(gy, gm, gd))

    rows_out: list[list[str]] = []
    for s in db.scalars(stmt).all()[:MAX_ROWS]:
        answers_by_id = {a.question_id: a.value_label for a in s.answers}
        answers_by_text = {a.question_text.strip(): a.value_label for a in s.answers if a.question_text}
        row: list[str] = []
        for col in columns:
            if col["kind"] == "base":
                row.append(_base_value(s, col["key"]))
            else:
                val = answers_by_id.get(col["id"])
                if val is None:
                    val = answers_by_text.get(col["label"].strip(), "")
                row.append(val or "")
        rows_out.append(row)

    return {
        "columns": columns,
        "rows": rows_out,
        "total": len(rows_out),
        "forms": selected,
        "truncated": len(rows_out) >= MAX_ROWS,
    }


def build_extract_excel(db: Session, user, **kwargs) -> tuple[bytes, str]:
    """همان استخراج، به‌صورت فایل اکسل — برگه راست‌به‌چپ با قالب رسمی سامانه."""
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    from ..services.excel_export import BODY_FONT, BORDER, CENTER, HEADER_FILL, HEADER_FONT

    result = build_extract(db, user, **kwargs)
    columns = result["columns"]

    wb = Workbook()
    ws = wb.active
    ws.title = "استخراج داده"
    ws.sheet_view.rightToLeft = True

    headers = []
    for col in columns:
        if col["kind"] == "question":
            headers.append(f"[{form_short_title(col.get('form_key'))}] {col['label']}")
        else:
            headers.append(col["label"])

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(1, len(headers)))
    title_cell = ws.cell(row=1, column=1, value=f"{ORG_NAME} — استخراج داده از فرم‌های نظرسنجی ({today_jalali_str()})")
    title_cell.font = Font(name="Vazirmatn", size=12, bold=True, color="BA376D")
    title_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 26

    for c_i, h in enumerate(headers, start=1):
        c = ws.cell(row=2, column=c_i, value=h)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = CENTER
        c.border = BORDER
    ws.row_dimensions[2].height = 40

    for r_i, row in enumerate(result["rows"], start=3):
        for c_i, val in enumerate(row, start=1):
            c = ws.cell(row=r_i, column=c_i, value=val)
            c.font = BODY_FONT
            c.alignment = Alignment(horizontal="right", vertical="center", wrap_text=False)
            c.border = BORDER

    # عرض ستون‌ها — سرستون‌های سؤال بلندند؛ عرض متعادل با wrap
    for c_i, h in enumerate(headers, start=1):
        width = min(46, max(10, (len(str(h)) * 1.1)))
        ws.column_dimensions[get_column_letter(c_i)].width = width
    ws.freeze_panes = "A3"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue(), f"extract-{today_jalali_str().replace('/', '')}.xlsx"
