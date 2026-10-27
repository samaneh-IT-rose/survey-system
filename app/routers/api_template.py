# -*- coding: utf-8 -*-
"""API مدیریت الگوی فرم — ویرایش متن پرسش‌ها و وضعیت‌های تماس (بخش ۸ سند)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ContactOption, Question

router = APIRouter(prefix="/api/template", tags=["template"])


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
def create_question(payload: dict, db: Session = Depends(get_db)):
    text = str(payload.get("text") or "").strip()
    if not (2 <= len(text) <= 300):
        raise HTTPException(422, detail={"message": "متن سؤال باید بین ۲ تا ۳۰۰ نویسه باشد."})
    max_order = db.scalar(select(func.max(Question.display_order))) or 0
    q = Question(text=text, display_order=int(max_order) + 1)
    db.add(q)
    db.commit()
    db.refresh(q)
    return serialize_question(q)


@router.patch("/questions/{qid}")
def update_question(qid: int, payload: dict, db: Session = Depends(get_db)):
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
    db.refresh(q)
    return serialize_question(q)


@router.post("/questions/{qid}/move")
def move_question(qid: int, payload: dict, db: Session = Depends(get_db)):
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
    return {"message": "ترتیب به‌روزرسانی شد."}


@router.get("/contact-options")
def list_contacts(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ContactOption).order_by(ContactOption.display_order, ContactOption.id)
    ).all()
    return [serialize_contact(c) for c in rows]


@router.post("/contact-options")
def create_contact(payload: dict, db: Session = Depends(get_db)):
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
    db.refresh(c)
    return serialize_contact(c)


@router.patch("/contact-options/{cid}")
def update_contact(cid: int, payload: dict, db: Session = Depends(get_db)):
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
    db.refresh(c)
    return serialize_contact(c)


@router.post("/contact-options/{cid}/move")
def move_contact(cid: int, payload: dict, db: Session = Depends(get_db)):
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
    return {"message": "ترتیب به‌روزرسانی شد."}
