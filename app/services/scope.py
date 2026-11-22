# -*- coding: utf-8 -*-
"""دامنهٔ دسترسی رکوردها (نسخهٔ 1.8.0) — سه قید سراسری روی همهٔ گزارش‌ها:

۱) «فقط داده‌های خودش» (دسترسی own_data): کاربر فقط رکوردهایی را می‌بیند که
   خودش ثبت کرده است. رکوردهای قدیمی (created_by = NULL، پیش از این نسخه)
   برای همهٔ کاربران دارای مجوز مشاهده دیده می‌شوند تا دادهٔ موجود حذف نشود.
   مدیر سامانه هرگز مشمول این قید نیست.

۲) «فرم‌های مجاز» (ستون users.allowed_forms): کاربر فقط نوع فرم‌هایی را می‌بیند
   و می‌تواند ثبت کند که مدیر برایش تعیین کرده؛ خالی یعنی همهٔ فرم‌های فعال.
   مدیر سامانه همیشه همهٔ فرم‌ها را دارد.

۳) «محدودیت استانی» (ستون users.province_name — نسخهٔ 1.8.0): کاربرِ عادی که
   برایش استان تعیین شده فقط رکوردهای همان استان را می‌بیند و ثبت می‌کند —
   فرم‌های استان‌های دیگر نه در آرشیو، نه در داشبورد، نه در تحلیل تلفیقی،
   نه در استخراج داده و نه در خروجی اکسل به او برنمی‌گردد. مدیر سامانه و
   کاربر بدون استان، همهٔ استان‌ها را می‌بینند.

این سه قید در یک نقطه متمرکز شده‌اند تا آرشیو، داشبورد، تحلیل تلفیقی،
خروجی اکسل، استخراج داده، مشاهده/ویرایش/حذف تک‌رکورد و چاپ هم‌رفتار باشند.
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..constants import PERM_OWN_ONLY
from ..forms_registry import enabled_forms, form_by_key
from ..models import Province, Survey, User


def sees_only_own(user: User) -> bool:
    """آیا این کاربر فقط رکوردهای خودش را می‌بیند؟ (مدیر مستثنا است)"""
    return (not user.is_admin_level) and user.has_perm(PERM_OWN_ONLY)


def province_scope_id(user: User | None, db: Session) -> int | None:
    """شناسهٔ استانِ محدودیت این کاربر؛ None یعنی بدون محدودیت استانی.

    - مدیر سامانه: همیشه بدون محدودیت
    - کاربر عادی بدون استان (province_name خالی): بدون محدودیت — همهٔ استان‌ها
    - کاربر عادی با استان: شناسهٔ استان هم‌نام در جدول provinces
    - اگر نام استان در جدول استان‌ها پیدا نشود: شناسهٔ ناممکن (‎-1‎) تا هیچ
      رکوردی فاش نشود — مدیر باید نام استان کاربر را اصلاح کند.
    """
    if user is None or user.is_admin_level:
        return None
    name = (user.province_name or "").strip()
    if not name:
        return None
    prov = db.scalars(select(Province).where(Province.name == name)).first()
    return prov.id if prov else -1


def user_province(user: User | None, db: Session) -> Province | None:
    """شیء استانِ محدودیت کاربر — برای منو/فیلترها؛ None یعنی همهٔ استان‌ها."""
    pid = province_scope_id(user, db)
    if pid is None or pid < 0:
        return None
    return db.get(Province, pid)


def allowed_form_keys(user: User, db: Session | None = None) -> list[str] | None:
    """فهرست فرم‌های مجاز کاربر؛ None یعنی همهٔ فرم‌های فعال.

    کلیدهای حذف‌شده از رجیستری نادیده گرفته می‌شوند تا ستون قدیمی خراب نکند.
    """
    if user.is_admin_level:
        return None
    keys = [k for k in user.allowed_form_keys if form_by_key(k)]
    return keys or None


def user_forms(user: User | None, db: Session | None = None) -> list[dict]:
    """فرم‌های فعالِ قابل نمایش برای این کاربر — منو، صفحه‌ها و فیلترها.

    نوع فرم‌ها بین استان‌ها مشترک است؛ محدودیت استانی روی «رکوردهای» هر فرم
    اعمال می‌شود، نه روی خودِ نوع فرم.
    """
    forms = enabled_forms()
    if user is None or user.is_admin_level:
        return forms
    keys = {k.strip() for k in (user.allowed_forms or "").split(",") if k.strip()}
    if not keys:
        return forms
    return [f for f in forms if f["key"] in keys]


def can_view_record(user: User, record: Survey, db: Session) -> bool:
    """آیا کاربر مجاز به دیدن این رکورد است؟ (قید own_data + فرم مجاز + استان)"""
    if user.is_admin_level:
        return True
    if sees_only_own(user):
        if record.created_by is not None and record.created_by != user.id:
            return False
    keys = allowed_form_keys(user)
    if keys is not None:
        fk = record.form_key or "tel"
        if fk not in keys:
            return False
    if db is not None:
        pid = province_scope_id(user, db)
        if pid is not None and (record.province_id or -1) != pid:
            return False
    return True


def apply_record_scope(stmt, user: User, db: Session):
    """اعمال قیدهای own_data + فرم‌های مجاز + محدودیت استانی روی هر کوئری Survey."""
    if user.is_admin_level:
        return stmt
    if sees_only_own(user):
        # رکوردهای قدیمی (created_by = NULL) مشترک می‌مانند
        stmt = stmt.where(or_(Survey.created_by == user.id, Survey.created_by.is_(None)))
    keys = allowed_form_keys(user)
    if keys is not None:
        stmt = stmt.where(Survey.form_key.in_(keys))
    pid = province_scope_id(user, db)
    if pid is not None:
        stmt = stmt.where(Survey.province_id == pid)
    return stmt
