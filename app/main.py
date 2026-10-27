# -*- coding: utf-8 -*-
"""نقطه ورود FastAPI — سامانه فرم نظرسنجی تلفنی."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_PREFIX, APP_TITLE, BASE_DIR
from .database import Base, engine
from .routers import (
    api_dashboard,
    api_export,
    api_locations,
    api_surveys,
    api_template,
    pages,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=APP_TITLE, lifespan=lifespan, docs_url="/docs", openapi_url="/openapi.json")

static_dir = BASE_DIR / "app" / "static"
app.mount("/app/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(pages.router)
app.include_router(api_locations.router, prefix=APP_PREFIX)
app.include_router(api_template.router, prefix=APP_PREFIX)
app.include_router(api_surveys.router, prefix=APP_PREFIX)
app.include_router(api_export.router, prefix=APP_PREFIX)
app.include_router(api_dashboard.router, prefix=APP_PREFIX)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # پیام خطای استاندارد بدون افشای جزئیات سرور (بخش ۱۴ و ۱۵ سند)
    return JSONResponse(
        status_code=500,
        content={"detail": {"message": "خطای غیرمنتظره در سرور رخ داد. لطفاً دوباره تلاش کنید."}},
    )


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}
