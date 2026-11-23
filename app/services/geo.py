# -*- coding: utf-8 -*-
"""مهره‌سازی ادغامی استان‌ها و شهرستان‌های رسمی در استارت برنامه (نسخهٔ 1.9.0).

دادهٔ فایل اکسل رسمی سفارش‌دهنده (app/seed_data/locations.py) با دیتابیس
موجود «ادغام» می‌شود، نه جایگزینی:
- استان یا شهرستانی که در دیتابیس هست (حتی اگر در فهرست رسمی نباشد، مثل
  شهرستان‌های دستیِ قبلی) دست‌نخورده می‌ماند و هیچ رکوردی قطع ارتباط نمی‌شود؛
- استان/شهرستان رسمیِ غایب اضافه می‌شود؛
- تطبیق نام با کلید نرمال‌شده (بدون فاصله/نیم‌فاصله، نویسه‌های عربی→فارسی)
  انجام می‌شود تا املاهای نزدیک («بیله‌سوار» / «بيله سوار») ردیف تکراری نسازند.
عملیات idempotent است — در هر استارت فقط موارد واقعاً غایب ساخته می‌شوند.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import County, Province

_CHAR_MAP = str.maketrans({
    "ي": "ی", "ك": "ک", "ى": "ی", "ۀ": "ه", "ة": "ه",
    "أ": "ا", "إ": "ا", "ٱ": "ا",
})


def match_key(s: str) -> str:
    """کلید مقایسهٔ نام استان/شهرستان — مستقل از نویسه‌عربی، فاصله و نیم‌فاصله."""
    s = (s or "").translate(_CHAR_MAP)
    return re.sub(r"[\s\u200c\u200f\u200e]+", "", s)


def ensure_official_locations(db: Session) -> dict:
    """ادغام فهرست رسمی استان/شهرستان با دیتابیس — idempotent و بدون حذف."""
    from ..seed_data.locations import LOCATIONS

    provinces = {match_key(p.name): p for p in db.scalars(select(Province)).all()}
    new_provinces = 0
    new_counties = 0

    for prov_name, county_names in LOCATIONS.items():
        prov = provinces.get(match_key(prov_name))
        if prov is None:
            prov = Province(name=prov_name)
            db.add(prov)
            db.flush()
            provinces[match_key(prov_name)] = prov
            new_provinces += 1
        existing = {match_key(c.name) for c in db.scalars(
            select(County).where(County.province_id == prov.id)
        ).all()}
        for town in county_names:
            if match_key(town) in existing:
                continue
            db.add(County(province_id=prov.id, name=town))
            existing.add(match_key(town))
            new_counties += 1

    if new_provinces or new_counties:
        db.commit()
    return {"provinces_added": new_provinces, "counties_added": new_counties}
