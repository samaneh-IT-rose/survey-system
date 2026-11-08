# -*- coding: utf-8 -*-
"""احراز هویت و سطوح دسترسی — قلب فاز کاربران.

لایه‌های کنترل دسترسی (از بالا به پایین):
۱) ورود به سامانه (سشن کوکی فعال) — همهٔ گاردها
۲) سطح کاربری: «مدیر سامانه» همه‌چیز؛ «کاربر سامانه» بر اساس نقش/دسترسی
۳) سطوح دسترسی: فقط خواندنی (view)، ثبت و ویرایش (edit)، چاپ (print)،
   خروجی اکسل (export)، حذف رکورد (delete)

دو گونه گارد داریم:
- page_*  : برای صفحات HTML — به‌جای خطا، به login/تغییر رمز هدایت می‌کند
- api_*   : برای APIها — خطای 401/403 JSON برمی‌گرداند

طراحی SSO-پسند: همهٔ گاردها فقط به جدول users اتکا دارند؛ در آینده یک
کاربر SSO کافی است در همین جدول ثبت شود (auth_source='sso').
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import APP_PREFIX
from .constants import PERM_DENY_MESSAGES, PERM_EDIT, PERM_DELETE, PERM_EXPORT, PERM_PRINT, PERM_VIEW
from .database import get_db
from .models import User
from .utils.security import SESSION_COOKIE, read_session_token


class PageRedirect(Exception):
    """برای صفحات: به‌جای JSON خطا، مرورگر به آدرس دیگری هدایت می‌شود.

    handler آن در main.py ثبت شده است.
    """

    def __init__(self, url: str):
        self.url = url
        super().__init__(url)


def _load_user(request: Request, db: Session) -> User | None:
    uid = read_session_token(request.cookies.get(SESSION_COOKIE))
    if uid is None:
        return None
    user = db.get(User, uid)
    if user is None or not user.is_active:
        return None
    return user


def _force_change_check(user: User, request: Request) -> None:
    """کاربری که باید رمزش را عوض کند، فقط اجازهٔ تغییر رمز و خروج دارد."""
    path = request.url.path
    allowed = (
        f"{APP_PREFIX}/change-password",
        f"{APP_PREFIX}/logout",
    )
    if user.must_change_password and not path.startswith(allowed):
        raise PageRedirect(f"{APP_PREFIX}/change-password")


# ---------- صفحات ----------

def page_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = _load_user(request, db)
    if user is None:
        raise PageRedirect(f"{APP_PREFIX}/login")
    _force_change_check(user, request)
    return user


def _page_redirect_for_perm(perm: str) -> str:
    """کاربرِ بدون دسترسی به جای خطا به داشبورد (خانهٔ امن خودش) هدایت می‌شود."""
    return f"{APP_PREFIX}/dashboard"


def page_require_perm(perm: str):
    """گارد صفحه بر اساس سطوح دسترسی — مدیر سامانه همیشه مجاز است."""

    def dep(request: Request, db: Session = Depends(get_db)) -> User:
        user = page_user(request, db)
        if not user.has_perm(perm):
            raise PageRedirect(_page_redirect_for_perm(perm))
        return user

    return dep


# ---------- APIها ----------

def api_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = _load_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"message": "ابتدا وارد سامانه شوید.", "login": True},
        )
    if user.must_change_password:
        raise HTTPException(
            status_code=403,
            detail={"message": "ابتدا رمز عبور خود را تغییر دهید.", "change_password": True},
        )
    return user


def api_require_perm(perm: str):
    """گارد API بر اساس سطوح دسترسی — مدیر سامانه همیشه مجاز است."""

    def dep(request: Request, db: Session = Depends(get_db)) -> User:
        user = api_user(request, db)
        if not user.has_perm(perm):
            raise HTTPException(
                status_code=403,
                detail={"message": PERM_DENY_MESSAGES.get(perm, "شما به این عملیات دسترسی ندارید.")},
            )
        return user

    return dep


# ---------- گاردهای سازگار با نسخه‌های قبل (هنوز جایی استفاده می‌شوند) ----------

def page_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """صفحات مدیریتی — فقط سطح «مدیر سامانه»."""
    user = page_user(request, db)
    if not user.is_admin_level:
        raise PageRedirect(_page_redirect_for_perm("admin"))
    return user


def page_staff(request: Request, db: Session = Depends(get_db)) -> User:
    """سازگاری با نسخهٔ قبل: کاربری که اجازهٔ ثبت/ویرایش فرم دارد."""
    user = page_user(request, db)
    if not user.has_perm(PERM_EDIT):
        raise PageRedirect(_page_redirect_for_perm(PERM_EDIT))
    return user


def api_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """APIهای مدیریتی — فقط سطح «مدیر سامانه»."""
    user = api_user(request, db)
    if not user.is_admin_level:
        raise HTTPException(
            status_code=403,
            detail={"message": "این عملیات فقط برای مدیر سامانه مجاز است."},
        )
    return user


def api_staff(request: Request, db: Session = Depends(get_db)) -> User:
    """سازگاری با نسخهٔ قبل: کاربری که اجازهٔ ثبت/ویرایش فرم دارد."""
    user = api_user(request, db)
    if not user.has_perm(PERM_EDIT):
        raise HTTPException(
            status_code=403,
            detail={"message": PERM_DENY_MESSAGES[PERM_EDIT]},
        )
    return user


# برای خوانایی کد در روترها
perm_view = api_require_perm(PERM_VIEW)
perm_edit = api_require_perm(PERM_EDIT)
perm_print = api_require_perm(PERM_PRINT)
perm_export = api_require_perm(PERM_EXPORT)
perm_delete = api_require_perm(PERM_DELETE)
