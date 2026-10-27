# -*- coding: utf-8 -*-
"""تبدیل و اعتبارسنجی تاریخ شمسی (جلالی).

الگوریتم بر مبنای jalaali-js (مجوز MIT) پیاده‌سازی شده و
در آزمون‌ها با کتابخانه jdatetime تطبیق داده می‌شود. کنترل روز نامعتبر،
طول ماه و سال کبیسه در سمت سرور انجام می‌شود (بخش ۵ سند).
"""
from __future__ import annotations

import datetime as dt

BREAKS = (
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
)

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

MONTH_NAMES = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)

WEEKDAY_NAMES = ("دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه")


def _div(a: int, b: int) -> int:
    """تقسیم صحیح با قطع به سمت صفر (مطابق رفتار JavaScript)."""
    if a == 0:
        return 0
    q = abs(a) // abs(b)
    return q if (a > 0) == (b > 0) else -q


def _mod(a: int, b: int) -> int:
    return a - _div(a, b) * b


def _jal_cal(jy: int) -> tuple[int, int, int]:
    """محاسبه سال کبیسه و روز آغاز سال جلالی؛ خروجی: (leap, gy, march)."""
    breaks = BREAKS
    bl = len(breaks)
    gy = jy + 621
    leap_j = -14
    jp = breaks[0]
    jump = 0
    for i in range(1, bl):
        jm = breaks[i]
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, 33) * 8 + _div(_mod(jump, 33), 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div(_mod(n, 33) + 3, 4)
    if _mod(jump, 33) == 4 and jump - n == 4:
        leap_j += 1
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + _div(jump + 4, 33) * 33
    leap = _mod(_mod(n + 1, 33) - 1, 4)
    if leap == -1:
        leap = 4
    return leap, gy, march


def _g2d(gy: int, gm: int, gd: int) -> int:
    """تاریخ میلادی به شماره روز ژولینی."""
    d = (
        _div((gy + _div(gm - 8, 6) + 100100) * 1461, 4)
        + _div(153 * _mod(gm + 9, 12) + 2, 5)
        + gd
        - 34840408
    )
    return d - _div(_div(gy + 100100 + _div(gm - 8, 6), 100) * 3, 4) + 752


def _d2g(jdn: int) -> tuple[int, int, int]:
    """شماره روز ژولینی به تاریخ میلادی."""
    j = 4 * jdn + 139361631
    j += _div(_div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = _div(_mod(j, 1461), 4) * 5 + 308
    gd = _div(_mod(i, 153), 5) + 1
    gm = _mod(_div(i, 153), 12) + 1
    gy = _div(j, 1461) - 100100 + _div(8 - gm, 6)
    return gy, gm, gd


def is_jalali_leap(jy: int) -> bool:
    return _jal_cal(jy)[0] == 0


def jalali_month_length(jy: int, jm: int) -> int:
    if 1 <= jm <= 6:
        return 31
    if 7 <= jm <= 11:
        return 30
    if jm == 12:
        return 30 if is_jalali_leap(jy) else 29
    raise ValueError("ماه جلالی باید بین ۱ تا ۱۲ باشد")


def is_valid_jalali(jy: int, jm: int, jd: int) -> bool:
    if not (1 <= jy <= 1600 and 1 <= jm <= 12):
        return False
    return 1 <= jd <= jalali_month_length(jy, jm)


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    r = _jal_cal(jy)
    jdn = _g2d(r[1], 3, r[2]) + (jm - 1) * 31 - _div(jm, 7) * (jm - 7) + jd - 1
    return _d2g(jdn)


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    jdn = _g2d(gy, gm, gd)
    jy = gy - 621
    r = _jal_cal(jy)
    jdn1f = _g2d(r[1], 3, r[2])
    k = jdn - jdn1f
    if k >= 0:
        if k <= 185:
            return jy, 1 + _div(k, 31), _mod(k, 31) + 1
        k -= 186
    else:
        jy -= 1
        k += 179
        if r[0] == 1:
            k += 1
    return jy, 7 + _div(k, 30), _mod(k, 30) + 1


def gdate_to_jalali_str(d: dt.date, with_zero_padding: bool = True) -> str:
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    if with_zero_padding:
        return f"{jy:04d}/{jm:02d}/{jd:02d}"
    return f"{jy}/{jm}/{jd}"


def parse_jalali_str(value: str) -> tuple[int, int, int] | None:
    """تبدیل رشته تاریخ شمسی (با ارقام فارسی یا لاتین، جداکننده / یا -) به سه‌تایی.

    مطابق سند: ارقام فارسی/عربی به انگلیسی تبدیل و فقط فاصله ابتدا/انتها حذف می‌شود.
    """
    if not isinstance(value, str):
        return None
    raw = value.translate(PERSIAN_DIGITS).strip()
    for sep in ("/", "-", "."):
        if sep in raw:
            parts = [p for p in raw.split(sep) if p != ""]
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                jy, jm, jd = (int(p) for p in parts)
                if len(str(jy)) == 4 and is_valid_jalali(jy, jm, jd):
                    return jy, jm, jd
                return None
    return None


def weekday_name(gd: dt.date) -> str:
    """نام روز هفته فارسی (دوشنبه = 0)."""
    return WEEKDAY_NAMES[gd.weekday()]


def today_jalali_str() -> str:
    """تاریخ امروز به وقت تهران، قالب ۱۴۰۵/۰۸/۰۵."""
    import zoneinfo

    from ..config import TZ_NAME

    return gdate_to_jalali_str(
        dt.datetime.now(dt.timezone.utc).astimezone(zoneinfo.ZoneInfo(TZ_NAME)).date()
    )
