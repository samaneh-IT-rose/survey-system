# -*- coding: utf-8 -*-
"""همگام‌سازی الگوی همهٔ فرم‌ها با فهرست دقیق فایل‌های نمونه.

کاره‌اش برای هر فرم (تلفنی، فردی و فرم‌های بعدی):
  - سؤال‌ها با همان متن‌های نمونهٔ همان فرم فعال و مرتب می‌شوند (ترتیب نمونه)؛
    اگر متنی از قبل وجود داشته باشد شناسه‌اش حفظ می‌شود تا پاسخ‌های
    قدیمی سالم بمانند؛ متن‌های اضافهٔ همان فرم غیرفعال می‌شوند (حذف نمی‌شوند).
  - وضعیت‌های تماس هم به همین شکل.

اجرا روی سرور ویندوز:
    cd C:\\survey-system
    venv\\Scripts\\python scripts\\update_template.py
نیازی به ری‌استارت سرویس نیست (و استارت برنامه هم همین همگام‌سازی را انجام می‌دهد).
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
from app.forms_registry import FORM_KEYS  # noqa: E402
from app.models import ContactOption, Question  # noqa: E402
from app.seed_data.defaults import FORM_TEMPLATES  # noqa: E402


def sync_questions(db, key: str) -> None:
    canonical = FORM_TEMPLATES.get(key, {}).get("questions", [])
    existing = {q.text.strip(): q for q in db.scalars(select(Question)).all()}
    kept_ids: set[int] = set()
    for order, text in enumerate(canonical, start=1):
        q = existing.get(text.strip())
        if q is None:
            q = Question(text=text, display_order=order, is_active=True, form_keys=key)
            db.add(q)
            print(f"  [{key}] + سؤال جدید: {text}")
        else:
            keys = [k.strip() for k in (q.form_keys or "").split(",") if k.strip()]
            if key not in keys:
                q.form_keys = ",".join(keys + [key])
            q.display_order = order
            q.is_active = True
            print(f"  [{key}] = سؤال موجود مرتب شد: {text}")
        db.flush()
        kept_ids.add(q.id if q.id else -1)
    # ردیف‌های همین فرم که دیگر در الگوی رسمی نیستند → غیرفعال (حذف نمی‌شوند)
    for q in db.scalars(select(Question)).all():
        keys = [k.strip() for k in (q.form_keys or "").split(",") if k.strip()]
        if key in keys and q.id not in kept_ids and q.is_active:
            q.is_active = False
            print(f"  [{key}] - سؤال اضافه غیرفعال شد: {q.text}")
    db.flush()


def sync_contacts(db, key: str) -> None:
    canonical = FORM_TEMPLATES.get(key, {}).get("contacts", [])
    existing = {c.text.strip(): c for c in db.scalars(select(ContactOption)).all()}
    kept_ids: set[int] = set()
    for order, (text, requires) in enumerate(canonical, start=1):
        c = existing.get(text.strip())
        if c is None:
            c = ContactOption(
                text=text, display_order=order, is_active=True,
                requires_answers=requires, form_keys=key,
            )
            db.add(c)
            print(f"  [{key}] + وضعیت تماس جدید: {text}")
        else:
            keys = [k.strip() for k in (c.form_keys or "").split(",") if k.strip()]
            if key not in keys:
                c.form_keys = ",".join(keys + [key])
            c.display_order = order
            c.is_active = True
            c.requires_answers = requires
            print(f"  [{key}] = وضعیت تماس موجود مرتب شد: {text}")
        db.flush()
        kept_ids.add(c.id if c.id else -1)
    for c in db.scalars(select(ContactOption)).all():
        keys = [k.strip() for k in (c.form_keys or "").split(",") if k.strip()]
        if key in keys and c.id not in kept_ids and c.is_active:
            c.is_active = False
            print(f"  [{key}] - وضعیت تماس اضافه غیرفعال شد: {c.text}")
    db.flush()


def main() -> int:
    db = SessionLocal()
    try:
        for key in FORM_KEYS:
            print(f"== همگام‌سازی سؤال‌های فرم «{key}» ==")
            sync_questions(db, key)
            print(f"== همگام‌سازی وضعیت‌های تماس فرم «{key}» ==")
            sync_contacts(db, key)
        db.commit()
        print("✔ انجام شد — الگوی همهٔ فرم‌ها دقیقاً مطابق فایل نمونه‌هاست.")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"خطا: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
