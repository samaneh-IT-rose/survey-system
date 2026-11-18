# -*- coding: utf-8 -*-
"""الگوی هر فرم — سؤال‌ها و وضعیت‌های تماس به تفکیک فرم + همگام‌سازی با فایل نمونه.

هر فرم سؤال‌ها و وضعیت‌های تماس خودش را دارد؛ ردیف‌های مشترک بین چند فرم با
ستون form_keys (مثل «tel,individual») برچسب می‌خورند. ترتیب نمایش هر فرم
مطابق ترتیب فایل نمونهٔ همان فرم است.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..forms_registry import FORM_KEYS, matches_form
from ..models import ContactOption, Question
from ..seed_data.defaults import FORM_TEMPLATES


def questions_for_form(db: Session, key: str, *, active_only: bool = True) -> list[Question]:
    """سؤال‌های یک فرم — به ترتیب الگوی رسمی همان فرم."""
    tpl = FORM_TEMPLATES.get(key, {})
    order_index = {t.strip(): i for i, t in enumerate(tpl.get("questions", []), start=1)}
    rows = [
        q for q in db.scalars(
            select(Question).order_by(Question.display_order, Question.id)
        ).all()
        if matches_form(q.form_keys, key) and (q.is_active or not active_only)
    ]
    rows.sort(key=lambda q: (order_index.get(q.text.strip(), 9000), q.display_order, q.id))
    return rows


def contacts_for_form(db: Session, key: str, *, active_only: bool = True) -> list[ContactOption]:
    """وضعیت‌های تماس یک فرم — به ترتیب الگوی رسمی همان فرم."""
    tpl = FORM_TEMPLATES.get(key, {})
    order_index = {t.strip(): i for i, (t, _) in enumerate(tpl.get("contacts", []), start=1)}
    rows = [
        c for c in db.scalars(
            select(ContactOption).order_by(ContactOption.display_order, ContactOption.id)
        ).all()
        if matches_form(c.form_keys, key) and (c.is_active or not active_only)
    ]
    rows.sort(key=lambda c: (order_index.get(c.text.strip(), 9000), c.display_order, c.id))
    return rows


def ensure_form_templates(db: Session) -> None:
    """اطمینان از وجود و فعال‌بودن الگوی رسمی همهٔ فرم‌ها در شروع برنامه.

    - اگر متن رسمیِ یک فرم در دیتابیس نبود، ساخته و به همان فرم برچسب می‌خورد.
    - اگر بود ولی برچسب فرم نداشت، برچسب اضافه می‌شود (بدون از بین بردن
      برچسب‌های قبلی — سؤال مشترک ممکن است).
    - ترتیب نمایش مطابق فایل نمونهٔ همان فرم ثبت می‌شود.
    - ردیف‌های بدون هیچ برچسب و متن ناشناخته (بازماندهٔ ویرایش قدیمی الگو)
      غیرفعال می‌شوند — حذف نمی‌شوند تا پاسخ‌های قدیمی بی‌سرنشین نشوند.
    """
    for key in FORM_KEYS:
        tpl = FORM_TEMPLATES.get(key)
        if not tpl:
            continue

        all_questions = {q.text.strip(): q for q in db.scalars(select(Question)).all()}
        for order, text in enumerate(tpl["questions"], start=1):
            q = all_questions.get(text.strip())
            if q is None:
                q = Question(
                    text=text, display_order=order, is_active=True, form_keys=key
                )
                db.add(q)
            else:
                keys = [k.strip() for k in (q.form_keys or "").split(",") if k.strip()]
                if key not in keys:
                    q.form_keys = ",".join(keys + [key])
                q.is_active = True
                q.display_order = order
            db.flush()

        all_contacts = {c.text.strip(): c for c in db.scalars(select(ContactOption)).all()}
        for order, (text, requires) in enumerate(tpl["contacts"], start=1):
            c = all_contacts.get(text.strip())
            if c is None:
                c = ContactOption(
                    text=text,
                    display_order=order,
                    is_active=True,
                    requires_answers=requires,
                    form_keys=key,
                )
                db.add(c)
            else:
                keys = [k.strip() for k in (c.form_keys or "").split(",") if k.strip()]
                if key not in keys:
                    c.form_keys = ",".join(keys + [key])
                c.is_active = True
                c.display_order = order
                c.requires_answers = requires
            db.flush()

    # بازمانده‌های بی‌برچسب با متن ناشناخته → غیرفعال (رفتار همگام‌سازی قبلی)
    known_texts: set[str] = set()
    for tpl in FORM_TEMPLATES.values():
        known_texts.update(t.strip() for t in tpl["questions"])
        known_texts.update(t.strip() for t, _ in tpl["contacts"])
    for q in db.scalars(select(Question).where(Question.form_keys == "")).all():
        if q.text.strip() not in known_texts:
            q.form_keys = "tel"
        if q.text.strip() not in known_texts and q.is_active:
            q.is_active = False
    for c in db.scalars(select(ContactOption).where(ContactOption.form_keys == "")).all():
        if c.text.strip() not in known_texts:
            c.form_keys = "tel,individual"
    db.commit()
