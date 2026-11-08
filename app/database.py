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
