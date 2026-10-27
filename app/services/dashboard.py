# -*- coding: utf-8 -*-
"""محاسبات داشبورد — آمار با فیلتر و گزارش جداگانهٔ پاسخ‌های خالی (بخش ۱۲ سند).

- پاسخ‌های خالی به‌صورت «بدون پاسخ» جداگانه گزارش می‌شوند و از محاسبات حذف
  یا معادل امتیازی فرض نمی‌شوند.
- میانگین نمایش داده نمی‌شود؛ نگاشت امتیازها نیاز به تأیید سفارش‌دهنده دارد.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import NO_ANSWER_LABEL, RATING_LABELS
from ..models import ContactOption, Province, Question, Survey, SurveyAnswer
from ..utils.jalali import gdate_to_jalali_str, jalali_to_gregorian, parse_jalali_str


def _apply_filters(stmt, q, province_id, county_id, contact_option_id, date_from, date_to):
    """اعمال فیلترهای مشترک داشبورد/فهرست روی کوئری Survey."""
    from sqlalchemy import or_

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


def build_dashboard(db: Session, *, q=None, province_id=None, county_id=None,
                    contact_option_id=None, date_from=None, date_to=None) -> dict:
    # زیرپرس‌وجوی شناسه رکوردهای فیلترشده — مبنای همه آمارها
    ids_sub = _apply_filters(
        select(Survey.id), q, province_id, county_id, contact_option_id, date_from, date_to
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
    questions = db.scalars(
        select(Question)
        .where(Question.is_active.is_(True))
        .order_by(Question.display_order, Question.id)
    ).all()

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

        for q in questions:
            c = counts_by_q.get(q.id, {})
            answered_total = sum(c.values())
            by_question.append(
                {
                    "id": q.id,
                    "text": q.text,
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
    }
