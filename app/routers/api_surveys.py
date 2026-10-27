# -*- coding: utf-8 -*-
"""API رکوردهای نظرسنجی — ثبت، مشاهده، ویرایش، حذف و فهرست با فیلتر."""
from __future__ import annotations

import datetime as dt
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..constants import RATING_LABEL_TO_SCORE
from ..database import get_db
from ..models import Survey, SurveyAnswer
from ..services.validation import validate_survey_payload
from ..utils.jalali import gdate_to_jalali_str, jalali_to_gregorian, parse_jalali_str

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


def _fa_datetime(dtval):
    """زمان ثبت به شمسی: ۱۴۰۵/۰۸/۰۵ — ۱۳:۲۵"""
    if not dtval:
        return "—"
    import zoneinfo
    from ..config import TZ_NAME
    from ..utils.jalali import gdate_to_jalali_str
    local = dtval.astimezone(zoneinfo.ZoneInfo(TZ_NAME))
    return gdate_to_jalali_str(local.date()) + " — " + local.strftime("%H:%M")


def serialize_survey(s: Survey) -> dict:
    co = s.contact_option
    return {
        "id": s.id,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "national_code": s.national_code,
        "phone": s.phone,
        "province": {"id": s.province_id, "name": s.province.name},
        "county": {"id": s.county_id, "name": s.county.name},
        "survey_date": s.survey_date.isoformat(),
        "survey_date_jalali": gdate_to_jalali_str(s.survey_date),
        "contact_option": (
            {"id": co.id, "text": co.text, "requires_answers": co.requires_answers}
            if co
            else None
        ),
        "answers": [
            {
                "question_id": a.question_id,
                "question_text": a.question_text,
                "value": a.value_label,
                "value_score": a.value_score,
            }
            for a in s.answers
        ],
        "created_at": s.created_at.astimezone(timezone.utc).isoformat()
        if s.created_at
        else None,
        "updated_at": s.updated_at.astimezone(timezone.utc).isoformat()
        if s.updated_at
        else None,
        "created_at_fa": _fa_datetime(s.created_at),
        "updated_at_fa": _fa_datetime(s.updated_at),
    }


def _save_answers(db: Session, survey: Survey, clean: dict) -> None:
    # حذف صریح پاسخ‌های قبلی و flush پیش از درج — برای جلوگیری از تداخل
    # قید یکتای (survey_id, question_id) در ترتیب اجرای درج/حذف SQLAlchemy
    from sqlalchemy import delete as sa_delete

    db.execute(sa_delete(SurveyAnswer).where(SurveyAnswer.survey_id == survey.id))
    db.flush()
    for item in clean["answers"]:
        question_text = next(
            (q.text for q in clean["active_questions"] if q.id == item["question_id"]),
            "",
        )
        db.add(
            SurveyAnswer(
                survey_id=survey.id,
                question_id=item["question_id"],
                question_text=question_text,
                value_label=item["value"],
                value_score=RATING_LABEL_TO_SCORE[item["value"]],
            )
        )


@router.post("")
def create_survey(payload: dict, db: Session = Depends(get_db)):
    clean, errors = validate_survey_payload(db, payload)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "اطلاعات فرم معتبر نیست.", "errors": errors})

    survey = Survey(
        first_name=clean["first_name"],
        last_name=clean["last_name"],
        national_code=clean["national_code"],
        phone=clean["phone"],
        province_id=clean["province_id"],
        county_id=clean["county_id"],
        survey_date=clean["survey_date"],
        contact_option_id=clean["contact_option_id"],
    )
    db.add(survey)
    db.flush()
    _save_answers(db, survey, clean)
    db.commit()
    fresh = db.scalars(select(Survey).where(Survey.id == survey.id)).unique().one()
    return {"id": fresh.id, "message": "فرم با موفقیت ذخیره شد.", "record": serialize_survey(fresh)}


@router.get("")
def list_surveys(
    q: str | None = None,
    province_id: int | None = None,
    county_id: int | None = None,
    contact_option_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db),
):
    per_page = max(1, min(per_page, 100))
    page = max(1, page)

    stmt = select(Survey)
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
    if province_id:
        stmt = stmt.where(Survey.province_id == province_id)
    if county_id:
        stmt = stmt.where(Survey.county_id == county_id)
    if contact_option_id:
        stmt = stmt.where(Survey.contact_option_id == contact_option_id)

    pf = parse_jalali_str(date_from or "")
    if pf:
        gy, gm, gd = jalali_to_gregorian(*pf)
        stmt = stmt.where(Survey.survey_date >= dt.date(gy, gm, gd))
    pt = parse_jalali_str(date_to or "")
    if pt:
        gy, gm, gd = jalali_to_gregorian(*pt)
        stmt = stmt.where(Survey.survey_date <= dt.date(gy, gm, gd))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Survey.survey_date.desc(), Survey.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    pages = max(1, -(-total // per_page))
    return {
        "items": [serialize_survey(r) for r in rows],
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
    }


@router.get("/export/excel")
def export_excel(
    q: str | None = None,
    province_id: int | None = None,
    county_id: int | None = None,
    contact_option_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
):
    """خروجی اکسل همان فیلترهای فهرست (بدون صفحه‌بندی)."""
    from ..services.excel_export import build_excel

    filters = dict(
        q=q,
        province_id=province_id,
        county_id=county_id,
        contact_option_id=contact_option_id,
        date_from=date_from,
        date_to=date_to,
    )
    content, filename = build_excel(db, filters)

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{survey_id}")
def get_survey(survey_id: int, db: Session = Depends(get_db)):
    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(status_code=404, detail={"message": "رکورد یافت نشد."})
    return serialize_survey(s)


@router.patch("/{survey_id}")
@router.put("/{survey_id}")
def update_survey(survey_id: int, payload: dict, db: Session = Depends(get_db)):
    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(status_code=404, detail={"message": "رکورد یافت نشد."})
    clean, errors = validate_survey_payload(db, payload)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "اطلاعات فرم معتبر نیست.", "errors": errors})

    s.first_name = clean["first_name"]
    s.last_name = clean["last_name"]
    s.national_code = clean["national_code"]
    s.phone = clean["phone"]
    s.province_id = clean["province_id"]
    s.county_id = clean["county_id"]
    s.survey_date = clean["survey_date"]
    s.contact_option_id = clean["contact_option_id"]
    _save_answers(db, s, clean)
    db.commit()
    # بارگذاری تازهٔ رکورد با پاسخ‌های جدید
    fresh = db.scalars(select(Survey).where(Survey.id == survey_id)).unique().one()
    return {"id": fresh.id, "message": "تغییرات با موفقیت ذخیره شد.", "record": serialize_survey(fresh)}


@router.delete("/{survey_id}")
def delete_survey(survey_id: int, db: Session = Depends(get_db)):
    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(status_code=404, detail={"message": "رکورد یافت نشد."})
    db.delete(s)
    db.commit()
    return {"message": "رکورد حذف شد.", "id": survey_id}


