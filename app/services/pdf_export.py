# -*- coding: utf-8 -*-
"""تولید PDF یک‌صفحه‌ای A4 با Playwright/Chromium (بخش ۹ سند).

- PDF از «نمای چاپ تأییدشده» همان رکورد تولید می‌شود تا خروجی PDF و چاپ
  دقیقاً یکسان باشند.
- ابعاد A4، بدون سربرگ/پابرگ مرورگر، با بارگذاری کامل لوگو و فونت‌ها.
- خطاهای رایج (نبودن Chromium، نصب‌شدن مرورگر در پروفایل کاربری اشتباه و …)
  به‌جای «خطای غیرمنتظره»، پیام فارسیِ دقیق همراه با راه‌حل می‌دهند.
"""
from __future__ import annotations

import asyncio
import logging
import os
import traceback
from pathlib import Path

from fastapi import HTTPException

from ..config import SELF_BASE_URL
from ..utils.security import SESSION_COOKIE

logger = logging.getLogger("survey.pdf")

_pdf_semaphore = asyncio.Semaphore(2)  # جلوگیری از بار همزمان زیاد روی Chromium

# محل مرورگرهای Playwright — باید با حسابی که سرویس با آن اجرا می‌شود یکی باشد
# (روی ویندوز سرویس با SYSTEM اجرا می‌شود، پس مسیر باید سراسری باشد نه پروفایل کاربر)
_DEFAULT_BROWSERS_DIR = (
    str(Path.home() / "AppData" / "Local" / "ms-playwright")
    if os.name == "nt"
    else str(Path.home() / ".cache" / "ms-playwright")
)
_BROWSERS_DIR = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or _DEFAULT_BROWSERS_DIR)

_MSG_CHROMIUM_MISSING = (
    "ساخت PDF ممکن است چون مرورگر Chromium روی سرور پیدا نشد. "
    "در سرور (Remote Desktop) پوشهٔ C:\\survey-system را باز کنید و فایل "
    "deploy\\fix-pdf-windows.ps1 را با PowerShell (Run as Administrator) اجرا کنید؛ "
    "اسکریپت Chromium را در مسیر سراسری نصب و سرویس را ری‌استارت می‌کند."
)
_MSG_RENDER_FAILED = (
    "خطا در ساخت PDF. جزئیات کامل خطا در فایل C:\\survey-system\\logs\\server.log ثبت شد. "
    "اگر مشکل ادامه داشت، فایل deploy\\fix-pdf-windows.ps1 را با PowerShell (Run as Administrator) اجرا کنید."
)
_MSG_PW_NOT_INSTALLED = (
    "کتابخانهٔ Playwright روی سرور نصب نیست. در پوشهٔ C:\\survey-system دستور "
    "venv\\Scripts\\python.exe -m pip install -r requirements.txt را اجرا کنید."
)


def _find_chromium_exe() -> Path | None:
    """مسیر chrome.exe نصب‌شده را (در هر نسخهٔ Playwright) پیدا می‌کند."""
    if not _BROWSERS_DIR.exists():
        return None
    for pattern in ("chromium-*/chrome-win*/chrome.exe", "chromium-*/chrome-linux*/chrome"):
        hits = sorted(_BROWSERS_DIR.glob(pattern))
        if hits:
            return hits[0]
    return None


def _render_sync(url: str, session_cookie: str | None = None) -> bytes:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
        try:
            context = browser.new_context()
            if session_cookie:
                # انتقال سشن کاربر به مرورگر تا صفحهٔ چاپِ محافظت‌شده باز شود
                context.add_cookies(
                    [
                        {
                            "name": SESSION_COOKIE,
                            "value": session_cookie,
                            "url": url,
                        }
                    ]
                )
            page = context.new_page()
            page.set_default_timeout(30000)
            # بارگذاری کامل منابع (لوگو، فونت‌ها) پیش از تولید PDF؛
            # اگر networkidle به‌خاطر منبع کند شکست خورد، با load ادامه می‌دهیم
            try:
                page.goto(url, wait_until="networkidle")
            except Exception:
                page.goto(url, wait_until="load")
            page.evaluate("() => document.fonts.ready.then(() => true)")
            page.wait_for_timeout(200)
            pdf = page.pdf(
                format="A4",
                print_background=True,
                display_header_footer=False,
                prefer_css_page_size=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
        finally:
            browser.close()
    return pdf


async def render_pdf_for_record(survey_id: int, session_cookie: str | None = None) -> bytes:
    """رندر نمای چاپ رکورد و تبدیل به PDF — با پیام خطای دقیق و قابل‌فهم."""
    url = f"{SELF_BASE_URL}/app/print/{survey_id}"

    # ۱) پکیج playwright اصلاً نصب است؟
    try:
        import playwright.sync_api  # noqa: F401
    except Exception:
        logger.error("Playwright package is not installed in this environment.")
        raise HTTPException(503, detail={"message": _MSG_PW_NOT_INSTALLED})

    # ۲) خودِ مرورگر Chromium وجود دارد؟ (شایع‌ترین علت خطای PDF روی ویندوز)
    exe = _find_chromium_exe()
    if exe is None:
        logger.error(
            "Chromium not found. PLAYWRIGHT_BROWSERS_PATH=%s (exists=%s). "
            "Run deploy/fix-pdf-windows.ps1 on the server.",
            _BROWSERS_DIR,
            _BROWSERS_DIR.exists(),
        )
        raise HTTPException(503, detail={"message": _MSG_CHROMIUM_MISSING})
    logger.info("PDF render for survey %s using chromium at %s", survey_id, exe)

    # ۳) رندر واقعی
    async with _pdf_semaphore:
        try:
            return await asyncio.to_thread(_render_sync, url, session_cookie)
        except HTTPException:
            raise
        except ImportError:
            logger.error("Playwright import failed inside worker thread.\n%s", traceback.format_exc())
            raise HTTPException(503, detail={"message": _MSG_PW_NOT_INSTALLED})
        except Exception:
            logger.error("PDF render failed for survey %s\n%s", survey_id, traceback.format_exc())
            raise HTTPException(500, detail={"message": _MSG_RENDER_FAILED})
