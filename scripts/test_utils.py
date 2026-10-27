# -*- coding: utf-8 -*-
"""آزمون ابزارهای تاریخ جلالی و کد ملی (اجرا: python scripts/test_utils.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import datetime as dt

import jdatetime

from app.utils import jalali
from app.utils.national_code import make_valid_national_code, normalize_national_code


def test_anchors():
    # نقاط لنگر معروف
    cases = [
        (dt.date(2024, 3, 20), (1403, 1, 1)),   # نوروز ۱۴۰۳
        (dt.date(2025, 3, 21), (1404, 1, 1)),   # نوروز ۱۴۰۴
        (dt.date(2026, 3, 21), (1405, 1, 1)),   # نوروز ۱۴۰۵
        (dt.date(2025, 3, 20), (1403, 12, 30)), # ۱۴۰۳ کبیسه
        (dt.date(2026, 10, 27), (1405, 8, 5)),  # امروز
    ]
    for g, j in cases:
        got = jalali.gregorian_to_jalali(g.year, g.month, g.day)
        assert got == j, f"{g}: got {got}, want {j}"
        back = jalali.jalali_to_gregorian(*j)
        assert back == (g.year, g.month, g.day), f"{j}: got {back}"


def test_roundtrip_and_jdatetime():
    # رفت‌وبرگشت کامل + تطبیق با jdatetime در بازه وسیع
    d = dt.date(1990, 1, 1)
    step = dt.timedelta(days=7)
    while d < dt.date(2036, 1, 1):
        jy, jm, jd = jalali.gregorian_to_jalali(d.year, d.month, d.day)
        jd2 = jdatetime.date(jy, jm, jd)
        assert jd2.togregorian() == d
        assert jalali.jalali_to_gregorian(jy, jm, jd) == (d.year, d.month, d.day)
        d += step

    # سال کبیسه: ۱۳۹۹ و ۱۴۰۳ کبیسه‌اند، ۱۴۰۴ نیست
    assert jalali.is_jalali_leap(1399) and jalali.is_jalali_leap(1403)
    assert not jalali.is_jalali_leap(1404)
    assert jalali.jalali_month_length(1403, 12) == 30
    assert jalali.jalali_month_length(1404, 12) == 29

    # پارس رشته‌ها: ارقام فارسی، جداکننده متفاوت
    assert jalali.parse_jalali_str("۱۴۰۵/۰۸/۰۵") == (1405, 8, 5)
    assert jalali.parse_jalali_str("1404-2-30") == (1404, 2, 30)
    assert jalali.parse_jalali_str("1404/12/30") is None  # ۱۴۰۴ کبیسه نیست
    assert jalali.parse_jalali_str("1403/12/30") == (1403, 12, 30)
    assert jalali.parse_jalali_str("1405/13/01") is None
    assert jalali.parse_jalali_str("abc") is None
    assert jalali.parse_jalali_str(" ۱۴۰۵ / ۰۸ / ۰۵ ") is None  # فاصله داخلی مجاز نیست


def test_national_code():
    valid = make_valid_national_code("012345678")  # با صفر ابتدایی
    assert valid is not None and len(valid) == 10 and valid.startswith("0")
    assert normalize_national_code(valid) == valid
    # ورودی ۸ رقمی → تکمیل دو صفر و بررسی رقم کنترلیِ نسخه ۱۰ رقمیِ حاصل
    # («23456787» → «0023456787» که رقم کنترلی‌اش درست است)
    assert normalize_national_code("23456787") == "0023456787"
    # ارقام فارسی
    fa = valid[:9].translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")) + valid[9]
    assert normalize_national_code(fa) == valid
    # نامعتبرها
    assert normalize_national_code("12345") is None            # کوتاه
    assert normalize_national_code("12345678901") is None      # بلندتر از ۱۰
    assert normalize_national_code("1111111111") is None       # ارقام تکراری
    assert normalize_national_code("123456789-") is None       # خط تیره
    assert normalize_national_code("1234 56789") is None       # فاصله داخلی
    assert normalize_national_code("0123456780") is None       # رقم کنترلی غلط (درست: ۹)
    assert normalize_national_code("abcd123456") is None


if __name__ == "__main__":
    test_anchors()
    test_roundtrip_and_jdatetime()
    test_national_code()
    print("ALL TESTS PASSED ✓")
