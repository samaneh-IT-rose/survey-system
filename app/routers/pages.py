# -*- coding: utf-8 -*-
"""صفحات رابط کاربری (Jinja2) — همه زیر پیشوند /app و با کنترل دسترسی."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import page_admin, page_require_perm
from ..config import APP_PREFIX, APP_TITLE, BASE_DIR, LOGO_URL, ORG_NAME
from ..constants import PERM_EDIT, PERM_PRINT, PERM_VIEW
from ..database import get_db
from ..forms_registry import enabled_forms
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


def _versioned_logo() -> str:
    """نشانی لوگو با پارامتر نسخه — اگر لوگو عوض شود مرورگر نسخهٔ جدید را می‌گیرد."""
    url = LOGO_URL
    if url.startswith(f"{APP_PREFIX}/static/"):
        url = _asset_url(url[len(f"{APP_PREFIX}/"):])
    return url


templates.env.globals["asset"] = _asset_url

router = APIRouter(prefix=APP_PREFIX, tags=["pages"])


def _ctx(user: User | None = None, **extra):
    from ..services.scope import user_forms

    ctx = {
        "app_title": APP_TITLE,
        "org_name": ORG_NAME,
        "logo_url": _versioned_logo(),
        "today": today_jalali_str(),
        "prefix": APP_PREFIX,
        "asset": _asset_url,
        "user": user,
        # منوی «فرم‌های نظرسنجی» — فقط فرم‌هایی که این کاربر اجازهٔ دیدنشان را دارد
        "forms": user_forms(user),
    }
    ctx.update(extra)
    return ctx


def _year_range() -> list[int]:
    jy_now = int(today_jalali_str()[:4])
    return list(range(jy_now - 10, jy_now + 3))


@router.get("/", response_class=HTMLResponse)
def form_root(request: Request, user: User = Depends(page_require_perm(PERM_EDIT))):
    """مسیر قدیمی فرم — پرت به اولین فرم فعال (منوی «فرم‌های نظرسنجی»)."""
    from ..forms_registry import DEFAULT_FORM_KEY

    return RedirectResponse(url=f"{APP_PREFIX}/form/{DEFAULT_FORM_KEY}", status_code=307)


@router.get("/form/{form_key}", response_class=HTMLResponse)
def form_page(form_key: str, request: Request, user: User = Depends(page_require_perm(PERM_EDIT)), db: Session = Depends(get_db)):
    """صفحهٔ ثبت هر فرم — سؤال‌ها و وضعیت‌های تماس همان فرم."""
    from ..forms_registry import form_by_key
    from ..models import ContactOption, Question
    from ..services.form_template import contacts_for_form, questions_for_form

    form = form_by_key(form_key)
    if form is None:
        raise HTTPException(404, detail="فرم نظرسنجی یافت نشد.")
    # اگر مدیر برای کاربر «فرم‌های مجاز» تعیین کرده، این فرم برایش باز نمی‌شود
    from ..services.scope import allowed_form_keys

    allowed = allowed_form_keys(user)
    if allowed is not None and form["key"] not in allowed:
        raise HTTPException(403, detail="به این نوع فرم دسترسی ندارید.")

    questions = questions_for_form(db, form["key"])
    contacts = contacts_for_form(db, form["key"])
    return templates.TemplateResponse(
        request,
        "form.html",
        _ctx(
            user,
            page_title=form["title"],
            form=form,
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
def records_page(request: Request, user: User = Depends(page_require_perm(PERM_VIEW))):
    return templates.TemplateResponse(request, "records.html", _ctx(user, page_title="آرشیو فرم‌ها"))


@router.get("/extract", response_class=HTMLResponse)
def extract_page(request: Request, user: User = Depends(page_require_perm(PERM_VIEW)), db: Session = Depends(get_db)):
    """استخراج آزاد داده از تمام فرم‌ها — انتخاب فرم و هر ستون دلخواه (نسخهٔ 1.7.0)."""
    from ..services.extract import BASE_FIELDS
    from ..services.form_template import questions_for_form
    from ..services.scope import user_forms

    forms = user_forms(user)
    # سؤال‌های هر فرم برای انتخاب ستون — فقط فرم‌های مجاز این کاربر
    form_questions = {}
    for f in forms:
        qs = questions_for_form(db, f["key"])
        form_questions[f["key"]] = [{"id": q.id, "text": q.text} for q in qs]
    return templates.TemplateResponse(
        request,
        "extract.html",
        _ctx(
            user,
            page_title="استخراج داده از فرم‌ها",
            base_fields=[{"key": k, "label": l} for k, l in BASE_FIELDS],
            form_questions=form_questions,
        ),
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, user: User = Depends(page_require_perm(PERM_VIEW))):
    return templates.TemplateResponse(request, "dashboard.html", _ctx(user, page_title="داشبورد آماری"))


@router.get("/template", response_class=HTMLResponse)
def template_page(request: Request, user: User = Depends(page_admin)):
    return templates.TemplateResponse(request, "template_admin.html", _ctx(user, page_title="مدیریت الگوی فرم"))


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request, user: User = Depends(page_admin), db: Session = Depends(get_db)):
    from ..constants import LEVEL_LABELS, PERMISSIONS
    from ..forms_registry import enabled_forms
    from ..services.roles import list_roles, serialize_role

    return templates.TemplateResponse(
        request,
        "users.html",
        _ctx(
            user,
            page_title="مدیریت کاربران",
            levels=[{"value": lv, "label": LEVEL_LABELS[lv]} for lv in ("admin", "user")],
            # نقش‌ها از جدول roles — شامل نقش‌های سفارشی هم می‌شود
            roles=[serialize_role(db, r) for r in list_roles(db)],
            permissions=[{"value": key, "label": label} for key, label in PERMISSIONS],
            forms=enabled_forms(),  # برای گزینه‌های «فرم‌های مجاز» کاربر
        ),
    )


@router.get("/roles", response_class=HTMLResponse)
def roles_page(request: Request, user: User = Depends(page_admin), db: Session = Depends(get_db)):
    from ..constants import LEVEL_LABELS, PERMISSIONS
    from ..services.roles import list_roles, serialize_role

    return templates.TemplateResponse(
        request,
        "roles.html",
        _ctx(
            user,
            page_title="مدیریت نقش‌ها",
            levels=[{"value": lv, "label": LEVEL_LABELS[lv]} for lv in ("admin", "user")],
            permissions=[{"value": key, "label": label} for key, label in PERMISSIONS],
            roles=[serialize_role(db, r) for r in list_roles(db)],
        ),
    )


@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request, user: User = Depends(page_admin)):
    return templates.TemplateResponse(request, "logs.html", _ctx(user, page_title="لاگ فعالیت‌ها"))


@router.get("/api-keys", response_class=HTMLResponse)
def api_keys_page(request: Request, user: User = Depends(page_admin)):
    return templates.TemplateResponse(request, "api_keys.html", _ctx(user, page_title="کلیدهای وب‌سرویس"))


@router.get("/print/{survey_id}", response_class=HTMLResponse)
def print_page(survey_id: int, request: Request, user: User = Depends(page_require_perm(PERM_PRINT)), db: Session = Depends(get_db)):
    from ..forms_registry import DEFAULT_FORM_KEY, form_by_key
    from ..models import Survey
    from ..services.sheet import build_sheet_context

    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(404, detail="رکورد یافت نشد.")
    from ..services.scope import can_view_record

    if not can_view_record(user, s):
        raise HTTPException(403, detail="این رکورد در محدودهٔ دسترسی شما نیست.")
    form_key = s.form_key or DEFAULT_FORM_KEY
    form = form_by_key(form_key)
    # هر فرم قالب چاپ خودش را دارد (عین فایل نمونهٔ همان فرم)
    template_name = form["sheet_template"] if form else "sheet.html"
    ctx = _ctx(user, **build_sheet_context(db, s, interactive=True))
    return templates.TemplateResponse(request, template_name, ctx)
