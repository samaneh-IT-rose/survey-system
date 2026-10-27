# -*- coding: utf-8 -*-
"""مدل‌های دیتابیس سامانه نظرسنجی (PostgreSQL + SQLAlchemy).

ساختار مطابق سند اجرایی (بخش ۱۳) با ساده‌سازی نسخه اول:
- users / audit_logs / import_jobs در فاز بعدی (با فعال‌سازی نقش‌ها) اضافه می‌شود.
- پرسش‌ها و وضعیت‌های تماس قابل مدیریت از بخش «مدیریت الگوی فرم» هستند.
"""
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now_tz() -> datetime:
    return datetime.now(timezone.utc)


class Province(Base):
    __tablename__ = "provinces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    counties: Mapped[list["County"]] = relationship(
        back_populates="province", cascade="all, delete-orphan", order_by="County.name"
    )


class County(Base):
    __tablename__ = "counties"
    __table_args__ = (UniqueConstraint("province_id", "name", name="uq_county_province"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    province: Mapped["Province"] = relationship(back_populates="counties")


class Question(Base):
    """پرسش‌های امتیازدهی جدول نظرسنجی (قابل ویرایش از مدیریت الگوی فرم)."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    answers: Mapped[list["SurveyAnswer"]] = relationship(back_populates="question")


class ContactOption(Base):
    """وضعیت‌های تماس — متن و تعداد آن‌ها پس از دریافت فایل Word قابل اصلاح است."""

    __tablename__ = "contact_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # اگر False باشد، تکمیل جدول امتیازدهی الزامی نیست (مثلاً «در دسترس نبود»)
    requires_answers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Survey(Base):
    """رکورد اصلی هر فرم نظرسنجی."""

    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(60), nullable=False)
    last_name: Mapped[str] = mapped_column(String(60), nullable=False)
    # کد ملی همیشه رشته است تا صفر ابتدایی از بین نرود
    national_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)

    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), nullable=False)
    county_id: Mapped[int] = mapped_column(ForeignKey("counties.id"), nullable=False)
    # تاریخ نظرسنجی (شمسی ورود می‌شود، به‌صورت میلادی در ستون DATE ذخیره می‌شود)
    survey_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    contact_option_id: Mapped[int | None] = mapped_column(
        ForeignKey("contact_options.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_tz
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_tz, onupdate=_now_tz
    )

    province: Mapped["Province"] = relationship()
    county: Mapped["County"] = relationship()
    contact_option: Mapped["ContactOption | None"] = relationship()
    answers: Mapped[list["SurveyAnswer"]] = relationship(
        back_populates="survey",
        cascade="all, delete-orphan",
        order_by="SurveyAnswer.question_id",
        lazy="selectin",
    )


class SurveyAnswer(Base):
    """پاسخ هر پرسش — حداکثر یک پاسخ برای هر پرسش در هر فرم.

    متن پرسش هنگام ثبت به‌صورت snapshot ذخیره می‌شود تا ویرایش یا تغییر
    بعدیِ متن الگو، معنای پاسخ‌های قدیمی را تغییر ندهد (بخش ۸ سند).
    """

    __tablename__ = "survey_answers"
    __table_args__ = (UniqueConstraint("survey_id", "question_id", name="uq_survey_question"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    value_label: Mapped[str] = mapped_column(String(20), nullable=False)
    value_score: Mapped[int] = mapped_column(Integer, nullable=False)

    survey: Mapped["Survey"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship(back_populates="answers")
