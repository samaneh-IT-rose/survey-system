# -*- coding: utf-8 -*-
"""داده اولیه سامانه: استان‌ها/شهرستان‌ها، سؤال‌ها، وضعیت‌های تماس و رکوردهای نمونه.

اجرا:
    python scripts/seed.py            # فقط داده‌های پایه
    python scripts/seed.py --demo 45  # + ۴۵ رکورد نمونه
    python scripts/seed.py --reset-demo  # حذف رکوردهای نمونه قبلی و ساخت مجدد
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import datetime as dt

from sqlalchemy import delete, func, select

from app.constants import RATING_LABELS, RATING_LABEL_TO_SCORE
from app.database import SessionLocal, engine
from app.models import Base, ContactOption, County, Province, Question, Survey, SurveyAnswer
from app.seed_data.defaults import DEFAULT_CONTACT_OPTIONS, DEFAULT_QUESTIONS
from app.seed_data.locations import LOCATIONS
from app.utils.jalali import gdate_to_jalali_str, jalali_to_gregorian, today_jalali_str
from app.utils.national_code import make_valid_national_code

FIRST_NAMES = ["علی", "محمد", "رضا", "حسین", "مهدی", "امیر", "حسن", "فاطمه", "زهرا", "مریم",
               "زینب", "سارا", "نرگس", "الهام", "سمیرا", "مهسا", "کیانا", "آرش", "بهنام", "پویا"]
LAST_NAMES = ["رضایی", "محمدی", "حسینی", "احمدی", "کریمی", "موسوی", "جعفری", "صادقی", "نوری", "شریفی",
              "قاسمی", "رحیمی", "مرادی", "کاظمی", "توکلی", "عزیزی", "فرهادی", "سلطانی", "اکبری", "نجفی"]


def seed_locations(db):
    n_p = db.scalar(select(func.count()).select_from(Province)) or 0
    if n_p > 0:
        print(f"• استان‌ها از قبل موجود است ({n_p} ردیف) — رد شد.")
        return
    for pname, counties in LOCATIONS.items():
        p = Province(name=pname)
        db.add(p)
        db.flush()
        for cname in dict.fromkeys(counties):  # حذف تکراری با حفظ ترتیب
            db.add(County(province_id=p.id, name=cname))
    db.commit()
    print(f"• {len(LOCATIONS)} استان و شهرستان‌های آن ثبت شد.")


def seed_template(db):
    if (db.scalar(select(func.count()).select_from(Question)) or 0) == 0:
        for i, text in enumerate(DEFAULT_QUESTIONS, start=1):
            db.add(Question(text=text, display_order=i))
        print(f"• {len(DEFAULT_QUESTIONS)} سؤال پیش‌فرض ثبت شد.")
    if (db.scalar(select(func.count()).select_from(ContactOption)) or 0) == 0:
        for i, (text, req) in enumerate(DEFAULT_CONTACT_OPTIONS, start=1):
            db.add(ContactOption(text=text, display_order=i, requires_answers=req))
        print(f"• {len(DEFAULT_CONTACT_OPTIONS)} وضعیت تماس پیش‌فرض ثبت شد.")
    db.commit()


def seed_demo(db, count=40):
    provinces = db.scalars(select(Province)).all()
    counties_by_pid = {}
    for c in db.scalars(select(County)).all():
        counties_by_pid.setdefault(c.province_id, []).append(c)
    questions = db.scalars(select(Question).where(Question.is_active.is_(True)).order_by(Question.display_order)).all()
    contacts = db.scalars(select(ContactOption).where(ContactOption.is_active.is_(True)).order_by(ContactOption.display_order)).all()
    requiring = [c for c in contacts if c.requires_answers]
    not_requiring = [c for c in contacts if not c.requires_answers]

    # بازه تاریخ: ۹۰ روز اخیر تا امروز (شمسی)
    jy, jm, jd = (int(x) for x in today_jalali_str().split("/"))
    today_g = dt.date(*jalali_to_gregorian(jy, jm, jd))
    rng = random.Random(1405)

    created = 0
    for i in range(count):
        days_ago = rng.randint(0, 90)
        gdate = today_g - dt.timedelta(days=days_ago)
        province = rng.choice(provinces)
        county = rng.choice(counties_by_pid.get(province.id, []))
        if county is None:
            continue
        nine = "".join(rng.choice("0123456789") for _ in range(9))
        code = make_valid_national_code(nine)
        phone = "09" + "".join(rng.choice("0123456789") for _ in range(9))

        contact = rng.choice(requiring) if rng.random() < 0.82 else rng.choice(not_requiring)
        s = Survey(
            first_name=rng.choice(FIRST_NAMES),
            last_name=rng.choice(LAST_NAMES),
            national_code=code,
            phone=phone,
            province_id=province.id,
            county_id=county.id,
            survey_date=gdate,
            contact_option_id=contact.id,
        )
        db.add(s)
        db.flush()
        if contact.requires_answers:
            for q in questions:
                label = rng.choices(RATING_LABELS, weights=[30, 26, 22, 13, 9])[0]
                db.add(SurveyAnswer(
                    survey_id=s.id,
                    question_id=q.id,
                    question_text=q.text,
                    value_label=label,
                    value_score=RATING_LABEL_TO_SCORE[label],
                ))
        created += 1
    db.commit()
    print(f"• {created} رکورد نمونه ساخته شد (تاریخ‌ها در ۹۰ روز اخیر).")


def reset_demo(db):
    n = db.execute(delete(SurveyAnswer)).rowcount
    n2 = db.execute(delete(Survey)).rowcount
    db.commit()
    print(f"• {n2} رکورد نمونه و {n} پاسخ حذف شد.")


def main():
    demo = "--demo" in sys.argv
    reset = "--reset-demo" in sys.argv
    count = 40
    if "--demo" in sys.argv:
        try:
            count = int(sys.argv[sys.argv.index("--demo") + 1])
        except (ValueError, IndexError):
            pass

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_locations(db)
        seed_template(db)
        if reset:
            reset_demo(db)
        if demo or reset:
            seed_demo(db, count)
        total = db.scalar(select(func.count()).select_from(Survey)) or 0
        print(f"✓ انجام شد — مجموع رکوردهای نظرسنجی: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
