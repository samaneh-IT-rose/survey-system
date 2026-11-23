# -*- coding: utf-8 -*-
"""ورود گروهی کاربران از فایل اکسل (نسخهٔ 1.7.0) — منطق مشترک.

هم دکمهٔ «ورود از اکسل» صفحهٔ مدیریت کاربران و هم دستور seed سرور
(python -m app.seed_users) از همین منطق استفاده می‌کنند تا رفتار یکسان باشد.

فرمت فایل اکسل پذیرفته‌شده: هر شیت یک گروه سازمانی است (نام شیت = سمت/گروه
مثل «مسئولین اجرایی» یا «مدیران کلینیک») و ستون‌ها با سرستون‌های فارسی:
«استان»، «نام و نام خانوادگی»، «کد ملی»، «شماره همراه»، «توضیحات».

عملیات idempotent است: کاربر موجود (با همان نام کاربری = کد ملی) رد می‌شود
با علامت «قبلاً ثبت شده است» — پس اجرای دوبارهٔ فایل هیچ کاربر تکراری نمی‌سازد.
"""
from __future__ import annotations

import io
import re

from sqlalchemy import select

from ..constants import LAYER_DEPARTMENT, LAYER_PROVINCE
from ..forms_registry import form_by_key
from ..models import User
from ..utils.security import hash_password

VALID_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.]{3,60}$")


def layer_for_sheet(sheet_title: str) -> str:
    """لایهٔ دسترسی سازمانی بر اساس نام شیت — نسخهٔ 1.9.0.

    شیت «مدیران کلینیک» (و هر شیت دیگری که «کلینیک» دارد) در لایهٔ
    «ادارهٔ استان» قرار می‌گیرد و بقیه (مثل «مسئولین اجرایی») در لایهٔ
    «سطح استان». مدیر بعداً می‌تواند لایهٔ هر کاربر را در صفحهٔ کاربران عوض کند.
    """
    title = (sheet_title or "")
    return LAYER_DEPARTMENT if "کلینیک" in title else LAYER_PROVINCE

# ارقام فارسی/عربی → لاتین — برای کد ملی و شماره همراه فایل اکسل
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# سرستون‌های پذیرفته‌شده — تطبیق با «شامل بودن» تا «کدملی»/«کد ملی» هر دو کار کند
HEADER_ALIASES: list[tuple[str, tuple[str, ...]]] = [
    ("province_name", ("استان", "province")),
    ("full_name", ("نام و نام خانوادگی", "نام خانوادگی", "نام", "full name", "fullname")),
    ("national_id", ("کد ملی", "کدملی", "national", "کد")),
    ("phone", ("شماره همراه", "موبایل", "همراه", "تلفن", "phone", "mobile")),
    ("department", ("اداره", "واحد", "department", "unit")),
    ("notes", ("توضیحات", "توضیح", "notes")),
]

IMPORT_MAX_ROWS = 2000

VALID_PASSWORD_MODES = ("national_id", "phone", "fixed")


def norm_text(v, limit: int = 200) -> str:
    """متن آزاد — حذف فاصله‌های اضافه و محدود به اندازهٔ ستون."""
    if v is None:
        return ""
    s = re.sub(r"\s+", " ", str(v).strip())
    return s[:limit]


