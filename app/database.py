# -*- coding: utf-8 -*-
"""راه‌اندازی SQLAlchemy و نشست دیتابیس."""
from sqlalchemy import create_engine, inspect, text
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
