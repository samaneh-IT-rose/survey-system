# -*- coding: utf-8 -*-
"""API انتقادات و پیشنهادات — فهرست و خروجی اکسل (نسخهٔ 1.9.0).

هر رکوردی که بخش «انتقادات و پیشنهادات» آن پر شده باشد این‌جا گزارش می‌شود
(صفحهٔ اختصاصی «انتقادات و پیشنهادات»). همهٔ قیدهای دسترسی کاربر — «فقط
داده‌های خودش»، لایهٔ سازمانی، «فرم‌های مجاز» و محدودیت استانی — دقیقاً
مثل آرشیو اعمال می‌شود؛ هیچ رکوردی خارج از محدودهٔ دسترسی فاش نمی‌شود.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import api_require_perm
from ..constants import PERM_EXPORT, PERM_VIEW
from ..database import get_db
from ..forms_registry import form_short_title
from ..models import Survey, User
from ..services.scope import apply_record_scope
from ..utils.activity import log_activity
from ..utils.jalali import gdate_to_jalali_str, jalali_to_gregorian, parse_jalali_str

router = APIRouter(prefix="/api/criticisms", tags=["criticisms"])


def _apply_filters(stmt: select, args: dict):
    """فیلترهای صفحهٔ انتقادات — همان قرارداد آرشیو (تاریخ شمسی و…)."""
    if args.get("form"):
        stmt = stmt.where(Survey.form_key == args["form"])
    if args.get("province_id"):
        stmt = stmt.where(Survey.province_id == args["province_id"])
    if args.get("county_id"):
        stmt = stmt.where(Survey.county_id == args["county_id"])
    q = (args.get("q") or "").strip()
    if q:
        needle = f"%{q}%"
        stmt = stmt.where(
            or_(
                Survey.first_name.ilike(needle),
                Survey.last_name.ilike(needle),
                Survey.national_code.ilike(needle),
                Survey.phone.ilike(needle),
            )
        )
    pf = parse_jalali_str(args.get("date_from") or "")
    if pf:
        gy, gm, gd = jalali_to_gregorian(*pf)
        stmt = stmt.where(Survey.survey_date >= dt.date(gy, gm, gd))
    pt = parse_jalali_str(args.get("date_to") or "")
    if pt:
        gy, gm, gd = jalali_to_gregorian(*pt)
        stmt = stmt.where(Survey.survey_date <= dt.date(gy, gm, gd))
    return stmt


def _criticism_rows(db: Session, user: User, args: dict):
    """کوئری پایهٔ انتقادات — رکوردهای دارای متن + قیدهای دسترسی کاربر."""
    stmt = _apply_filters(
        apply_record_scope(select(Survey), user, db), args
    ).where(Survey.criticism.isnot(None)).where(Survey.criticism != "")
    return stmt.order_by(Survey.survey_date.desc(), Survey.id.desc())


def serialize_criticism(s: Survey) -> dict:
    local = s.created_at
    return {
        "id": s.id,
        "form_key": s.form_key or "tel",
        "form_title": form_short_title(s.form_key),
        "first_name": s.first_name,
        "last_name": s.last_name,
        "national_code": s.national_code,
        "phone": s.phone,
        "province": s.province.name if s.province else "",
        "county": s.county.name if s.county else "",
        "survey_date_jalali": gdate_to_jalali_str(s.survey_date),
        "criticism": getattr(s, "criticism", "") or "",
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
def list_criticisms(
    q: str | None = None,
    form: str | None = None,
    province_id: int | None = None,
    county_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(api_require_perm(PERM_VIEW)),
    db: Session = Depends(get_db),
):
    per_page = max(1, min(per_page, 100))
    page = max(1, page)
    args = dict(q=q, form=form, province_id=province_id, county_id=county_id,
                date_from=date_from, date_to=date_to)
    stmt = _criticism_rows(db, user, args)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.offset((page - 1) * per_page).limit(per_page)).all()
    return {
        "items": [serialize_criticism(r) for r in rows],
        "total": total,
        "page": page,
        "pages": max(1, -(-total // per_page)),
        "per_page": per_page,
    }


@router.get("/export/excel")
def export_criticisms_excel(
    request: Request,
    q: str | None = None,
    form: str | None = None,
    province_id: int | None = None,
    county_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: User = Depends(api_require_perm(PERM_EXPORT)),
    db: Session = Depends(get_db),
):
    """خروجی اکسل انتقادات با همان فیلترها — دسترسی «خروجی اکسل»."""
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    from ..config import ORG_NAME
    from ..utils.jalali import today_jalali_str

    args = dict(q=q, form=form, province_id=province_id, county_id=county_id,
                date_from=date_from, date_to=date_to)
    rows = db.scalars(_criticism_rows(db, user, args)).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "انتقادات و پیشنهادات"
    ws.sheet_view.rightToLeft = True

    HEADER_FILL = PatternFill("solid", fgColor="BA376D")
    HEADER_FONT = Font(name="Vazirmatn", size=11, bold=True, color="FFFFFF")
    BODY_FONT = Font(name="Vazirmatn", size=10)
    THIN = Side(style="thin", color="D9A9BF")
    BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
    CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
    RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=True)

    headers = [
        "ردیف", "فرم", "نام", "نام خانوادگی", "کد ملی", "شماره تماس",
        "استان", "شهرستان", "تاریخ نظرسنجی (شمسی)", "انتقادات و پیشنهادات",
        "زمان ثبت (شمسی)",
    ]
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title_cell = ws.cell(row=1, column=1, value=f"{ORG_NAME} — گزارش انتقادات و پیشنهادات ({today_jalali_str()})")
    title_cell.font = Font(name="Vazirmatn", size=12, bold=True, color="BA376D")
    title_cell.alignment = CENTER
    ws.row_dimensions[1].height = 26
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=2, column=col, value=h)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = CENTER
        c.border = BORDER
    ws.row_dimensions[2].height = 30

    for i, s in enumerate(rows, start=1):
        local = s.created_at
        values = [
            i,
            form_short_title(s.form_key),
            s.first_name,
            s.last_name,
            s.national_code,
            s.phone,
            s.province.name if s.province else "",
            s.county.name if s.county else "",
            gdate_to_jalali_str(s.survey_date),
            getattr(s, "criticism", "") or "",
            gdate_to_jalali_str(local.date()) if local else "",
        ]
        for col, v in enumerate(values, start=1):
            c = ws.cell(row=i + 2, column=col, value=v)
            c.font = BODY_FONT
            c.border = BORDER
            c.alignment = CENTER if col in (1, 5, 9) else RIGHT

    widths = [6, 16, 14, 16, 14, 14, 12, 14, 16, 50, 16]
    for col, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.freeze_panes = "A3"

    bio = BytesIO()
    wb.save(bio)
    content = bio.getvalue()
    filename = f"criticisms-{today_jalali_str().replace('/', '-')}.xlsx"
    log_activity(db, request, user, "criticism_export", f"خروجی {filename} — {len(rows)} ردیف")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
