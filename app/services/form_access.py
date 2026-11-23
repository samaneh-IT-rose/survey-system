# -*- coding: utf-8 -*-
"""قواعد دیده‌شدن فرم‌ها در دو لایهٔ سازمانی — نسخهٔ 1.9.0.

لایهٔ «سطح استان» و لایهٔ «ادارهٔ استان»: مدیر سامانه در صفحهٔ
«سطح دسترسی فرم‌ها» تعیین می‌کند برای برخی فرم‌ها فقط سطح استان ببیند
و برای برخی دیگر ادارات استان هم. ردیف هر فرم در جدول form_access
نگه‌داری می‌شود و در استارت برای فرم‌های فاقد ردیف، پیش‌فرض ساخته می‌شود
(هر دو True — تا رفتار کاربران موجود پس از به‌روزرسانی تغییر نکند).

مدیر سامانه هرگز محدود به لایه نیست؛ اعمال قواعد در app/services/scope.py
متمرکز شده تا منو، صفحهٔ ثبت، آرشیو، داشبورد، تحلیل تلفیقی، استخراج داده
و خروجی اکسل هم‌رفتار بمانند.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import LAYER_DEPARTMENT, LAYER_PROVINCE
from ..forms_registry import FORM_KEYS, all_forms
from ..models import FormAccess


def ensure_form_access_rules(db: Session) -> int:
    """ساخت ردیف قاعدهٔ پیش‌فرض برای هر فرم رجیستری — idempotent."""
    existing = {r.form_key for r in db.scalars(select(FormAccess)).all()}
    created = 0
    for key in FORM_KEYS:
        if key in existing:
            continue
        db.add(FormAccess(form_key=key, visible_to_province=True, visible_to_department=True))
        created += 1
    if created:
        db.commit()
    return created


def layer_rules(db: Session) -> dict[str, tuple[bool, bool]]:
    """نقشهٔ form_key → (دیده‌شدن در سطح استان، دیده‌شدن در ادارهٔ استان).

    فرم بدون ردیف: پیش‌فرض دیده‌شدن در هر دو لایه (رفتار پیش از این نسخه).
    """
    rows = db.scalars(select(FormAccess)).all()
    return {r.form_key: (bool(r.visible_to_province), bool(r.visible_to_department)) for r in rows}


def layer_allows(rules: dict[str, tuple[bool, bool]], form_key: str, layer: str) -> bool:
    """آیا لایهٔ سازمانی این فرم را می‌بیند؟"""
    rule = rules.get(form_key)
    if rule is None:
        return True
    return rule[1] if layer == LAYER_DEPARTMENT else rule[0]


def serialize_rules(db: Session) -> list[dict]:
    """قواعد همهٔ فرم‌ها (حتی غیرفعال) برای صفحهٔ مدیریت."""
    rules = layer_rules(db)
    out: list[dict] = []
    for f in all_forms():
        vp, vd = rules.get(f["key"], (True, True))
        out.append(
            {
                "form_key": f["key"],
                "title": f["title"],
                "short_title": f["short_title"],
                "enabled": bool(f.get("enabled")),
                "visible_to_province": vp,
                "visible_to_department": vd,
            }
        )
    return out


def save_rules(db: Session, items: list[dict]) -> list[str]:
    """ذخیرهٔ قواعد ارسالی مدیر — خروجی: فهرست فرم‌های تغییرکرده.

    فرم ناشناخته یا مقدار غیربولی خطا می‌دهد تا تنظیم خراب ذخیره نشود.
    """
    from ..forms_registry import form_by_key

    rows = {r.form_key: r for r in db.scalars(select(FormAccess)).all()}
    changed: list[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            raise ValueError("قاعدهٔ فرم نامعتبر است.")
        key = str(item.get("form_key") or "").strip()
        if form_by_key(key) is None:
            raise ValueError(f"فرم «{key}» معتبر نیست.")
        vp = item.get("visible_to_province")
        vd = item.get("visible_to_department")
        if not isinstance(vp, bool) or not isinstance(vd, bool):
            raise ValueError(f"مقادیر قاعدهٔ فرم «{key}» باید درست/غلط باشد.")
        row = rows.get(key)
        if row is None:
            row = FormAccess(form_key=key)
            db.add(row)
        if row.visible_to_province != vp or row.visible_to_department != vd:
            row.visible_to_province = vp
            row.visible_to_department = vd
            changed.append(key)
    if changed:
        db.commit()
    return changed
