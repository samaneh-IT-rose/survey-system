# -*- coding: utf-8 -*-
"""محاسبات داشبورد — آمار با فیلتر و گزارش جداگانهٔ پاسخ‌های خالی (بخش ۱۲ سند).

- پاسخ‌های خالی به‌صورت «بدون پاسخ» جداگانه گزارش می‌شوند و از محاسبات حذف
  یا معادل امتیازی فرض نمی‌شوند.
- میانگین نمایش داده نمی‌شود؛ نگاشت امتیازها نیاز به تأیید سفارش‌دهنده دارد.
- بخش «تحلیل تلفیقی»: درصد رضایت کل همهٔ فرم‌ها را از سؤال «رضایت کل» هر فرم
  می‌گیرد و با هم ترکیب می‌کند — مثلاً سهم تلفنی + فردی + گروهی در «درصد
  رضایت از خدمات ارائه‌شده».
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import NO_ANSWER_LABEL, RATING_LABELS, RATING_LABEL_TO_SCORE
from ..forms_registry import enabled_forms, form_by_key, form_short_title
from ..models import ContactOption, Province, Question, Survey, SurveyAnswer
from ..utils.jalali import gdate_to_jalali_str, jalali_to_gregorian, parse_jalali_str

# رضایت‌های مثبت برای «درصد رضایت» — دو گزینهٔ بالای مقیاس پنج‌گزینه‌ای
SATISFIED_LABELS = ("خیلی زیاد", "زیاد")


def _apply_filters(stmt, q, province_id, county_id, contact_option_id, date_from, date_to,
                   form=None, counselor=None, service_type=None):
    """اعمال فیلترهای مشترک داشبورد/فهرست روی کوئری Survey."""
    from sqlalchemy import or_

    if form:
        stmt = stmt.where(Survey.form_key == form)
    if counselor:
        stmt = stmt.where(Survey.counselor == counselor.strip())
    if service_type:
        stmt = stmt.where(Survey.service_type == service_type.strip())
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
    return stmt


def _satisfaction_counts(db: Session, ids_sub, question_text: str) -> dict:
    """فراوانی گزینه‌های یک سؤال مشخص (با متن snapshot) روی رکوردهای فیلترشده."""
    rows = db.execute(
        select(SurveyAnswer.value_label, func.count())
        .join(ids_sub, SurveyAnswer.survey_id == ids_sub.c.id)
        .where(SurveyAnswer.question_text == question_text)
        .group_by(SurveyAnswer.value_label)
    ).all()
    counts = {label: 0 for label in RATING_LABELS}
    other = 0
    for label, cnt in rows:
        if label in counts:
            counts[label] = cnt
        else:
            other += cnt
    answered = sum(counts.values())
    satisfied = sum(counts.get(l, 0) for l in SATISFIED_LABELS)
    return {
        "counts": counts,
        "other": other,
        "answered": answered,
        "satisfied": satisfied,
        "satisfied_rate": round(satisfied * 100.0 / answered, 1) if answered else None,
    }


def build_dashboard(db: Session, *, q=None, province_id=None, county_id=None,
                    contact_option_id=None, date_from=None, date_to=None,
                    form=None, counselor=None, service_type=None, user=None) -> dict:
    from ..services.scope import apply_record_scope

    # زیرپرس‌وجوی شناسه رکوردهای فیلترشده — مبنای همه آمارها
    # + قیدهای دسترسی کاربر: «فقط داده‌های خودش» و فرم‌های مجاز
    ids_sub = _apply_filters(
        apply_record_scope(select(Survey.id), user) if user is not None else select(Survey.id),
        q, province_id, county_id, contact_option_id, date_from, date_to,
        form=form, counselor=counselor, service_type=service_type,
    ).subquery()

    total = db.scalar(select(func.count()).select_from(ids_sub)) or 0

    completed_stmt = (
        select(func.count())
        .select_from(Survey)
        .join(ContactOption, Survey.contact_option_id == ContactOption.id)
        .where(ContactOption.requires_answers.is_(True))
        .where(Survey.id.in_(select(ids_sub.c.id)))
    )
    completed = db.scalar(completed_stmt) or 0
    completion_rate = round(completed * 100.0 / total, 1) if total else 0.0

    # ── آمار هر سؤال: فراوانی پنج گزینه + پاسخ خالی (جداگانه) ──
    from ..services.form_template import questions_for_form

    # وقتی فیلتر فرم فعال است فقط سؤال‌های همان فرم؛ در حالت همهٔ فرم‌ها
    # سؤال‌های همهٔ فرم‌های فعال (بدون تکرار متن) گزارش می‌شود
    if form:
        questions = questions_for_form(db, form)
    else:
        questions = [
            q_ for q_ in db.scalars(
                select(Question)
                .where(Question.is_active.is_(True))
                .order_by(Question.display_order, Question.id)
            ).all()
        ]

    by_question = []
    if questions:
        answered_rows = db.execute(
            select(SurveyAnswer.question_id, SurveyAnswer.value_label, func.count())
            .join(ids_sub, SurveyAnswer.survey_id == ids_sub.c.id)
            .where(SurveyAnswer.question_id.in_([q.id for q in questions]))
            .group_by(SurveyAnswer.question_id, SurveyAnswer.value_label)
        ).all()

        counts_by_q: dict[int, dict[str, int]] = {}
        for qid, label, cnt in answered_rows:
            counts_by_q.setdefault(qid, {})[label] = cnt

        for qq in questions:
            c = counts_by_q.get(qq.id, {})
            answered_total = sum(c.values())
            by_question.append(
                {
                    "id": qq.id,
                    "text": qq.text,
                    "counts": {label: c.get(label, 0) for label in RATING_LABELS},
                    "no_answer": max(0, total - answered_total),
                }
            )

    # ── توزیع وضعیت تماس ──
    by_contact_rows = db.execute(
        select(ContactOption.text, func.count())
        .select_from(Survey)
        .join(ContactOption, Survey.contact_option_id == ContactOption.id)
        .where(Survey.id.in_(select(ids_sub.c.id)))
        .group_by(ContactOption.text)
        .order_by(func.count().desc())
    ).all()
    by_contact = [{"text": t, "count": n} for t, n in by_contact_rows]

    blank_contact = db.scalar(
        select(func.count())
        .select_from(Survey)
        .where(Survey.id.in_(select(ids_sub.c.id)))
        .where(Survey.contact_option_id.is_(None))
    ) or 0
    if blank_contact:
        by_contact.append({"text": "بدون وضعیت", "count": blank_contact})

    # ── برترین استان‌ها ──
    by_province_rows = db.execute(
        select(Province.name, func.count())
        .select_from(Survey)
        .join(Province, Survey.province_id == Province.id)
        .where(Survey.id.in_(select(ids_sub.c.id)))
        .group_by(Province.name)
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    by_province = [{"name": n, "count": c} for n, c in by_province_rows]

    # ── روند روزانه (برچسب شمسی) ──
    by_day_rows = db.execute(
        select(Survey.survey_date, func.count())
        .where(Survey.id.in_(select(ids_sub.c.id)))
        .group_by(Survey.survey_date)
        .order_by(Survey.survey_date)
    ).all()
    by_day = [{"date": gdate_to_jalali_str(d), "count": c} for d, c in by_day_rows]

    # ── تحلیل تلفیقی بین‌فرمی — درصد رضایت از خدمات ارائه‌شده ──
    # برای هر فرم فعال: آمار سؤال «رضایت کل» همان فرم + تعداد رکورد؛
    # عدد نهایی = ترکیب وزنی همهٔ فرم‌ها (مجموع راضی‌ها / مجموع پاسخ‌ها)
    # فقط فرم‌های مجاز کاربر + رکوردهای در محدودهٔ دسترسی او
    per_form_stats = []
    if user is not None:
        from ..services.scope import allowed_form_keys as _afk

        _keys = _afk(user)
    else:
        _keys = None
    per_form_forms = [form_by_key(form)] if form else enabled_forms()
    if _keys is not None:
        per_form_forms = [f for f in per_form_forms if f and f["key"] in _keys]
    for f in per_form_forms:
        if not f:
            continue
        f_ids_sub = _apply_filters(
            apply_record_scope(select(Survey.id), user) if user is not None else select(Survey.id),
            q, province_id, county_id, contact_option_id, date_from, date_to,
            form=f["key"], counselor=counselor, service_type=service_type,
        ).subquery()
        f_total = db.scalar(select(func.count()).select_from(f_ids_sub)) or 0
        sat = _satisfaction_counts(db, f_ids_sub, f["overall_question"])
        per_form_stats.append(
            {
                "key": f["key"],
                "title": f["title"],
                "short_title": f["short_title"],
                "total": f_total,
                "overall_question": f["overall_question"],
                "answered": sat["answered"],
                "satisfied": sat["satisfied"],
                "satisfied_rate": sat["satisfied_rate"],
                "counts": sat["counts"],
                "no_answer": max(0, f_total - sat["answered"]),
            }
        )

    total_answered = sum(x["answered"] for x in per_form_stats)
    total_satisfied = sum(x["satisfied"] for x in per_form_stats)
    combined_rate = (
        round(total_satisfied * 100.0 / total_answered, 1) if total_answered else None
    )
    combined = {
        "label": "درصد رضایت از خدمات ارائه‌شده",
        "total_records": sum(x["total"] for x in per_form_stats),
        "answered": total_answered,
        "satisfied": total_satisfied,
        "satisfied_rate": combined_rate,
        "per_form": per_form_stats,
    }

    return {
        "total": total,
        "completed": completed,
        "completion_rate": completion_rate,
        "no_answer_label": NO_ANSWER_LABEL,
        "rating_labels": RATING_LABELS,
        "by_question": by_question,
        "by_contact": by_contact,
        "by_province": by_province,
        "by_day": by_day,
        "form_filter": form or "",
        "combined": combined,
    }
