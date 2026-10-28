# -*- coding: utf-8 -*-
"""صفحات رابط کاربری (Jinja2) — همه زیر پیشوند /app و با کنترل دسترسی."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import page_admin, page_staff, page_user
from ..config import APP_PREFIX, APP_TITLE, BASE_DIR, LOGO_URL, ORG_NAME
from ..database import get_db
from ..models import Survey, User
from ..utils.jalali import gregorian_to_jalali, is_jalali_leap, today_jalali_str

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def _asset_url(path: str) -> str:
    """نشانی فایل استاتیک با نسخهٔ مبتنی بر زمان تغییر فایل.

    بدون این پارامتر، مرورگر پس از هر به‌روزرسانی CSS/JS همچنان نسخهٔ قدیمی
    کش‌شده را نشان می‌دهد (مثل مشکل بریده‌شدن کادر سال تاریخ).
    """
    f = BASE_DIR / "app" / path
    try:
        v = int(f.stat().st_mtime)
    except OSError:
        v = 0
    return f"{APP_PREFIX}/{path}?v={v}"


templates.env.globals["asset"] = _asset_url

router = APIRouter(prefix=APP_PREFIX, tags=["pages"])


def _ctx(user: User | None = None, **extra):
    ctx = {
        "app_title": APP_TITLE,
        "org_name": ORG_NAME,
        "logo_url": LOGO_URL,
        "today": today_jalali_str(),
        "prefix": APP_PREFIX,
        "asset": _asset_url,
        "user": user,
    }
    ctx.update(extra)
    return ctx


def _year_range() -> list[int]:
    jy_now = int(today_jalali_str()[:4])
    return list(range(jy_now - 10, jy_now + 3))


@router.get("/", response_class=HTMLResponse)
def form_page(request: Request, user: User = Depends(page_staff), db: Session = Depends(get_db)):
    from ..models import ContactOption, Question

    questions = db.scalars(
        select(Question).where(Question.is_active.is_(True)).order_by(Question.display_order, Question.id)
    ).all()
    contacts = db.scalars(
        select(ContactOption).where(ContactOption.is_active.is_(True)).order_by(ContactOption.display_order, ContactOption.id)
    ).all()
    return templates.TemplateResponse(
        request,
        "form.html",
        _ctx(
            user,
            page_title="ثبت فرم نظرسنجی",
            questions=[{"id": q.id, "text": q.text} for q in questions],
            contact_options=[
                {"id": c.id, "text": c.text, "requires_answers": c.requires_answers}
                for c in contacts
            ],
            years=_year_range(),
            leap_years=[y for y in _year_range() if is_jalali_leap(y)],
        ),
    )


@router.get("/records", response_class=HTMLResponse)
def records_page(request: Request, user: User = Depends(page_user)):
    return templates.TemplateResponse(request, "records.html", _ctx(user, page_title="آرشیو فرم‌ها"))


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, user: User = Depends(page_user)):
    return templates.TemplateResponse(request, "dashboard.html", _ctx(user, page_title="داشبورد آماری"))


@router.get("/template", response_class=HTMLResponse)
def template_page(request: Request, user: User = Depends(page_admin)):
    return templates.TemplateResponse(request, "template_admin.html", _ctx(user, page_title="مدیریت الگوی فرم"))


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request, user: User = Depends(page_admin)):
    return templates.TemplateResponse(request, "users.html", _ctx(user, page_title="مدیریت کاربران"))


@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request, user: User = Depends(page_admin)):
    return templates.TemplateResponse(request, "logs.html", _ctx(user, page_title="لاگ فعالیت‌ها"))


@router.get("/api-keys", response_class=HTMLResponse)
def api_keys_page(request: Request, user: User = Depends(page_admin)):
    return templates.TemplateResponse(request, "api_keys.html", _ctx(user, page_title="کلیدهای وب‌سرویس"))


@router.get("/print/{survey_id}", response_class=HTMLResponse)
def print_page(survey_id: int, request: Request, user: User = Depends(page_user), db: Session = Depends(get_db)):
    from ..models import Survey
    from ..services.sheet import build_sheet_context

    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(404, detail="رکورد یافت نشد.")
    ctx = _ctx(user, **build_sheet_context(db, s, interactive=True))
    return templates.TemplateResponse(request, "sheet.html", ctx)
