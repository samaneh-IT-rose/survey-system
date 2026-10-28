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

# ---------- نقش‌های کاربران ----------
ROLE_ADMIN = "admin"        # همه‌چیز + مدیریت کاربران/الگو/کلیدها/لاگ
ROLE_OPERATOR = "operator"  # ثبت و ویرایش فرم‌ها + آرشیو و داشبورد + خروجی اکسل
ROLE_VIEWER = "viewer"      # فقط مشاهده داشبورد و آرشیو

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: "مدیر",
    ROLE_OPERATOR: "کارشناس",
    ROLE_VIEWER: "مشاهده‌گر",
}
