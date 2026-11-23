# -*- coding: utf-8 -*-
"""ثابت‌های سامانه — گزینه‌های امتیازدهی مطابق ترتیب فرم (بخش ۶ سند)."""

# ترتیب ستون‌های امتیازدهی به ترتیب فرم: «خیلی زیاد»، «زیاد»، «متوسط»، «کم»، «خیلی کم»
RATING_OPTIONS: list[tuple[int, str]] = [
    (5, "خیلی زیاد"),
    (4, "زیاد"),
    (3, "متوسط"),
    (2, "کم"),
    (1, "خیلی کم"),
]

RATING_LABELS = [label for _, label in RATING_OPTIONS]
RATING_LABEL_TO_SCORE = {label: score for score, label in RATING_OPTIONS}
RATING_SCORE_TO_LABEL = {score: label for score, label in RATING_OPTIONS}

# برچسب پاسخ خالی در داشبورد — جداگانه گزارش می‌شود و از محاسبه میانگین حذف می‌گردد
NO_ANSWER_LABEL = "بدون پاسخ"

# ---------- سطوح کاربری (دو سطح) ----------
# سطح، بالاترین لایهٔ دسترسی است:
#  - مدیر سامانه: همهٔ بخش‌ها از جمله مدیریت کاربران/الگو/کلیدها/لاگ
#  - کاربر سامانه: فقط بر اساس نقش و سطوح دسترسی که مدیر برایش تعیین می‌کند
LEVEL_ADMIN = "admin"   # مدیر سامانه
LEVEL_USER = "user"     # کاربر سامانه

LEVEL_LABELS: dict[str, str] = {
    LEVEL_ADMIN: "مدیر سامانه",
    LEVEL_USER: "کاربر سامانه",
}
VALID_LEVELS = (LEVEL_ADMIN, LEVEL_USER)

# ---------- نقش‌های کاربران (۶ نقش) ----------
ROLE_ADMIN = "admin"           # مدیر — همه‌چیز
ROLE_OPERATOR = "operator"     # کارشناس نظرسنجی — ثبت، ویرایش، چاپ و خروجی اکسل
ROLE_DATA_ENTRY = "data_entry" # ورود داده — فقط ثبت و ویرایش و چاپ فرم‌ها
ROLE_SUPERVISOR = "supervisor" # ناظر حرفه‌ای — ثبت و ویرایش و چاپ (امضای نظارت)
ROLE_REPORTER = "reporter"     # گزارش‌گیر — مشاهده، چاپ و خروجی اکسل
ROLE_VIEWER = "viewer"         # مشاهده‌گر — فقط خواندنی (داشبورد و آرشیو)

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: "مدیر",
    ROLE_OPERATOR: "کارشناس نظرسنجی",
    ROLE_DATA_ENTRY: "ورود داده",
    ROLE_SUPERVISOR: "ناظر حرفه‌ای",
    ROLE_REPORTER: "گزارش‌گیر",
    ROLE_VIEWER: "مشاهده‌گر",
}

# توضیح کوتاه هر نقش — در فهرست انتخاب نقشِ صفحهٔ مدیریت کاربران نشان داده می‌شود
ROLE_DESCRIPTIONS: dict[str, str] = {
    ROLE_ADMIN: "همهٔ دسترسی‌ها + مدیریت کاربران و الگو",
    ROLE_OPERATOR: "ثبت و ویرایش فرم، چاپ و خروجی اکسل",
    ROLE_DATA_ENTRY: "ثبت و ویرایش فرم و چاپ",
    ROLE_SUPERVISOR: "ثبت و ویرایش فرم و چاپ (نظارت حرفه‌ای)",
    ROLE_REPORTER: "مشاهده، چاپ و خروجی اکسل (ثبت ندارد)",
    ROLE_VIEWER: "فقط مشاهدهٔ داشبورد و آرشیو",
}

VALID_ROLES = tuple(ROLE_LABELS.keys())

# ---------- لایه‌های دسترسی سازمانی (نسخهٔ 1.9.0) ----------
# هر کاربر سامانه (غیرمدیر) در یکی از دو لایهٔ زیر قرار می‌گیرد:
#  - سطح استان: مسئولین استانی (مثل مدیران کلینیک و مسئولین اجرایی)
#  - ادارهٔ استان: واحدهای تابعهٔ استانی
# کدام فرم برای کدام لایه دیده شود در جدول form_access تنظیم می‌شود
# (صفحهٔ «سطح دسترسی فرم‌ها»): برخی فرم‌ها فقط سطح استان و برخی دیگر
# ادارات استان هم می‌بینند. مدیر سامانه هرگز محدود به لایه نیست.
LAYER_PROVINCE = "province"     # سطح استان
LAYER_DEPARTMENT = "department" # ادارهٔ استان

LAYER_LABELS: dict[str, str] = {
    LAYER_PROVINCE: "سطح استان",
    LAYER_DEPARTMENT: "ادارهٔ استان",
}
VALID_LAYERS = (LAYER_PROVINCE, LAYER_DEPARTMENT)

