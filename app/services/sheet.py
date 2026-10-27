# -*- coding: utf-8 -*-
"""ساخت زمینه مشترک قالب ورقه A4 (چاپ مرورگر و PDF سرور)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import APP_TITLE, ORG_NAME
from ..models import ContactOption, Question, Survey
from ..routers.api_surveys import serialize_survey
from ..utils.jalali import today_jalali_str


def build_sheet_context(db: Session, survey: Survey, *, interactive: bool) -> dict:
    record = serialize_survey(survey)
    active_questions = db.scalars(
        select(Question)
        .where(Question.is_active.is_(True))
        .order_by(Question.display_order, Question.id)
    ).all()
    answers_by_qid = {a["question_id"]: a["value"] for a in record["answers"]}
    contacts = db.scalars(
        select(ContactOption)
        .where(ContactOption.is_active.is_(True))
        .order_by(ContactOption.display_order, ContactOption.id)
    ).all()

    return {
        "record": record,
        "questions": [
            {"id": q.id, "text": q.text, "value": answers_by_qid.get(q.id)}
            for q in active_questions
        ],
        "contact_options": [{"id": c.id, "text": c.text} for c in contacts],
        "interactive": interactive,
        "org_name": ORG_NAME,
        "app_title": APP_TITLE,
        "today": today_jalali_str(),
    }
