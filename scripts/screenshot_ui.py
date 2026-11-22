# -*- coding: utf-8 -*-
"""اسکرین‌شات صفحات کاربران/استخراج برای بررسی بصری (سرور تست روی 3010)."""
import asyncio
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:3010/app"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # ورود مدیر
        page.goto(BASE + "/login")
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", "admin123")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        if "change-password" in page.url:
            page.fill("input[name='current_password']", "admin123")
            page.fill("input[name='new_password']", "Adm1n#2026")
            page.fill("input[name='new_password2']", "Adm1n#2026")
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle")

        # صفحهٔ کاربران + باز کردن مودال ورود اکسل
        page.goto(BASE + "/users")
        page.wait_for_load_state("networkidle")
        page.click("#btnImportUsers")
        page.wait_for_timeout(400)
        page.screenshot(path="/tmp/render/users_import_modal.png", full_page=False)
        page.keyboard.press("Escape")
        page.click("#importCancel")
        # مودال کاربر جدید
        page.click("#btnNewUser")
        page.wait_for_timeout(300)
        page.screenshot(path="/tmp/render/users_new_modal.png", full_page=False)
        # مودال با فیلدهای جدید بلند است — دکمهٔ انصراف ممکن است بیرون از viewport باشد
        page.evaluate("document.getElementById('userCancel').click()")
        page.wait_for_timeout(200)

        # صفحهٔ استخراج
        page.goto(BASE + "/extract")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(400)
        page.screenshot(path="/tmp/render/extract_page.png", full_page=False)

        browser.close()
    print("screenshots done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
