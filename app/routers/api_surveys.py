# -*- coding: utf-8 -*-
"""API رکوردهای نظرسنجی — ثبت، مشاهده، ویرایش، حذف و فهرست با فیلتر."""
from __future__ import annotations

import datetime as dt
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import api_require_perm
from ..constants import PERM_DELETE, PERM_EDIT, PERM_EXPORT, PERM_VIEW, RATING_LABEL_TO_SCORE
from ..database import get_db
from ..forms_registry import DEFAULT_FORM_KEY, form_by_key, form_title
from ..models import Survey, SurveyAnswer, User
from ..services.scope import apply_record_scope, can_view_record, province_scope_id, visible_form_keys
from ..services.validation import validate_survey_payload
from ..utils.activity import log_activity
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
        "form_key": s.form_key or DEFAULT_FORM_KEY,
        "form_title": form_title(s.form_key),
        "first_name": s.first_name,
        "last_name": s.last_name,
        "national_code": s.national_code,
        "phone": s.phone,
        "province": {"id": s.province_id, "name": s.province.name},
        "county": {"id": s.county_id, "name": s.county.name},
        "survey_date": s.survey_date.isoformat(),
        "survey_date_jalali": gdate_to_jalali_str(s.survey_date),
        "counselor": getattr(s, "counselor", "") or "",
        "service_type": getattr(s, "service_type", "") or "",
        "service_date": getattr(s, "service_date", "") or "",
        "strengths": getattr(s, "strengths", "") or "",
        "strengths_extra": getattr(s, "strengths_extra", "") or "",
        "improvement": getattr(s, "improvement", "") or "",
        "improvement_extra": getattr(s, "improvement_extra", "") or "",
        "supervisor_name": getattr(s, "supervisor_name", "") or "",
        "supervisor_signature": getattr(s, "supervisor_signature", "") or "",
        "criticism": getattr(s, "criticism", "") or "",
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
def create_survey(payload: dict, request: Request, user: User = Depends(api_require_perm(PERM_EDIT)), db: Session = Depends(get_db)):
    # اگر قواعد لایهٔ سازمانی یا «فرم‌های مجاز» کاربر این فرم را باز نکرده باشد،
    # ثبت پیش از هر اعتبارسنجی رد می‌شود تا اطلاعاتی دربارهٔ فرم غیرمجاز فاش نشود
    raw_form_key = str(payload.get("form_key") or DEFAULT_FORM_KEY)
    visible = visible_form_keys(user, db)
    if visible is not None and raw_form_key not in visible:
        raise HTTPException(status_code=403, detail={"message": "شما اجازهٔ ثبت این نوع فرم را ندارید."})

    clean, errors = validate_survey_payload(db, payload)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "اطلاعات فرم معتبر نیست.", "errors": errors})

    # کاربرِ دارای استان فقط فرمِ استان خودش را می‌تواند ثبت کند (نسخهٔ 1.8.0)
    scoped_pid = province_scope_id(user, db)
    if scoped_pid is not None and clean["province_id"] != scoped_pid:
        raise HTTPException(status_code=403, detail={"message": "شما فقط می‌توانید فرم‌های استان خودتان را ثبت کنید."})

    survey = Survey(
        first_name=clean["first_name"],
        last_name=clean["last_name"],
        national_code=clean["national_code"],
        phone=clean["phone"],
        province_id=clean["province_id"],
        county_id=clean["county_id"],
        survey_date=clean["survey_date"],
        contact_option_id=clean["contact_option_id"],
        form_key=clean["form_key"],
        created_by=user.id,
        counselor=clean.get("counselor", ""),
        service_type=clean.get("service_type", ""),
        service_date=clean.get("service_date", ""),
        strengths=clean.get("strengths", ""),
        strengths_extra=clean.get("strengths_extra", ""),
        improvement=clean.get("improvement", ""),
        improvement_extra=clean.get("improvement_extra", ""),
        supervisor_name=clean.get("supervisor_name", ""),
        supervisor_signature=clean.get("supervisor_signature", ""),
        criticism=clean.get("criticism", ""),
    )
    db.add(survey)
    db.flush()
    _save_answers(db, survey, clean)
    db.commit()
    log_activity(db, request, user, "survey_create", f"رکورد {survey.id} — {survey.first_name} {survey.last_name}")
    fresh = db.scalars(select(Survey).where(Survey.id == survey.id)).unique().one()
    return {"id": fresh.id, "message": "فرم با موفقیت ذخیره شد.", "record": serialize_survey(fresh)}


