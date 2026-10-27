# -*- coding: utf-8 -*-
"""راه‌اندازی SQLAlchemy و نشست دیتابیس."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

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
