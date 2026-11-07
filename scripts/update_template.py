# -*- coding: utf-8 -*-
"""همگام‌سازی الگوی فرم (سؤال‌ها و وضعیت‌های تماس) با فهرست دقیق فایل نمونه.

کاره‌اش:
  - سؤال‌ها با همان متن‌های نمونه فعال و مرتب می‌شوند (ترتیب نمونه)؛
    اگر متنی از قبل وجود داشته باشد شناسه‌اش حفظ می‌شود تا پاسخ‌های
    قدیمی سالم بمانند؛ متن‌های اضافه غیرفعال می‌شوند (حذف نمی‌شوند).
  - وضعیت‌های تماس هم به همین شکل.

اجرا روی سرور ویندوز:
    cd C:\\survey-system
    venv\\Scripts\\python scripts\\update_template.py
نیازی به ری‌استارت سرویس نیست.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault(
    "SURVEY_DATABASE_URL",
    f"sqlite:///{ROOT.as_posix()}/data/survey.db",
)

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import ContactOption, Question  # noqa: E402
from app.seed_data.defaults import DEFAULT_CONTACT_OPTIONS, DEFAULT_QUESTIONS  # noqa: E402


def sync_questions(db) -> None:
    existing = {q.text.strip(): q for q in db.scalars(select(Question)).all()}
    kept_ids: set[int] = set()
    for order, text in enumerate(DEFAULT_QUESTIONS, start=1):
        q = existing.get(text.strip())
        if q is None:
            q = Question(text=text, display_order=order, is_active=True)
            db.add(q)
            print(f"  + سؤال جدید: {text}")
        else:
            q.display_order = order
            q.is_active = True
            print(f"  = سؤال موجود مرتب شد: {text}")
        kept_ids.add(q.id if q.id else -1)
    # غیرفعال‌کردن بقیه (حذف نمی‌شوند تا پاسخ‌های قدیمی بی‌سرنشین نشوند)
    for q in db.scalars(select(Question)).all():
        if q.id not in kept_ids and q.is_active:
            q.is_active = False
            print(f"  - سؤال اضافه غیرفعال شد: {q.text}")
    db.flush()


def sync_contacts(db) -> None:
    existing = {c.text.strip(): c for c in db.scalars(select(ContactOption)).all()}
    kept_ids: set[int] = set()
    for order, (text, requires) in enumerate(DEFAULT_CONTACT_OPTIONS, start=1):
        c = existing.get(text.strip())
        if c is None:
            c = ContactOption(
                text=text, display_order=order, is_active=True, requires_answers=requires
            )
            db.add(c)
            print(f"  + وضعیت تماس جدید: {text}")
        else:
            c.display_order = order
            c.is_active = True
            c.requires_answers = requires
            print(f"  = وضعیت تماس موجود مرتب شد: {text}")
        kept_ids.add(c.id if c.id else -1)
    for c in db.scalars(select(ContactOption)).all():
        if c.id not in kept_ids and c.is_active:
            c.is_active = False
            print(f"  - وضعیت تماس اضافه غیرفعال شد: {c.text}")
    db.flush()


def main() -> int:
    db = SessionLocal()
    try:
        print("== همگام‌سازی سؤال‌ها با فایل نمونه ==")
        sync_questions(db)
        print("== همگام‌سازی وضعیت‌های تماس با فایل نمونه ==")
        sync_contacts(db)
        db.commit()
        print("✔ انجام شد — الگو اکنون دقیقاً مطابق فایل نمونه است.")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"خطا: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
