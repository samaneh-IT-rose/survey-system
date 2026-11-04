# -*- coding: utf-8 -*-
"""API مدیریت الگوی فرم — ویرایش متن پرسش‌ها و وضعیت‌های تماس (بخش ۸ سند)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import api_admin
from ..database import get_db
from ..models import ContactOption, Question, User
from ..utils.activity import log_activity

router = APIRouter(prefix="/api/template", tags=["template"], dependencies=[Depends(api_admin)])


def serialize_question(q: Question) -> dict:
    return {"id": q.id, "text": q.text, "display_order": q.display_order, "is_active": q.is_active}


def serialize_contact(c: ContactOption) -> dict:
    return {
        "id": c.id,
        "text": c.text,
        "display_order": c.display_order,
        "is_active": c.is_active,
        "requires_answers": c.requires_answers,
    }


@router.get("/questions")
def list_questions(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Question).order_by(Question.display_order, Question.id)
    ).all()
    return [serialize_question(q) for q in rows]


@router.post("/questions")
def create_question(payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    text = str(payload.get("text") or "").strip()
    if not (2 <= len(text) <= 300):
        raise HTTPException(422, detail={"message": "متن سؤال باید بین ۲ تا ۳۰۰ نویسه باشد."})
    max_order = db.scalar(select(func.max(Question.display_order))) or 0
    q = Question(text=text, display_order=int(max_order) + 1)
    db.add(q)
    db.commit()
    log_activity(db, request, user, "template_question_create", f"سؤال {q.id}: {text[:80]}")
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
    direction = payload.get("direction")
    rows = list(db.scalars(select(Question).order_by(Question.display_order, Question.id)))
    idx = next((i for i, r in enumerate(rows) if r.id == qid), None)
    if idx is None:
        raise HTTPException(404, detail={"message": "سؤال یافت نشد."})
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
    """جای‌گذاری گروهی متن سؤال‌ها — برای انتقال دقیق سؤال‌های فرم اصلی.

    هر سطر یک سؤال است. سؤال‌های موجود به‌ترتیب با متن‌های جدید به‌روزرسانی
    می‌شوند (شناسه ثابت می‌ماند تا پاسخ‌های قدیمی بی‌معنا نشوند)،
    اگر متن‌ها بیشتر باشند سؤال جدید ساخته و اگر کمتر باشند
    سؤال‌های اضافی غیرفعال می‌شوند.
    """
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

    existing = list(db.scalars(
        select(Question)
        .where(Question.is_active.is_(True))
        .order_by(Question.display_order, Question.id)
    ))
    for i, text in enumerate(texts):
        if i < len(existing):
            existing[i].text = text
            existing[i].is_active = True
        else:
            db.add(Question(text=text, display_order=1000 + i))
    for extra in existing[len(texts):]:
        extra.is_active = False
    db.flush()

    # شماره‌گذاری یکدست سؤال‌های فعال
    actives = list(db.scalars(
        select(Question).where(Question.is_active.is_(True)).order_by(Question.display_order, Question.id)
    ))
    for i, q in enumerate(actives, start=1):
        q.display_order = i
    db.commit()
    log_activity(db, request, user, "template_question_bulk", f"جای‌گذاری گروهی {len(texts)} سؤال")
    rows = db.scalars(select(Question).order_by(Question.display_order, Question.id)).all()
    return {"replaced": len(texts), "questions": [serialize_question(q) for q in rows]}


@router.get("/contact-options")
def list_contacts(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ContactOption).order_by(ContactOption.display_order, ContactOption.id)
    ).all()
    return [serialize_contact(c) for c in rows]


@router.post("/contact-options")
def create_contact(payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    text = str(payload.get("text") or "").strip()
    if not (2 <= len(text) <= 300):
        raise HTTPException(422, detail={"message": "متن وضعیت تماس باید بین ۲ تا ۳۰۰ نویسه باشد."})
    c = ContactOption(
        text=text,
        requires_answers=bool(payload.get("requires_answers", True)),
        display_order=999,
    )
    db.add(c)
    db.commit()
    log_activity(db, request, user, "template_contact_update", f"افزودن وضعیت تماس: {text[:80]}")
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
    """جای‌گذاری گروهی وضعیت‌های تماس — مثل سؤال‌ها؛ شناسه‌های ثابت می‌مانند."""
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

    existing = list(db.scalars(
        select(ContactOption)
        .where(ContactOption.is_active.is_(True))
        .order_by(ContactOption.display_order, ContactOption.id)
    ))
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
            ))
    for extra in existing[len(texts):]:
        extra.is_active = False
    db.flush()

    actives = list(db.scalars(
        select(ContactOption).where(ContactOption.is_active.is_(True)).order_by(ContactOption.display_order, ContactOption.id)
    ))
    for i, c in enumerate(actives, start=1):
        c.display_order = i
    db.commit()
    log_activity(db, request, user, "template_contact_bulk", f"جای‌گذاری گروهی {len(texts)} وضعیت تماس")
    rows = db.scalars(select(ContactOption).order_by(ContactOption.display_order, ContactOption.id)).all()
    return {"replaced": len(texts), "contact_options": [serialize_contact(c) for c in rows]}


@router.post("/contact-options/{cid}/move")
def move_contact(cid: int, payload: dict, request: Request, user: User = Depends(api_admin), db: Session = Depends(get_db)):
    direction = payload.get("direction")
    rows = list(db.scalars(select(ContactOption).order_by(ContactOption.display_order, ContactOption.id)))
    idx = next((i for i, r in enumerate(rows) if r.id == cid), None)
    if idx is None:
        raise HTTPException(404, detail={"message": "وضعیت تماس یافت نشد."})
    swap = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap < len(rows):
        rows[idx], rows[swap] = rows[swap], rows[idx]
        for i, r in enumerate(rows):
            r.display_order = i + 1
        db.commit()
        log_activity(db, request, user, "template_contact_update", f"جابه‌جایی وضعیت تماس {cid}")
    return {"message": "ترتیب به‌روزرسانی شد."}
