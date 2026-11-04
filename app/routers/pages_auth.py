# -*- coding: utf-8 -*-
"""صفحات احراز هویت: ورود، خروج و تغییر رمز عبور — همه زیر /app."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import PageRedirect
from ..config import APP_PREFIX, APP_TITLE, APP_VERSION, BASE_DIR, ORG_NAME
from ..database import get_db
from ..models import User
from ..utils.activity import log_activity
from ..utils.jalali import today_jalali_str
from ..utils.security import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    hash_password,
    make_session_token,
    verify_password,
)
from ..auth import _load_user
from .pages import _asset_url, _versioned_logo

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
# مهم: صفحات ورود و تغییر رمز قالب مستقل دارند (base.html را extend نمی‌کنند)؛
# بدون asset() با نسخهٔ ?v=، مرورگر CSS قدیمی کش‌شده را نشان می‌داد و لوگو
# نصفه دیده می‌شد حتی بعد از به‌روزرسانی سرور. اندازهٔ لوگو هم به‌صورت
# استایل درون‌خطی داده شده تا با CSS قدیمیِ کش‌شده هم درست نمایش داده شود.
templates.env.globals["asset"] = _asset_url

router = APIRouter(prefix=APP_PREFIX, tags=["auth"])

MIN_PASSWORD_LEN = 6


def _auth_ctx(**extra):
    ctx = {
        "app_title": APP_TITLE,
        "org_name": ORG_NAME,
        "logo_url": _versioned_logo(),
        "today": today_jalali_str(),
        "prefix": APP_PREFIX,
        "app_version": APP_VERSION,
    }
    ctx.update(extra)
    return ctx


def _set_session_cookie(response: RedirectResponse, user: User) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(user.id),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    user = _load_user(request, db)
    if user is not None and user.is_active:
        if user.must_change_password:
            return RedirectResponse(f"{APP_PREFIX}/change-password", status_code=303)
        return RedirectResponse(f"{APP_PREFIX}/", status_code=303)
    return templates.TemplateResponse(request, "login.html", _auth_ctx(page_title="ورود"))


@router.post("/login")
async def login_do(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    username = str(form.get("username") or "").strip().lower()
    password = str(form.get("password") or "")

    user = db.scalars(select(User).where(User.username == username)).first()
    if user is None or not verify_password(password, user.password_hash):
        log_activity(db, request, None, "login_failed", f"نام کاربری: {username}", username_override=username)
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(page_title="ورود", error="نام کاربری یا رمز عبور اشتباه است.", username=username),
            status_code=401,
        )
    if not user.is_active:
        return templates.TemplateResponse(
            request,
            "login.html",
            _auth_ctx(page_title="ورود", error="حساب کاربری شما غیرفعال است. با مدیر سامانه تماس بگیرید.", username=username),
            status_code=403,
        )

    from datetime import datetime, timezone

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    log_activity(db, request, user, "login_success")

    target = f"{APP_PREFIX}/change-password" if user.must_change_password else f"{APP_PREFIX}/"
    response = RedirectResponse(target, status_code=303)
    _set_session_cookie(response, user)
    return response


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    user = _load_user(request, db)
    if user is not None:
        log_activity(db, request, user, "logout")
    response = RedirectResponse(f"{APP_PREFIX}/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


def change_password_page(request: Request, db: Session = Depends(get_db)):
    user = _load_user(request, db)
    if user is None:
        raise PageRedirect(f"{APP_PREFIX}/login")
    return templates.TemplateResponse(
        request,
        "change_password.html",
        _auth_ctx(page_title="تغییر رمز عبور", forced=bool(user.must_change_password), error=None),
    )


async def change_password_do(request: Request, db: Session = Depends(get_db)):
    user = _load_user(request, db)
    if user is None:
        raise PageRedirect(f"{APP_PREFIX}/login")

    form = await request.form()
    current = str(form.get("current_password") or "")
    new1 = str(form.get("new_password") or "")
    new2 = str(form.get("new_password2") or "")

    error = None
    if not verify_password(current, user.password_hash):
        error = "رمز عبور فعلی اشتباه است."
    elif len(new1) < MIN_PASSWORD_LEN:
        error = f"رمز جدید باید حداقل {MIN_PASSWORD_LEN} نویسه باشد."
    elif new1 != new2:
        error = "تکرار رمز جدید با رمز جدید یکسان نیست."
    elif new1 == current:
        error = "رمز جدید نباید با رمز فعلی یکسان باشد."

    if error:
        return templates.TemplateResponse(
            request,
            "change_password.html",
            _auth_ctx(page_title="تغییر رمز عبور", forced=bool(user.must_change_password), error=error),
            status_code=422,
        )

    user.password_hash = hash_password(new1)
    was_forced = bool(user.must_change_password)
    user.must_change_password = False
    db.commit()
    log_activity(db, request, user, "password_changed_forced" if was_forced else "password_changed", "تغییر رمز توسط خود کاربر")

    response = RedirectResponse(f"{APP_PREFIX}/", status_code=303)
    _set_session_cookie(response, user)  # تازه‌سازی سشن پس از تغییر
    return response


# ثبت مسیرها با متدهای مشخص
router.add_api_route("/change-password", change_password_page, methods=["GET"], include_in_schema=False)
router.add_api_route("/change-password", change_password_do, methods=["POST"], include_in_schema=False)