@router.get("")
def list_surveys(
    q: str | None = None,
    form: str | None = None,
    counselor: str | None = None,
    service_type: str | None = None,
    province_id: int | None = None,
    county_id: int | None = None,
    contact_option_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    per_page: int = 10,
    user: User = Depends(api_require_perm(PERM_VIEW)),
    db: Session = Depends(get_db),
):
    per_page = max(1, min(per_page, 100))
    page = max(1, page)

    stmt = select(Survey)
    # قیدهای سراسری: «فقط داده‌های خودش» + فرم‌های مجاز + محدودیت استانی کاربر
    stmt = apply_record_scope(stmt, user, db)
    if form:
        stmt = stmt.where(Survey.form_key == form)
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
    if counselor:
        stmt = stmt.where(Survey.counselor == counselor.strip())
    if service_type:
        stmt = stmt.where(Survey.service_type == service_type.strip())

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


@router.get("/facets")
def survey_facets(
    form: str | None = None,
    user: User = Depends(api_require_perm(PERM_VIEW)),
    db: Session = Depends(get_db),
):
    """مقادیر مجزا برای فیلترهای «مشاور» و «خدمات» — با فیلتر اختیاری فرم.

    با قیدهای دسترسی کاربر هم محدود می‌شود تا مقداری از رکوردهایی که
    کاربر حق دیدنشان را ندارد فاش نشود.
    """
    stmt = apply_record_scope(select(Survey.counselor).distinct(), user, db)
    if form:
        stmt = stmt.where(Survey.form_key == form)
    counselors = [
        v for v in db.scalars(stmt).all() if v and str(v).strip()
    ]
    stmt2 = apply_record_scope(select(Survey.service_type).distinct(), user, db)
    if form:
        stmt2 = stmt2.where(Survey.form_key == form)
    services = [
        v for v in db.scalars(stmt2).all() if v and str(v).strip()
    ]
    return {
        "counselors": sorted(counselors),
        "service_types": sorted(services),
    }


@router.get("/export/excel")
def export_excel(
    request: Request,
    q: str | None = None,
    form: str | None = None,
    counselor: str | None = None,
    service_type: str | None = None,
    province_id: int | None = None,
    county_id: int | None = None,
    contact_option_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: User = Depends(api_require_perm(PERM_EXPORT)),
    db: Session = Depends(get_db),
):
    """خروجی اکسل همان فیلترهای فهرست (بدون صفحه‌بندی) — دسترسی «خروجی اکسل»."""
    from ..services.excel_export import build_excel

    filters = dict(
        q=q,
        form=form,
        counselor=counselor,
        service_type=service_type,
        province_id=province_id,
        county_id=county_id,
        contact_option_id=contact_option_id,
        date_from=date_from,
        date_to=date_to,
    )
    content, filename = build_excel(db, filters, user=user)
    log_activity(db, request, user, "excel_export", f"خروجی {filename}")

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{survey_id}")
def get_survey(survey_id: int, user: User = Depends(api_require_perm(PERM_VIEW)), db: Session = Depends(get_db)):
    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(status_code=404, detail={"message": "رکورد یافت نشد."})
    if not can_view_record(user, s, db):
        raise HTTPException(status_code=403, detail={"message": "این رکورد در محدودهٔ دسترسی شما نیست."})
    return serialize_survey(s)


