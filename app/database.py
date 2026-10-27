# -*- coding: utf-8 -*-
"""راه‌اندازی SQLAlchemy و نشست دیتابیس."""
from sqlalchemy import create_engine
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
