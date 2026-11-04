#!/bin/bash
# تست بصری: صفحهٔ چاپ (sheet) و صفحهٔ ورود — رندر با Playwright
set -u
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
mkdir -p logs
PY=/home/z/.venv/bin/python3
[ -x "$PY" ] || PY=$(command -v python3)
export SURVEY_DATABASE_URL="sqlite:////$APP_DIR/data/test_print.db"
export SURVEY_SELF_URL="http://127.0.0.1:3010"
export SURVEY_FORM_CODE="RZ-1405-07"
LOG="$APP_DIR/logs/test-server.log"

rm -f data/test_print.db
"$PY" -c "
from app.database import Base, engine
import app.models  # noqa
Base.metadata.create_all(engine)"
"$PY" scripts/seed.py --demo 3 | tail -1

"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 3010 --log-level warning >> "$LOG" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3010/app/login || true)
  [ "$code" = "200" ] && break
  sleep 0.5
done
echo "server ready: $code"

# ورود مدیر + تغییر رمز اجباری
C=/tmp/print_cookies.txt; rm -f "$C"
LOC=$(curl -s -c "$C" -o /dev/null -w "%{redirect_url}" -X POST "http://127.0.0.1:3010/app/login" --data "username=admin&password=admin123")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$C" -c "$C" -o /dev/null -X POST "http://127.0.0.1:3010/app/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
fi

# گرفتن رکورد ۱
ID=$(curl -s -b "$C" "http://127.0.0.1:3010/app/api/surveys?page=1&per_page=1" | python3 -c "import json,sys; print(json.load(sys.stdin)['items'][0]['id'])")
echo "record id: $ID"
curl -s -b "$C" "http://127.0.0.1:3010/app/print/$ID" -o /tmp/print_page.html
curl -s -b "$C" "http://127.0.0.1:3010/app/login" -o /tmp/login_page.html
wc -c /tmp/print_page.html /tmp/login_page.html

"$PY" - << 'EOF'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 900, "height": 1100})
    BASE = "http://127.0.0.1:3010/app"

    def do_login(u, pw):
        pg.goto(f"{BASE}/login", wait_until="networkidle")
        pg.fill('input[name="username"]', u)
        pg.fill('input[name="password"]', pw)
        pg.click('button[type="submit"]')
        pg.wait_for_load_state("networkidle")

    # صفحهٔ ورود (اسکرین‌شات قبل از ورود)
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.screenshot(path="/tmp/render/login.png", full_page=True)

    # ورود: ممکن است رمز قبلا در این دیتابیس عوض شده باشد
    do_login("admin", "admin123")
    if "/login" in pg.url:
        do_login("admin", "Adm1n#2026")
    if "/change-password" in pg.url:
        pg.fill('input[name="current_password"]', "Adm1n#2026")
        pg.fill('input[name="new_password"]', "Adm1n#2026")
        pg.fill('input[name="new_password2"]', "Adm1n#2026")
        pg.click('button[type="submit"]')
        pg.wait_for_load_state("networkidle")
    assert "/login" not in pg.url, f"login failed: {pg.url}"

    # نسخهٔ چاپی — PDF واقعی A4
    pg.goto(f"{BASE}/print/1", wait_until="networkidle")
    pg.pdf(path="/tmp/render/sheet.pdf", format="A4", print_background=True)
    pg.screenshot(path="/tmp/render/sheet_view.png", full_page=True)
    b.close()
print("render done")
EOF
ls -la /tmp/render/ 2>/dev/null
# تعداد صفحات PDF
"$PY" -c "
import re
d = open('/tmp/render/sheet.pdf','rb').read()
print('PDF pages:', len(re.findall(rb'/Type\s*/Page[^s]', d)))
"