# -*- coding: utf-8 -*-
"""نقطه ورود FastAPI — سامانه فرم نظرسنجی تلفنی."""
import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_PREFIX, APP_TITLE, BASE_DIR
from .database import Base, SessionLocal, engine
from .routers import (
    api_dashboard,
    api_export,
    api_keys,
    api_locations,
    api_logs,
    api_surveys,
    api_template,
    api_users,
    api_v1,
    pages,
    pages_auth,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # مهاجرت‌های خودکار سبک: ستون‌های فیلدهای فرم نمونه + سطح کاربری و
    # سطوح دسترسی کاربران — بدون دست‌زدن به داده‌های موجود
    from .database import ensure_schema_updates

    ensure_schema_updates(engine)
    _bootstrap_admin()
    yield


def _bootstrap_admin() -> None:
    """اگر هیچ کاربری نباشد، حساب مدیر اولیه ساخته می‌شود.

    نام کاربری: admin — رمز اولیه: admin123 — کاربر در اولین ورود
    مجبور به تغییر رمز می‌شود (بخش امنیت سند).
    """
    from sqlalchemy import func, select

    from .constants import LEVEL_ADMIN, ROLE_ADMIN
    from .models import User
    from .utils.security import hash_password

    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(User)) or 0
        if count > 0:
            return
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            full_name="مدیر سامانه",
            role=ROLE_ADMIN,
            level=LEVEL_ADMIN,
            is_active=True,
            must_change_password=True,
        )
        db.add(admin)
        db.commit()

        from .models import ActivityLog

        db.add(
            ActivityLog(
                username="system",
                action="system_bootstrap",
                detail="حساب مدیر اولیه (admin) ساخته شد — رمز موقت admin123",
            )
        )
        db.commit()
        logging.getLogger("survey.bootstrap").warning(
            "Bootstrap admin created: username=admin password=admin123 (must change on first login)"
        )


app = FastAPI(title=APP_TITLE, lifespan=lifespan, docs_url="/docs", openapi_url="/openapi.json")

static_dir = BASE_DIR / "app" / "static"
app.mount("/app/static", StaticFiles(directory=str(static_dir)), name="static")


@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    """صفحات HTML هرگز کش نشوند — مرورگر همیشه نسخهٔ تازه را می‌گیرد.

    بدون این، مرورگر می‌تواند HTML قدیمی (بدون ?v= فایل‌های استاتیک) را
    هفته‌ها نشان دهد و کاربر بعد از هر آپدیت ظاهر قدیمی ببیند.
    """
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(pages.router)
app.include_router(pages_auth.router)
app.include_router(api_locations.router, prefix=APP_PREFIX)
app.include_router(api_template.router, prefix=APP_PREFIX)
app.include_router(api_surveys.router, prefix=APP_PREFIX)
app.include_router(api_export.router, prefix=APP_PREFIX)
app.include_router(api_dashboard.router, prefix=APP_PREFIX)
app.include_router(api_users.router, prefix=APP_PREFIX)
app.include_router(api_logs.router, prefix=APP_PREFIX)
app.include_router(api_keys.router, prefix=APP_PREFIX)
app.include_router(api_v1.router, prefix=APP_PREFIX)


from .auth import PageRedirect  # noqa: E402 — بعد از ساخت app لازم نیست بالا باشد


@app.exception_handler(PageRedirect)
async def page_redirect_handler(request: Request, exc: PageRedirect):
    """برای صفحات HTML هدایت تمیز انجام می‌دهد (به‌جای خطای JSON)."""
    return RedirectResponse(exc.url, status_code=303)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # ثبت کامل ردپای خطا در لاگ سرور (logs/server.log) برای امکان عیب‌یابی
    logging.getLogger("survey.error").error(
        "Unhandled error on %s %s\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    # پیام خطای استاندارد بدون افشای جزئیات سرور (بخش ۱۴ و ۱۵ سند)
    return JSONResponse(
        status_code=500,
        content={"detail": {"message": "خطای غیرمنتظره در سرور رخ داد. لطفاً دوباره تلاش کنید."}},
    )


@app.get("/healthz", include_in_schema=False)
def healthz():
    from .config import APP_VERSION
    return {"status": "ok", "version": APP_VERSION}
