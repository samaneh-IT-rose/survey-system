# -*- coding: utf-8 -*-
"""اعتبارسنجی کد ملی — دقیقاً مطابق الگوریتم دوم سند اجرایی (بخش ۵).

- ورودی ۸ تا ۱۰ رقمی پذیرفته و با تکمیل صفرهای ابتدایی به ۱۰ رقم تبدیل می‌شود.
- ارقام فارسی و عربی به انگلیسی تبدیل می‌شوند.
- فقط فاصله ابتدا و انتها حذف می‌شود؛ حروف، خط تیره و فاصله داخلی پذیرفته نیست.
- کد ملی به‌صورت رشته ذخیره می‌شود تا صفر ابتدایی از بین نرود.
"""
from __future__ import annotations

import re

DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_national_code(value: str) -> str | None:
    """کد ملی معتبر را به‌صورت رشته ۱۰ رقمی برمی‌گرداند؛ در غیر این صورت None."""
    if not isinstance(value, str):
        return None

    code = value.translate(DIGIT_MAP).strip()

    if re.fullmatch(r"[0-9]{8,10}", code) is None:
        return None

    code = code.zfill(10)

    if len(set(code)) == 1:
        return None

    checksum = sum(int(code[i]) * (10 - i) for i in range(9))
    remainder = checksum % 11
    expected = remainder if remainder < 2 else 11 - remainder

    return code if int(code[-1]) == expected else None


def make_valid_national_code(nine_digits: str) -> str | None:
    """برای تولید داده آزمایشی: از ۹ رقم، رقم کنترلی معتبر می‌سازد."""
    if not isinstance(nine_digits, str) or re.fullmatch(r"[0-9]{9}", nine_digits) is None:
        return None
    checksum = sum(int(nine_digits[i]) * (10 - i) for i in range(9))
    remainder = checksum % 11
    check = remainder if remainder < 2 else 11 - remainder
    return nine_digits + str(check)
