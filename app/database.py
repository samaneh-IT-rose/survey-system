# -*- coding: utf-8 -*-
"""راه‌اندازی SQLAlchemy و نشست دیتابیس."""
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

if DATABASE_URL.startswith("sqlite"):
    # SQLite (نصب سبک، مثلاً روی ویندوز): آرگومان‌های pool_size/max_overflow معتبر نیستند
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """نشست دیتابیس برای هر درخواست."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ستون‌های جدید جدول surveys (فیلدهای فرم نمونه) — اگر در دیتابیس موجود نبودند
# هنگام استارت به‌صورت idempotent اضافه می‌شوند؛ داده‌های قدیمی دست‌نخورده می‌مانند.
SURVEY_NEW_COLUMNS: dict[str, str] = {
    "counselor": "VARCHAR(120) NOT NULL DEFAULT ''",
    "service_type": "VARCHAR(120) NOT NULL DEFAULT ''",
    "service_date": "VARCHAR(10) NOT NULL DEFAULT ''",
    "strengths": "TEXT NOT NULL DEFAULT ''",
    "strengths_extra": "TEXT NOT NULL DEFAULT ''",
    "improvement": "TEXT NOT NULL DEFAULT ''",
    "improvement_extra": "TEXT NOT NULL DEFAULT ''",
    "supervisor_name": "VARCHAR(120) NOT NULL DEFAULT ''",
    "supervisor_signature": "VARCHAR(255) NOT NULL DEFAULT ''",
}


def ensure_survey_columns(target_engine) -> list[str]:
    """افزودن ستون‌های جدید جدول surveys در صورت نبود (SQLite و Postgres)."""
    added: list[str] = []
    inspector = inspect(target_engine)
    if "surveys" not in inspector.get_table_names():
        return added
    existing = {c["name"] for c in inspector.get_columns("surveys")}
    with target_engine.begin() as conn:
        for name, ddl in SURVEY_NEW_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE surveys ADD COLUMN {name} {ddl}"))
                added.append(name)
    return added


# ستون‌های جدید جدول users (سطح کاربری و سطوح دسترسی) — مهاجرت خودکار idempotent
USER_NEW_COLUMNS: dict[str, str] = {
    # سطح کاربری: admin (مدیر سامانه) یا user (کاربر سامانه)
    "level": "VARCHAR(20) NOT NULL DEFAULT 'user'",
    # سطوح دسترسی «view,edit,print,export,delete» — خالی یعنی پیش‌فرض نقش
    "permissions": "TEXT NOT NULL DEFAULT ''",
}


def ensure_user_columns(target_engine) -> list[str]:
    """افزودن ستون‌های سطح کاربری/سطوح دسترسی به جدول users در صورت نبود.

    کاربران موجود بی‌درنگ سازگار می‌شوند: هر کس نقش admin دارد سطحش
    «مدیر سامانه» ثبت می‌شود؛ بقیه «کاربر سامانه» با دسترسی‌های پیش‌فرض نقش.
    """
    added: list[str] = []
    inspector = inspect(target_engine)
    if "users" not in inspector.get_table_names():
        return added
    existing = {c["name"] for c in inspector.get_columns("users")}
    with target_engine.begin() as conn:
        for name, ddl in USER_NEW_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))
                added.append(name)
        if "level" in added:
            # کاربران قدیمیِ مدیر → سطح مدیر سامانه (یک‌بار، فقط هنگام افزودن ستون)
            conn.execute(text("UPDATE users SET level = 'admin' WHERE role = 'admin'"))
    return added


def ensure_schema_updates(target_engine) -> None:
    """همهٔ مهاجرت‌های خودکار سبک — در شروع برنامه اجرا می‌شود."""
    ensure_survey_columns(target_engine)
    ensure_user_columns(target_engine)
    ensure_form_columns(target_engine)


# ---------- مهاجرت چند-فرمی (نسخهٔ 1.4.0) ----------
FORM_NEW_COLUMNS: dict[str, tuple[str, str]] = {
    # جدول، نام ستون، DDL
    ("questions", "form_keys"): ("TEXT", "NOT NULL DEFAULT ''"),
    ("contact_options", "form_keys"): ("TEXT", "NOT NULL DEFAULT ''"),
    ("surveys", "form_key"): ("VARCHAR(20)", "NOT NULL DEFAULT 'tel'"),
}


def ensure_form_columns(target_engine) -> list[str]:
    """افزودن ستون‌های form_keys/form_key برای پشتیبانی از چند فرم.

    رکوردهای موجود دست‌نخورده می‌مانند: ردیف‌های الگوی بدون برچسب بعداً در
    tag_legacy_rows برچسب می‌خورند و رکوردهای قدیمی به فرم تلفنی تعلق می‌گیرند.
    """
    added: list[str] = []
    inspector = inspect(target_engine)
    tables = inspector.get_table_names()
    with target_engine.begin() as conn:
        for (table, name), (col_type, extra) in FORM_NEW_COLUMNS.items():
            if table not in tables:
                continue
            cols = {c["name"] for c in inspector.get_columns(table)}
            if name not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {col_type} {extra}"))
                added.append(f"{table}.{name}")
    return added


def tag_legacy_rows(target_engine) -> None:
    """برچسب‌گذاری ردیف‌های الگو و رکوردهای قدیمی که form_keys/form_key ندارند.

    - سؤال/وضعیت تماس بدون برچسب: با تطبیق متن با الگوهای رسمی فرم‌ها برچسب
      می‌خورد (تلفنی یا فردی یا هر دو)؛ متن ناشناخته → تلفنی (همهٔ دادهٔ
      قدیمی سامانه تلفنی بوده است).
    - رکوردهای نظرسنجی: اگر snapshot پاسخ‌های رکورد فقط با سؤال‌های فرم
      فردی همخوان بود و هیچ سؤال تلفنی نداشت، فردی ثبت می‌شود؛ در غیر این
      صورت تلفنی (رفع فاصلهٔ نسخه‌ای 1.2.6 تا این نسخه — idempotent).
    """
    from .forms_registry import FORM_KEYS
    from .seed_data.defaults import FORM_TEMPLATES

    canonical_q: dict[str, set[str]] = {
        key: {t.strip() for t in tpl["questions"]} for key, tpl in FORM_TEMPLATES.items()
    }
    canonical_c: dict[str, set[str]] = {
        key: {t.strip() for t, _ in tpl["contacts"]} for key, tpl in FORM_TEMPLATES.items()
    }

    with SessionLocal() as db:
        from .models import ContactOption, Question, Survey, SurveyAnswer

        # سؤال‌های بدون برچسب
        for q in db.scalars(select(Question).where(Question.form_keys == "")).all():
            keys = [k for k in FORM_KEYS if q.text.strip() in canonical_q[k]]
            q.form_keys = ",".join(keys) if keys else "tel"
        # وضعیت‌های تماس بدون برچسب
        for c in db.scalars(select(ContactOption).where(ContactOption.form_keys == "")).all():
            keys = [k for k in FORM_KEYS if c.text.strip() in canonical_c[k]]
            # وضعیت ناشناخته در همهٔ فرم‌ها مشترک می‌شود تا از هیچ صفحه‌ای پنهان نماند
            c.form_keys = ",".join(keys) if keys else ",".join(FORM_KEYS)
        # رکوردهای نظرسنجی: تشخیص فرم از snapshot سؤال‌های پاسخ‌داده‌شده
        ind_texts = canonical_q.get("individual", set())
        tel_texts = canonical_q.get("tel", set())
        answer_texts: dict[int, set[str]] = {}
        for sid, txt in db.execute(select(SurveyAnswer.survey_id, SurveyAnswer.question_text)):
            if txt:
                answer_texts.setdefault(sid, set()).add(txt.strip())
        fixed = 0
        for s in db.scalars(select(Survey)).all():
            if s.form_key not in (None, "", "tel"):
                continue  # برچسب درست دارد
            texts = answer_texts.get(s.id, set())
            if texts and (texts & ind_texts) and not (texts & tel_texts):
                s.form_key = "individual"
                fixed += 1
            elif s.form_key in (None, ""):
                s.form_key = "tel"
                fixed += 1
        db.commit()
        if fixed:
            import logging

            logging.getLogger("survey.migrate").warning(
                "tag_legacy_rows: %s survey row(s) relabeled", fixed
            )
