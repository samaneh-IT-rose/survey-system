# -*- coding: utf-8 -*-
"""وب‌سرویس رسمی نسخهٔ ۱ — برای سیستم‌های دیگر (بدون ورود صفحه‌ای).

احراز هویت: هدر «X-API-Key» با کلیدی که مدیر از پنل «کلیدهای API» می‌سازد.

مسیرها (همه با پیشوند /app):
  GET  /app/api/v1/template        — پرسش‌ها و وضعیت‌های تماس (ساختار فرم)
  GET  /app/api/v1/surveys         — فهرست رکوردها با فیلتر و صفحه‌بندی
  GET  /app/api/v1/surveys/{id}    — جزئیات یک رکورد
  POST /app/api/v1/surveys         — ثبت نظرسنجی از سیستم دیگر
  GET  /app/api/v1/dashboard       — آمار همان داشبورد

مستندات تعاملی کامل: صفحهٔ /docs
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ApiKey, ContactOption, Question, Survey, User
from ..services.dashboard import build_dashboard
from ..services.validation import validate_survey_payload
from ..utils.activity import log_activity
from ..utils.jalali import jalali_to_gregorian, parse_jalali_str
from ..utils.security import hash_api_key
from .api_surveys import serialize_survey

router = APIRouter(prefix="/api/v1", tags=["web-service-v1"])


def current_api_key(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> ApiKey:
    from datetime import datetime, timezone as tz

    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail={"message": "کلید وب‌سرویس ارسال نشده است. هدر X-API-Key را بفرستید."},
        )
    item = db.scalars(select(ApiKey).where(ApiKey.key_hash == hash_api_key(x_api_key))).first()
    if item is None or not item.is_active:
        raise HTTPException(status_code=401, detail={"message": "کلید وب‌سرویس نامعتبر یا غیرفعال است."})
    item.last_used_at = datetime.now(tz.utc)
    db.commit()
    return item


@router.get("/template")
def v1_template(key: ApiKey = Depends(current_api_key), db: Session = Depends(get_db)):
    questions = db.scalars(
        select(Question).where(Question.is_active.is_(True)).order_by(Question.display_order, Question.id)
    ).all()
    contacts = db.scalars(
        select(ContactOption).where(ContactOption.is_active.is_(True)).order_by(ContactOption.display_order, ContactOption.id)
    ).all()
    return {
        "questions": [{"id": q.id, "text": q.text, "order": q.display_order} for q in questions],
        "contact_options": [
            {"id": c.id, "text": c.text, "requires_answers": c.requires_answers} for c in contacts
        ],
        "allowed_answer_values": ["خیلی زیاد", "زیاد", "متوسط", "کم", "خیلی کم"],
    }


@router.get("/surveys")
def v1_list_surveys(
    q: str | None = None,
    province_id: int | None = None,
    county_id: int | None = None,
    contact_option_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    per_page: int = 10,
    key: ApiKey = Depends(current_api_key),
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

    return {
        "items": [serialize_survey(r) for r in rows],
        "total": total,
        "page": page,
        "pages": max(1, -(-total // per_page)),
    }


@router.get("/surveys/{survey_id}")
def v1_get_survey(survey_id: int, key: ApiKey = Depends(current_api_key), db: Session = Depends(get_db)):
    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(404, detail={"message": "رکورد یافت نشد."})
    return serialize_survey(s)


@router.post("/surveys")
def v1_create_survey(payload: dict, key: ApiKey = Depends(current_api_key), db: Session = Depends(get_db)):
    clean, errors = validate_survey_payload(db, payload)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "اطلاعات فرم معتبر نیست.", "errors": errors})

    from ..models import SurveyAnswer
    from ..constants import RATING_LABEL_TO_SCORE
    from sqlalchemy import delete as sa_delete

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
    db.execute(sa_delete(SurveyAnswer).where(SurveyAnswer.survey_id == survey.id))
    db.flush()
    for item in clean["answers"]:
        question_text = next(
            (qq.text for qq in clean["active_questions"] if qq.id == item["question_id"]),
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
    db.commit()

    fresh = db.scalars(select(Survey).where(Survey.id == survey.id)).unique().one()
    log_activity(
        db, None, None, "v1_survey_create",
        f"ثبت رکورد {survey.id} از سیستم «{key.name}»",
        username_override=f"api:{key.name}",
    )
    return {"id": fresh.id, "message": "فرم با موفقیت ذخیره شد.", "record": serialize_survey(fresh)}


@router.get("/dashboard")
def v1_dashboard(
    province_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    key: ApiKey = Depends(current_api_key),
    db: Session = Depends(get_db),
):
    return build_dashboard(db, province_id=province_id, date_from=date_from, date_to=date_to)
