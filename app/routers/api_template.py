# -*- coding: utf-8 -*-
"""API مدیریت الگوی فرم — ویرایش متن پرسش‌ها و وضعیت‌های تماس (بخش ۸ سند).

از نسخهٔ 1.4.0 الگو به تفکیک فرم مدیریت می‌شود: همهٔ مسیرها پارامتر
«form» (کلید فرم) می‌گیرند و فقط ردیف‌های همان فرم را نشان می‌دهند/تغییر می‌دهند.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import api_admin
from ..database import get_db
from ..forms_registry import form_by_key
from ..models import ContactOption, Question, User
from ..services.form_template import contacts_for_form, questions_for_form
from ..utils.activity import log_activity

router = APIRouter(prefix="/api/template", tags=["template"], dependencies=[Depends(api_admin)])


def _form_or_404(form: str | None) -> str:
    f = form_by_key(form or "")
    if f is None:
        raise HTTPException(422, detail={"message": "کلید فرم معتبر نیست."})
    return f["key"]


def serialize_question(q: Question) -> dict:
    return {"id": q.id, "text": q.text, "display_order": q.display_order, "is_active": q.is_active, "form_keys": q.form_keys or ""}


def serialize_contact(c: ContactOption) -> dict:
    return {
        "id": c.id,
        "text": c.text,
        "display_order": c.display_order,
        "is_active": c.is_active,
        "requires_answers": c.requires_answers,
        "form_keys": c.form_keys or "",
    }


@router.get("/questions")
def list_questions(form: str | None = None, db: Session = Depends(get_db)):
    key = _form_or_404(form)
    # همهٔ ردیف‌های فرم (فعال و غیرفعال) برای مدیریت الگو
    rows = questions_for_form(db, key, active_only=False)
    return [serialize_question(q) for q in rows]


@router.post("/questions")
def create_question(payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    key = _form_or_404(payload.get("form"))
    text = str(payload.get("text") or "").strip()
    if not (2 <= len(text) <= 300):
        raise HTTPException(422, detail={"message": "متن سؤال باید بین ۲ تا ۳۰۰ نویسه باشد."})
    actives = questions_for_form(db, key)
    q = Question(text=text, display_order=int(len(actives) + 1), is_active=True, form_keys=key)
    db.add(q)
    db.commit()
    log_activity(db, request, user, "template_question_create", f"سؤال {q.id} (فرم {key}): {text[:80]}")
    db.refresh(q)
    return serialize_question(q)


@router.patch("/questions/{qid}")
def update_question(qid: int, payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    q = db.get(Question, qid)
    if q is None:
        raise HTTPException(404, detail={"message": "سؤال یافت نشد."})
    if "text" in payload:
        text = str(payload.get("text") or "").strip()
        if not (2 <= len(text) <= 300):
            raise HTTPException(422, detail={"message": "متن سؤال باید بین ۲ تا ۳۰۰ نویسه باشد."})
        q.text = text
    if "is_active" in payload:
        q.is_active = bool(payload["is_active"])
    if "display_order" in payload:
        try:
            q.display_order = int(payload["display_order"])
        except (TypeError, ValueError):
            pass
    db.commit()
    log_activity(db, request, user, "template_question_update", f"سؤال {qid}")
    db.refresh(q)
    return serialize_question(q)


@router.post("/questions/{qid}/move")
def move_question(qid: int, payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    form = payload.get("form")
    direction = payload.get("direction")
    if not form:
        # سازگاری: اگر فرم ارسال نشده بود از برچسب خود ردیف می‌خوانیم
        q0 = db.get(Question, qid)
        form = (q0.form_keys.split(",")[0] if q0 and q0.form_keys else "tel") if q0 else None
        key = _form_or_404(form) if form else None
    else:
        key = _form_or_404(form)
    rows = list(questions_for_form(db, key))
    idx = next((i for i, r in enumerate(rows) if r.id == qid), None)
    if idx is None:
        raise HTTPException(404, detail={"message": "سؤال در این فرم یافت نشد."})
    swap = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap < len(rows):
        rows[idx], rows[swap] = rows[swap], rows[idx]
        for i, r in enumerate(rows):
            r.display_order = i + 1
        db.commit()
        log_activity(db, request, user, "template_question_update", f"جابه‌جایی سؤال {qid}")
    return {"message": "ترتیب به‌روزرسانی شد."}


@router.post("/questions/bulk")
def bulk_questions(payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    """جای‌گذاری گروهی متن سؤال‌های یک فرم — شناسه‌های ثابت می‌مانند تا پاسخ‌های
    قدیمی سالم بمانند؛ کمتر → غیرفعال، بیشتر → سؤال جدید همان فرم."""
    key = _form_or_404(payload.get("form"))
    raw = payload.get("texts")
    if not isinstance(raw, list):
        raise HTTPException(422, detail={"message": "فهرست متن‌ها ارسال نشده است."})
    texts: list[str] = []
    for item in raw:
        t = str(item or "").strip()
        if not t:
            continue
        if not (2 <= len(t) <= 300):
            raise HTTPException(422, detail={"message": "هر سؤال باید بین ۲ تا ۳۰۰ نویسه باشد: " + t[:60]})
        texts.append(t)
    if not texts:
        raise HTTPException(422, detail={"message": "حداقل یک سؤال لازم است."})
    if len(texts) > 40:
        raise HTTPException(422, detail={"message": "حداکثر ۴۰ سؤال پذیرفته می‌شود."})

    existing = list(questions_for_form(db, key))
    for i, text in enumerate(texts):
        if i < len(existing):
            existing[i].text = text
            existing[i].is_active = True
        else:
            db.add(Question(text=text, display_order=1000 + i, is_active=True, form_keys=key))
    for extra in existing[len(texts):]:
        extra.is_active = False
    db.flush()

    for i, q in enumerate(questions_for_form(db, key), start=1):
        q.display_order = i
    db.commit()
    log_activity(db, request, user, "template_question_bulk", f"جای‌گذاری گروهی {len(texts)} سؤال (فرم {key})")
    rows = questions_for_form(db, key, active_only=False)
    return {"replaced": len(texts), "questions": [serialize_question(q) for q in rows]}


@router.get("/contact-options")
def list_contacts(form: str | None = None, db: Session = Depends(get_db)):
    # بدون فرم (مثلاً برای فیلتر آرشیو): همهٔ وضعیت‌های فعال همهٔ فرم‌ها بدون تکرار
    if not form:
        rows = db.scalars(
            select(ContactOption)
            .where(ContactOption.is_active.is_(True))
            .order_by(ContactOption.display_order, ContactOption.id)
        ).all()
        seen: set[str] = set()
        out = []
        for c in rows:
            if c.text in seen:
                continue
            seen.add(c.text)
            out.append(serialize_contact(c))
        return out
    key = _form_or_404(form)
    rows = contacts_for_form(db, key, active_only=False)
    return [serialize_contact(c) for c in rows]


@router.post("/contact-options")
def create_contact(payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    key = _form_or_404(payload.get("form"))
    text = str(payload.get("text") or "").strip()
    if not (2 <= len(text) <= 300):
        raise HTTPException(422, detail={"message": "متن وضعیت تماس باید بین ۲ تا ۳۰۰ نویسه باشد."})
    c = ContactOption(
        text=text,
        requires_answers=bool(payload.get("requires_answers", True)),
        display_order=999,
        form_keys=key,
    )
    db.add(c)
    db.commit()
    log_activity(db, request, user, "template_contact_update", f"افزودن وضعیت تماس (فرم {key}): {text[:80]}")
    db.refresh(c)
    return serialize_contact(c)


@router.patch("/contact-options/{cid}")
def update_contact(cid: int, payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    c = db.get(ContactOption, cid)
    if c is None:
        raise HTTPException(404, detail={"message": "وضعیت تماس یافت نشد."})
    if "text" in payload:
        text = str(payload.get("text") or "").strip()
        if not (2 <= len(text) <= 300):
            raise HTTPException(422, detail={"message": "متن وضعیت تماس باید بین ۲ تا ۳۰۰ نویسه باشد."})
        c.text = text
    if "is_active" in payload:
        c.is_active = bool(payload["is_active"])
    if "requires_answers" in payload:
        c.requires_answers = bool(payload["requires_answers"])
    db.commit()
    log_activity(db, request, user, "template_contact_update", f"وضعیت تماس {cid}")
    db.refresh(c)
    return serialize_contact(c)


@router.post("/contact-options/bulk")
def bulk_contacts(payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    """جای‌گذاری گروهی وضعیت‌های تماس یک فرم — مثل سؤال‌ها؛ شناسه‌های ثابت می‌مانند."""
    key = _form_or_404(payload.get("form"))
    raw = payload.get("texts")
    if not isinstance(raw, list):
        raise HTTPException(422, detail={"message": "فهرست متن‌ها ارسال نشده است."})
    texts: list[str] = []
    for item in raw:
        t = str(item or "").strip()
        if not t:
            continue
        if not (2 <= len(t) <= 300):
            raise HTTPException(422, detail={"message": "هر وضعیت تماس باید بین ۲ تا ۳۰۰ نویسه باشد: " + t[:60]})
        texts.append(t)
    if not texts:
        raise HTTPException(422, detail={"message": "حداقل یک وضعیت تماس لازم است."})
    if len(texts) > 40:
        raise HTTPException(422, detail={"message": "حداکثر ۴۰ وضعیت تماس پذیرفته می‌شود."})
    flags = payload.get("requires_answers")
    flags = flags if isinstance(flags, list) else []

    existing = list(contacts_for_form(db, key))
    for i, text in enumerate(texts):
        if i < len(existing):
            existing[i].text = text
            existing[i].is_active = True
            if i < len(flags):
                existing[i].requires_answers = bool(flags[i])
        else:
            db.add(ContactOption(
                text=text,
                requires_answers=bool(flags[i]) if i < len(flags) else False,
                display_order=1000 + i,
                form_keys=key,
            ))
    for extra in existing[len(texts):]:
        extra.is_active = False
    db.flush()

    for i, c in enumerate(contacts_for_form(db, key), start=1):
        c.display_order = i
    db.commit()
    log_activity(db, request, user, "template_contact_bulk", f"جای‌گذاری گروهی {len(texts)} وضعیت تماس (فرم {key})")
    rows = contacts_for_form(db, key, active_only=False)
    return {"replaced": len(texts), "contact_options": [serialize_contact(c) for c in rows]}


@router.post("/contact-options/{cid}/move")
def move_contact(cid: int, payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    form = payload.get("form")
    direction = payload.get("direction")
    if not form:
        c0 = db.get(ContactOption, cid)
        form = (c0.form_keys.split(",")[0] if c0 and c0.form_keys else "tel") if c0 else None
        key = _form_or_404(form) if form else None
    else:
        key = _form_or_404(form)
    rows = list(contacts_for_form(db, key))
    idx = next((i for i, r in enumerate(rows) if r.id == cid), None)
    if idx is None:
        raise HTTPException(404, detail={"message": "وضعیت تماس در این فرم یافت نشد."})
    swap = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap < len(rows):
        rows[idx], rows[swap] = rows[swap], rows[idx]
        for i, r in enumerate(rows):
            r.display_order = i + 1
        db.commit()
        log_activity(db, request, user, "template_contact_update", f"جابه‌جایی وضعیت تماس {cid}")
    return {"message": "ترتیب به‌روزرسانی شد."}
