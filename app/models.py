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

    # ── فیلدهای فرم نمونه (همه اختیاری؛ برای رکوردهای قدیمی رشتهٔ خالی) ──
    # مشاور
    counselor: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    # نوع خدمت
    service_type: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    # تاریخ دریافت خدمت (شمسی، به‌صورت متن استاندارد ۱۴۰۵/۰۵/۱۰)
    service_date: Mapped[str] = mapped_column(String(10), nullable=False, default="", server_default="")
    # نقاط قوت مشاوره تلفنی (خط اول و خط ادامه)
    strengths: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    strengths_extra: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # پیشنهاد بهبود (خط اول و خط ادامه)
    improvement: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    improvement_extra: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # کارشناس نظارت حرفه‌ای: نام و امضا
    supervisor_name: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    supervisor_signature: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")

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


class User(Base):
    """کاربر سامانه با نقش (admin / operator / viewer).

    - رمز به‌صورت PBKDF2-SHA256 ذخیره می‌شود (بدون وابستگی بیرونی).
    - auth_source برای اتصال آینده به SSO است: «local» یعنی رمز داخلی؛
      بعداً می‌تواند «sso» شود بدون تغییر ساختار جداول.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # اگر True باشد، کاربر تا تغییر رمز به هیچ صفحه‌ای جز تغییر رمز راه ندارد
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auth_source: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now_tz)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApiKey(Base):
    """کلیدهای وب‌سرویس برای سیستم‌های دیگر — هر سیستم یک کلید جداگانه.

    فقط هش SHA-256 کلید ذخیره می‌شود؛ کلید کامل فقط هنگام ساخت یک‌بار نمایش
    داده می‌شود.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now_tz)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActivityLog(Base):
    """لاگ فعالیت‌ها (چه‌کسی، چه‌زمانی، چه‌کرد) — برای مدیر قابل مشاهده."""

    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # نام کاربری جدا از کلید خارجی ذخیره می‌شود تا حذف کاربر، لاگ را خراب نکند
    username: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ip: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now_tz, index=True)