@router.patch("/{survey_id}")
@router.put("/{survey_id}")
def update_survey(survey_id: int, payload: dict, request: Request, user: User = Depends(api_require_perm(PERM_EDIT)), db: Session = Depends(get_db)):
    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(status_code=404, detail={"message": "رکورد یافت نشد."})
    if not can_view_record(user, s, db):
        raise HTTPException(status_code=403, detail={"message": "این رکورد در محدودهٔ دسترسی شما نیست."})
    # ویرایش همیشه با فرمِ خودِ رکورد اعتبارسنجی می‌شود؛ فرم رکورد قابل تغییر نیست
    if not payload.get("form_key"):
        payload = dict(payload)
        payload["form_key"] = s.form_key or DEFAULT_FORM_KEY

    # PATCH جزئی (نسخهٔ 1.9.0): فیلدهای الزامیِ غایب از مقدار فعلی رکورد پر می‌شود
    # تا ویرایش فقط یک فیلد (مثل انتقادات و پیشنهادات) به ۴۲۲ یا حذف بقیهٔ داده‌ها نرسد؛
    # پاسخ‌های جدول هم اگر ارسال نشده باشند با پاسخ‌های موجود رکورد ادامه می‌یابند
    merged = dict(payload)
    if not isinstance(merged.get("answers"), list) or not merged.get("answers"):
        merged["answers"] = [{"question_id": a.question_id, "value": a.value} for a in s.answers]
    _base_map = {
        "first_name": s.first_name,
        "last_name": s.last_name,
        "national_code": s.national_code,
        "phone": s.phone,
        "province_id": s.province_id,
        "county_id": s.county_id,
        "survey_date": gdate_to_jalali_str(s.survey_date),
        "contact_option_id": s.contact_option_id,
    }
    for _k, _v in _base_map.items():
        if merged.get(_k) in (None, "") and _v:
            merged[_k] = _v
    clean, errors = validate_survey_payload(db, merged)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "اطلاعات فرم معتبر نیست.", "errors": errors})

    # کاربرِ دارای استان نمی‌تواند استان رکورد را به استان دیگر ببرد (نسخهٔ 1.8.0)
    scoped_pid = province_scope_id(user, db)
    if scoped_pid is not None and clean["province_id"] != scoped_pid:
        raise HTTPException(status_code=403, detail={"message": "شما فقط می‌توانید فرم‌های استان خودتان را ثبت کنید."})

    s.first_name = clean["first_name"]
    s.last_name = clean["last_name"]
    s.national_code = clean["national_code"]
    s.phone = clean["phone"]
    s.province_id = clean["province_id"]
    s.county_id = clean["county_id"]
    s.survey_date = clean["survey_date"]
    s.contact_option_id = clean["contact_option_id"]
    # فرم رکورد در ویرایش تغییر نمی‌کند (رکورد متعلق به فرم ثبت خودش می‌ماند)
    s.counselor = clean.get("counselor", "")
    s.service_type = clean.get("service_type", "")
    s.service_date = clean.get("service_date", "")
    # نقاط قوت/پیشنهاد بهبود در فرم «مشاورهٔ فردی» نیستند؛ اگر کلاینت نفرستدشان
    # مقدار فعلی رکورد حفظ می‌شود تا ویرایش رکوردهای قدیمی تلفنی داده نکشد
    s.strengths = clean.get("strengths", "") if "strengths" in payload else (s.strengths or "")
    s.strengths_extra = clean.get("strengths_extra", "") if "strengths_extra" in payload else (s.strengths_extra or "")
    s.improvement = clean.get("improvement", "") if "improvement" in payload else (s.improvement or "")
    s.improvement_extra = clean.get("improvement_extra", "") if "improvement_extra" in payload else (s.improvement_extra or "")
    s.supervisor_name = clean.get("supervisor_name", "")
    s.supervisor_signature = clean.get("supervisor_signature", "")
    # انتقادات و پیشنهادات — اگر کلاینت نفرستدشان مقدار فعلی حفظ می‌شود
    s.criticism = clean.get("criticism", "") if "criticism" in payload else (s.criticism or "")
    _save_answers(db, s, clean)
    db.commit()
    log_activity(db, request, user, "survey_update", f"رکورد {survey_id} — {s.first_name} {s.last_name}")
    # بارگذاری تازهٔ رکورد با پاسخ‌های جدید
    fresh = db.scalars(select(Survey).where(Survey.id == survey_id)).unique().one()
    return {"id": fresh.id, "message": "تغییرات با موفقیت ذخیره شد.", "record": serialize_survey(fresh)}


@router.delete("/{survey_id}")
def delete_survey(survey_id: int, request: Request, user: User = Depends(api_require_perm(PERM_DELETE)), db: Session = Depends(get_db)):
    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(status_code=404, detail={"message": "رکورد یافت نشد."})
    if not can_view_record(user, s, db):
        raise HTTPException(status_code=403, detail={"message": "این رکورد در محدودهٔ دسترسی شما نیست."})
    detail = f"رکورد {survey_id} — {s.first_name} {s.last_name}"
    db.delete(s)
    db.commit()
    log_activity(db, request, user, "survey_delete", detail)
    return {"message": "رکورد حذف شد.", "id": survey_id}


