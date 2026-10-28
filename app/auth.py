# -*- coding: utf-8 -*-
"""احراز هویت و سطوح دسترسی — قلب فاز کاربران.

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
from .constants import ROLE_ADMIN, ROLE_OPERATOR
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


def page_staff(request: Request, db: Session = Depends(get_db)) -> User:
    user = page_user(request, db)
    if user.role not in (ROLE_ADMIN, ROLE_OPERATOR):
        raise PageRedirect(f"{APP_PREFIX}/dashboard")
    return user


def page_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = page_user(request, db)
    if user.role != ROLE_ADMIN:
        raise PageRedirect(f"{APP_PREFIX}/dashboard")
    return user


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


def api_staff(request: Request, db: Session = Depends(get_db)) -> User:
    user = api_user(request, db)
    if user.role not in (ROLE_ADMIN, ROLE_OPERATOR):
        raise HTTPException(
            status_code=403,
            detail={"message": "این عملیات فقط برای مدیر و کارشناس مجاز است."},
        )
    return user


def api_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = api_user(request, db)
    if user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=403,
            detail={"message": "این عملیات فقط برای مدیر سامانه مجاز است."},
        )
    return user
