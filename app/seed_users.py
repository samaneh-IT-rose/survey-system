# -*- coding: utf-8 -*-
"""ورود خودکار کاربران سازمانی از فایل اکسل — برای اجرا روی سرور.

با فایل رسمی «مدیران کلینیک و مسئولین اجرایی» (دو شیت) کاربران سامانه ساخته
می‌شوند: نام کاربری = کد ملی، رمز اولیه = کد ملی (با تغییر اجباری در اولین
ورود)، سمت = نام شیت، استان = ستون استان (مبنای محدودیت استانی نسخهٔ 1.8.0).

عملیات idempotent است: اجرای دوباره کاربر تکراری نمی‌سازد — کاربران موجود
با پیام «قبلاً ثبت شده است» رد می‌شوند.

استفاده:
    python -m app.seed_users [--file data/users_seed.xlsx]
                             [--role operator] [--level user]
                             [--password-mode national_id] [--fixed-password X]
                             [--allowed-forms tel,individual,group]

خروجی: گزارش تعداد ساخته‌شده/ردشده با دلیل؛ کد خروج ۰ در موفقیت.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .constants import LEVEL_ADMIN, LEVEL_USER, ROLE_OPERATOR
from .database import Base, SessionLocal
from .services.roles import valid_role_keys
from .services.users_import import import_users_from_bytes, validate_forms_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed_users",
        description="ورود گروهی کاربران از فایل اکسل (idempotent — اجرای دوباره امن است)",
    )
    parser.add_argument(
        "--file",
        default="app/seed_data/users_seed.xlsx",
        help="مسیر فایل اکسل (پیش‌فرض: app/seed_data/users_seed.xlsx — فایل رسمی دو شیتی)",
    )
    parser.add_argument("--role", default=ROLE_OPERATOR, help="نقش کاربران جدید (پیش‌فرض: operator)")
    parser.add_argument("--level", default=LEVEL_USER, choices=(LEVEL_ADMIN, LEVEL_USER), help="سطح کاربری (پیش‌فرض: user)")
    parser.add_argument(
        "--password-mode",
        default="national_id",
        choices=("national_id", "phone", "fixed"),
        help="رمز اولیه: کد ملی / شماره همراه / یکسان (پیش‌فرض: کد ملی)",
    )
    parser.add_argument("--fixed-password", default="", help="رمز یکسان برای حالت fixed")
    parser.add_argument("--allowed-forms", default="", help="فرم‌های مجاز CSV مثل tel,individual,group — خالی یعنی همهٔ فرم‌ها")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"✖ فایل اکسل پیدا نشد: {path}")
        return 1

    # ساخت جداول/مهاجرت‌ها اگر نباشند — روی سرور برنامه در استارت همین کار را
    # می‌کند؛ این خط فقط اجرای مستقل seed (قبل از اولین استارت) را امن می‌کند
    from .database import engine
    from .database import ensure_schema_updates as _ensure_schema
    from .services.roles import ensure_roles as _ensure_roles

    Base.metadata.create_all(bind=engine)
    _ensure_schema(engine)
    with SessionLocal() as _db:
        _ensure_roles(_db)

    with SessionLocal() as db:
        if args.role not in valid_role_keys(db):
            print(f"✖ نقش «{args.role}» در سامانه وجود ندارد.")
            return 1
        try:
            forms_csv = validate_forms_csv(args.allowed_forms)
        except ValueError as exc:
            print(f"✖ {exc}")
            return 1

        try:
            result = import_users_from_bytes(
                db,
                path.read_bytes(),
                level=args.level,
                role=args.role,
                password_mode=args.password_mode,
                fixed_password=args.fixed_password,
                forms_csv=forms_csv,
            )
        except ValueError as exc:
            print(f"✖ {exc}")
            return 1

        created = result["created"]
        skipped = result["skipped"]
        print(f"✔ {len(created)} کاربر ساخته شد؛ {len(skipped)} ردیف رد شد (از {result['total_rows']} ردیف).")
        for c in created:
            print(
                f"  + {c['full_name']} — کد ملی {c['username']}"
                + (f" — {c['position']}" if c["position"] else "")
                + (f" — {c['province']}" if c["province"] else "")
            )
        for s in skipped:
            print(f"  - {s['sheet']} ردیف {s['row']}: {s['reason']}")

        from .utils.activity import log_activity

        log_activity(
            db,
            None,
            None,
            "users_seed",
            f"seed اکسل {path.name}: {len(created)} کاربر ساخته شد، {len(skipped)} ردیف رد شد",
            username_override="system",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