def norm_digits(v, zfill: int = 0) -> str:
    """کد ملی/شماره — فقط رقم لاتین؛ اگر اکسل سلول را عدد ذخیره کرده باشد
    صفرهای ابتدایی بازیابی می‌شود (کد ملی ۱۰ رقمی، شماره همراه ۱۱ رقمی)."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = re.sub(r"\D", "", str(v).strip().translate(_FA_DIGITS))
    if zfill and s and len(s) < zfill:
        s = s.zfill(zfill)
    return s


def match_headers(headers: list[str]) -> dict[str, int]:
    """نقشهٔ فیلد → شاخص ستون با تطبیق نرم سرستون‌ها."""
    out: dict[str, int] = {}
    for idx, raw in enumerate(headers):
        h = norm_text(raw).lower().replace("‌", " ")
        if not h:
            continue
        for field, aliases in HEADER_ALIASES:
            if field in out:
                continue
            if any(alias.lower() in h for alias in aliases):
                out[field] = idx
                break
    return out


def initial_password(password_mode: str, fixed_password: str, nid: str, phone: str) -> str:
    """رمز اولیه بر اساس انتخاب مدیر — کاربر در اولین ورود مجبور به تغییر می‌شود."""
    if password_mode == "phone" and phone:
        return phone
    if password_mode == "fixed" and fixed_password:
        return fixed_password
    return nid


def validate_forms_csv(allowed_forms: str | None) -> str:
    """تبدیل رشتهٔ «tel,individual» به CSV معتبر — فرم ناشناخته خطا."""
    keys: list[str] = []
    for f in str(allowed_forms or "").split(","):
        key = f.strip()
        if not key:
            continue
        if form_by_key(key) is None:
            raise ValueError(f"فرم «{key}» معتبر نیست.")
        if key not in keys:
            keys.append(key)
    return ",".join(keys)


def import_users_from_bytes(
    db,
    data: bytes,
    *,
    level: str,
    role: str,
    password_mode: str = "national_id",
    fixed_password: str = "",
    forms_csv: str = "",
) -> dict:
    """ساخت گروهی کاربران از محتوای فایل اکسل — هر شیت یک گروه سازمانی.

    خروجی: created / skipped / total_rows — یا ValueError با پیام فارسی
    برای خطاهای فایل (خالی، خوانده‌نشدن، بدون ردیف قابل ورود).
    """
    if password_mode not in VALID_PASSWORD_MODES:
        raise ValueError("حالت رمز اولیه معتبر نیست.")
    if password_mode == "fixed" and len(str(fixed_password or "").strip()) < 6:
        raise ValueError("رمز یکسان باید حداقل ۶ نویسه باشد.")

    if not data:
        raise ValueError("فایل اکسل خالی است.")
    try:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except ValueError:
        raise
    except Exception:
        raise ValueError("فایل اکسل خوانده نشد — فایل xlsx معتبر بارگذاری کنید.")

    created: list[dict] = []
    skipped: list[dict] = []
    total_rows = 0

    for sheet in wb.worksheets:
        position = norm_text(sheet.title, 80)
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue
        headers = ["" if h is None else str(h) for h in rows[0]]
        colmap = match_headers(headers)
        if "full_name" not in colmap and "national_id" not in colmap:
            # شیت بدون سرستون شناخته‌شده — رد می‌شود تا شیت‌های بی‌ربط خطا نسازند
            skipped.append({"sheet": sheet.title, "row": 1, "full_name": "", "reason": "سرستون‌های شیت شناسایی نشد"})
            continue
        for r_i, row in enumerate(rows[1:], start=2):
            if r_i > IMPORT_MAX_ROWS + 1:
                break

            def cell(field: str):
                i = colmap.get(field)
                return row[i] if i is not None and i < len(row) else None

            nid = norm_digits(cell("national_id"), zfill=10)[:10]
            phone = norm_digits(cell("phone"), zfill=11)[:15]
            full_name = norm_text(cell("full_name"), 120)
            province = norm_text(cell("province_name"), 80)
            department = norm_text(cell("department"), 80)
            notes = norm_text(cell("notes"), 1000)
            if not any([nid, phone, full_name, province, notes]):
                continue  # ردیف کاملاً خالی
            total_rows += 1
            where = f"«{sheet.title}» ردیف {r_i}"
            if not full_name:
                skipped.append({"sheet": sheet.title, "row": r_i, "full_name": "", "reason": "نام و نام خانوادگی خالی است"})
                continue
            if not nid or len(nid) < 8:
                skipped.append({"sheet": sheet.title, "row": r_i, "full_name": full_name, "reason": "کد ملی نامعتبر است"})
                continue
            if not VALID_USERNAME_RE.match(nid):
                skipped.append({"sheet": sheet.title, "row": r_i, "full_name": full_name, "reason": "کد ملی به‌عنوان نام کاربری معتبر نیست"})
                continue
            if db.scalars(select(User).where(User.username == nid)).first():
                skipped.append({"sheet": sheet.title, "row": r_i, "full_name": full_name, "reason": f"کاربر با کد ملی {nid} قبلاً ثبت شده است"})
                continue
            password = initial_password(password_mode, str(fixed_password or "").strip(), nid, phone)
            if len(password) < 6:
                skipped.append({"sheet": sheet.title, "row": r_i, "full_name": full_name, "reason": "رمز اولیه کوتاه است (حداقل ۶ نویسه)"})
                continue
            user = User(
                username=nid,
                full_name=full_name,
                role=role,
                level=level,
                permissions="",
                allowed_forms=forms_csv,
                password_hash=hash_password(password),
                must_change_password=True,
                national_id=nid,
                province_name=province,
                phone=phone,
                position=position,
                # لایهٔ دسترسی از نام شیت — «مدیران کلینیک» در لایهٔ ادارهٔ استان (نسخهٔ 1.9.0)
                access_layer=layer_for_sheet(sheet.title),
                department=department,
                notes=notes,
            )
            db.add(user)
            db.commit()
            created.append(
                {
                    "username": nid,
                    "full_name": full_name,
                    "position": position,
                    "province": province,
                    "phone": phone,
                    "access_layer": layer_for_sheet(sheet.title),
                    "department": department,
                }
            )

    wb.close()
    if total_rows == 0 and not created:
        raise ValueError(
            "هیچ ردیف قابل ورود در فایل پیدا نشد — سرستون‌ها باید شامل «نام و نام خانوادگی» و «کد ملی» باشد."
        )
    return {"created": created, "skipped": skipped, "total_rows": total_rows}