# ---------- سطوح دسترسی (۶ سطح) ----------
# هر کاربر می‌تواند ترکیبی از این دسترسی‌ها را داشته باشد؛ اگر خالی باشد،
# دسترسی‌های پیش‌فرض نقش او اعمال می‌شود. سطح «مدیر سامانه» همیشه همه را دارد
# و از قید «فقط داده‌های خودش» مستثنا است.
PERM_VIEW = "view"         # فقط خواندنی — داشبورد، آرشیو و مشاهدهٔ رکورد
PERM_EDIT = "edit"         # ثبت و ویرایش فرم نظرسنجی
PERM_PRINT = "print"       # چاپ فرم و گرفتن PDF
PERM_EXPORT = "export"     # خروجی اکسل
PERM_DELETE = "delete"     # حذف رکورد
PERM_OWN_ONLY = "own_data" # محدودیت مشاهده: فقط رکوردهایی که خودش ثبت کرده

# ترتیب نمایش در رابط کاربری
PERMISSIONS: list[tuple[str, str]] = [
    (PERM_VIEW, "فقط خواندنی (داشبورد و آرشیو)"),
    (PERM_EDIT, "ثبت و ویرایش فرم"),
    (PERM_PRINT, "چاپ و PDF"),
    (PERM_EXPORT, "خروجی اکسل"),
    (PERM_DELETE, "حذف رکورد"),
    (PERM_OWN_ONLY, "فقط داده‌های خودش را ببیند"),
]
VALID_PERMISSIONS = tuple(key for key, _ in PERMISSIONS)

PERM_LABELS: dict[str, str] = {key: label for key, label in PERMISSIONS}

# پیام خطای ۴۰۳ برای هر دسترسی
PERM_DENY_MESSAGES: dict[str, str] = {
    PERM_VIEW: "این بخش فقط برای مشاهده در دسترس شما نیست.",
    PERM_EDIT: "شما اجازهٔ ثبت یا ویرایش فرم ندارید.",
    PERM_PRINT: "شما اجازهٔ چاپ و دریافت PDF ندارید.",
    PERM_EXPORT: "شما اجازهٔ گرفتن خروجی اکسل ندارید.",
    PERM_DELETE: "شما اجازهٔ حذف رکورد ندارید.",
    PERM_OWN_ONLY: "شما اجازهٔ دیدن رکوردهای دیگر کاربران را ندارید.",
}

# دسترسی‌های پیش‌فرض هر نقش — هنگام انتخاب نقش در فرم کاربر جدید
# به‌صورت خودکار تیک می‌خورد و مدیر می‌تواند آن را تغییر دهد
ROLE_DEFAULT_PERMS: dict[str, tuple[str, ...]] = {
    ROLE_ADMIN: (PERM_VIEW, PERM_EDIT, PERM_PRINT, PERM_EXPORT, PERM_DELETE),
    ROLE_OPERATOR: (PERM_VIEW, PERM_EDIT, PERM_PRINT, PERM_EXPORT),
    ROLE_DATA_ENTRY: (PERM_VIEW, PERM_EDIT, PERM_PRINT),
    ROLE_SUPERVISOR: (PERM_VIEW, PERM_EDIT, PERM_PRINT),
    ROLE_REPORTER: (PERM_VIEW, PERM_PRINT, PERM_EXPORT),
    ROLE_VIEWER: (PERM_VIEW,),
}

ALL_PERMISSIONS = (PERM_VIEW, PERM_EDIT, PERM_PRINT, PERM_EXPORT, PERM_DELETE, PERM_OWN_ONLY)


def parse_permissions(raw: str | None) -> list[str]:
    """تبدیل رشتهٔ ذخیره‌شدهٔ جدول («view,edit,print») به فهرست کلید معتبر."""
    if not raw:
        return []
    keys = [p.strip() for p in str(raw).replace("،", ",").split(",")]
    return [p for p in keys if p in VALID_PERMISSIONS]


def effective_permissions(
    level: str,
    role: str,
    permissions_raw: str | None,
    role_perms: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """دسترسی‌های نهایی کاربر — منطق واحد برای API و رابط کاربری.

    ۱) سطح «مدیر سامانه» یا نقش «مدیر» → همهٔ دسترسی‌ها
    ۲) اگر فهرست دسترسی ذخیره‌شدهٔ کاربر غیرخالی باشد → همان فهرست
    ۳) اگر نقش در جدول نقش‌ها دسترسی پیش‌فرض داشته باشد → همان
    ۴) در غیر این صورت → دسترسی‌های پیش‌فرض نقش‌های سیستمی (ثابت‌های قدیمی)

    role_perms: دسترسی‌های پیش‌فرض نقش از جدول roles (نقش‌های تعریف‌شدهٔ جدید).
    """
    if level == LEVEL_ADMIN or role == ROLE_ADMIN:
        return list(ALL_PERMISSIONS)
    perms = parse_permissions(permissions_raw)
    if perms:
        return [p for p in ALL_PERMISSIONS if p in perms]
    if role_perms:
        return [p for p in ALL_PERMISSIONS if p in role_perms]
    return list(ROLE_DEFAULT_PERMS.get(role, (PERM_VIEW,)))
