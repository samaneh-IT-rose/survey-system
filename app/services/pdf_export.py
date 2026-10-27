# -*- coding: utf-8 -*-
"""تولید PDF یک‌صفحه‌ای A4 با Playwright/Chromium (بخش ۹ سند).

- PDF از «نمای چاپ تأییدشده» همان رکورد تولید می‌شود تا خروجی PDF و چاپ
  دقیقاً یکسان باشند.
- ابعاد A4، بدون سربرگ/پابرگ مرورگر، با بارگذاری کامل لوگو و فونت‌ها.
"""
from __future__ import annotations

import asyncio

from ..config import SELF_BASE_URL

_pdf_semaphore = asyncio.Semaphore(2)  # جلوگیری از بار همزمان زیاد روی Chromium


def _render_sync(url: str) -> bytes:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
        try:
            page = browser.new_page()
            page.set_default_timeout(30000)
            # بارگذاری کامل منابع (لوگو، فونت‌ها) پیش از تولید PDF
            page.goto(url, wait_until="networkidle")
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


async def render_pdf_for_record(survey_id: int) -> bytes:
    """رندر نمای چاپ رکورد و تبدیل به PDF."""
    url = f"{SELF_BASE_URL}/app/print/{survey_id}"
    async with _pdf_semaphore:
        return await asyncio.to_thread(_render_sync, url)
