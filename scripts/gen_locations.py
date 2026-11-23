# -*- coding: utf-8 -*-
"""تولید app/seed_data/locations.py از فایل اکسل رسمی استان‌ها و شهرها.

فایل رسمی (Iran-Cities1.xlsx — شیت DB، ستون‌های State و City) جایگزین
فهرست نمونه می‌شود. نویسه‌های عربی (ي/ك) به فارسی (ی/ک) نرمال می‌شوند و
نام چند استان با فاصلهٔ درست «و» بازنویسی می‌شود تا با نام‌های موجود در
دیتابیس سرور هم‌خوان بماند (جلوگیری از استان تکراری پس از مهره‌سازی).

اجرا:
    python scripts/gen_locations.py "/path/to/Iran-Cities1.xlsx"
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SRC = Path(__file__).resolve().parent.parent / "app" / "seed_data" / "locations.py"

# نویسه‌های عربی رایج در فایل‌های اکسل → فارسی
_CHAR_MAP = str.maketrans({
    "ي": "ی", "ك": "ک", "ى": "ی", "ۀ": "ه", "ة": "ه",
    "أ": "ا", "إ": "ا", "ٱ": "ا", "ؤ": "و", "ﺁ": "آ",
})

# فاصلهٔ درست «و» در نام استان‌های مرکب — مطابق نام‌های موجود در دیتابیس
_PROV_FIX = {
    "چهارمحال وبختیاری": "چهارمحال و بختیاری",
    "سیستان وبلوچستان": "سیستان و بلوچستان",
    "کهگیلویه وبویراحمد": "کهگیلویه و بویراحمد",
}


def norm_name(v) -> str:
    s = re.sub(r"\s+", " ", str(v or "").strip().translate(_CHAR_MAP))
    return _PROV_FIX.get(s, s)


def match_key(s: str) -> str:
    """کلید مقایسهٔ نام‌ها — بدون فاصله/نیم‌فاصله تا املاهای نزدیک یکی شوند."""
    return re.sub(r"[\s\u200c\u200f\u200e]+", "", s)


def main(xlsx_path: str) -> None:
    from openpyxl import load_workbook

    wb = load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb["DB"] if "DB" in wb.sheetnames else wb.worksheets[0]

    loc: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    rows = 0
    for row in ws.iter_rows(values_only=True):
        state, city = row[0], row[1] if len(row) > 1 else None
        prov = norm_name(state)
        town = norm_name(city)
        if not prov or prov in ("State", "*") or not town or town == "*":
            continue
        rows += 1
        bucket = seen.setdefault(prov, set())
        if match_key(town) in bucket:
            continue
        bucket.add(match_key(town))
        loc.setdefault(prov, []).append(town)
    wb.close()

    lines = [
        '# -*- coding: utf-8 -*-',
        '"""فهرست رسمی استان‌ها و شهرستان‌های ایران.',
        '',
        'منبع: فایل اکسل رسمی سفارش‌دهنده (Iran-Cities1.xlsx — شیت DB) که با',
        'دستور scripts/gen_locations.py به این ماژول تبدیل شده است؛ ارقام و',
        'نویسه‌های عربی به فارسی نرمال شده‌اند. مهره‌سازی در استارت برنامه',
        '(app/services/geo.py — ensure_official_locations) ادغامی و بدون حذف',
        'دادهٔ موجود انجام می‌شود.',
        '"""',
        '',
        'LOCATIONS: dict[str, list[str]] = {',
    ]
    for prov, towns in loc.items():
        towns_str = ", ".join(f'"{t}"' for t in towns)
        lines.append(f'    "{prov}": [{towns_str}],')
    lines.append("}")
    lines.append("")
    SRC.write_text("\n".join(lines), encoding="utf-8")

    total_c = sum(len(v) for v in loc.values())
    print(f"OK — {len(loc)} استان / {total_c} شهرستان از {rows} ردیف اکسل نوشته شد در {SRC}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/home/z/my-project/upload/Iran-Cities1.xlsx")
