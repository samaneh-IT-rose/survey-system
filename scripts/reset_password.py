# -*- coding: utf-8 -*-
"""بازیابی رمز عبور از خط فرمان — برای وقتی که رمز مدیر فراموش شده است.

اجرا روی سرور ویندوز (PowerShell یا cmd):

    cd C:\\survey-system
    venv\\Scripts\\python scripts\\reset_password.py --list
    venv\\Scripts\\python scripts\\reset_password.py admin

بعد از اجرای دستور دوم، رمز جدید را دوبار تایپ کنید (هنگام تایپ نمایش
داده نمی‌شود). نیازی به ری‌استارت سرویس نیست.

روش دوم (بدون پرسش — رمز مستقیم در دستور):
    venv\\Scripts\\python scripts\\reset_password.py admin "NewPass#2026"

نکته: اگر رمز را در دستور بنویسید در تاریخچهٔ دستورها می‌ماند؛ روش اول
(پرسش رمز) امن‌تر است.
"""
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# اگر متغیر محیطی تنظیم نشده باشد، همان دیتابیس کنار برنامه استفاده می‌شود
# (روی سرور ویندوز: C:\\survey-system\\data\\survey.db)
os.environ.setdefault(
    "SURVEY_DATABASE_URL",
    f"sqlite:///{ROOT.as_posix()}/data/survey.db",
)

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

MIN_PASSWORD_LEN = 6


def list_users() -> int:
    db = SessionLocal()
    try:
        users = db.scalars(select(User).order_by(User.id)).all()
        if not users:
            print("هیچ کاربری در دیتابیس نیست.")
            return 0
        print(f"{'شناسه':<6}{'نام کاربری':<20}{'نقش':<12}{'فعال':<8}{'نام'}")
        for u in users:
            role_fa = {"admin": "مدیر", "expert": "کارشناس", "viewer": "مشاهده‌گر"}.get(u.role, u.role)
            print(f"{u.id:<6}{u.username:<20}{role_fa:<12}{'بله' if u.is_active else 'خیر':<8}{u.full_name or ''}")
        return 0
    finally:
        db.close()


def reset_password(username: str, new_password: str | None) -> int:
    username = username.strip().lower()
    if not new_password:
        p1 = getpass.getpass("رمز عبور جدید: ")
        p2 = getpass.getpass("تکرار رمز عبور جدید: ")
        if p1 != p2:
            print("خطا: تکرار رمز با رمز جدید یکسان نیست.")
            return 1
        new_password = p1

    if len(new_password) < MIN_PASSWORD_LEN:
        print(f"خطا: رمز جدید باید حداقل {MIN_PASSWORD_LEN} نویسه باشد.")
        return 1

    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.username == username)).first()
        if user is None:
            print(f"خطا: کاربری با نام «{username}» پیدا نشد.")
            print("برای دیدن فهرست کاربرها:  venv\\Scripts\\python scripts\\reset_password.py --list")
            return 1
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.is_active = True  # اگر حساب غیرفعال شده بود، با بازیابی رمز فعال می‌شود
        db.commit()
        print(f"✔ رمز عبور کاربر «{username}» با موفقیت عوض شد.")
        print("  حالا می‌توانید با همین رمز وارد سامانه شوید:")
        print(f"  http://127.0.0.1:3010/app/login")
        print("  (پیشنهاد: بعد از ورود، از منوی کاربر رمز را عوض کنید.)")
        return 0
    finally:
        db.close()


def main() -> int:
    args = [a for a in sys.argv[1:]]
    if not args or args[0] in ("-h", "--help", "/?"):
        print(__doc__)
        return 0
    if args[0] == "--list":
        return list_users()
    return reset_password(args[0], args[1] if len(args) > 1 else None)


if __name__ == "__main__":
    sys.exit(main())
