#!/bin/bash
# تست مجوزهای الگوی فرم (رفع باگ ۴۰۳ فیلتر آرشیو برای کاربران غیرمدیر)
# - خواندن سؤال‌ها/وضعیت‌های تماس: هر کاربر لاگین‌شده با اجازهٔ «مشاهده» → 200
# - نوشتن (POST/PATCH): فقط مدیر سامانه → برای غیرمدیر 403
set -u
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
mkdir -p "$APP_DIR/logs"
export SURVEY_DATABASE_URL="sqlite:////$APP_DIR/data/test_tplperm.db"
export SURVEY_SELF_URL="http://127.0.0.1:3010"
LOG="$APP_DIR/logs/test-server.log"

rm -f data/test_tplperm.db
/home/z/my-project/venv/bin/python3 -c "
from app.database import Base, engine
import app.models  # noqa
Base.metadata.create_all(engine)
print('tables ok')"
/home/z/my-project/venv/bin/python3 scripts/seed.py | tail -1

/home/z/my-project/venv/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 3010 --log-level warning >> "$LOG" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT

for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3010/app/login || true)
  [ "$code" = "200" ] && break
  sleep 0.5
done

B="http://127.0.0.1:3010/app"
PASS=0; FAIL=0
chk() { local name="$1" expect="$2" got="$3"
  if [ "$got" = "$expect" ]; then echo "  ✅ $name ($got)"; PASS=$((PASS+1));
  else echo "  ❌ $name — انتظار $expect، دریافت $got"; FAIL=$((FAIL+1)); fi }

# ---------- ورود مدیر ----------
CA=/tmp/tpl_admin.txt; rm -f "$CA"
try_login() { curl -s -c "$CA" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admin&password=$1"; }
LOC=$(try_login admin123)
if [ -z "$LOC" ]; then LOC=$(try_login 'Adm1n#2026'); fi
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CA" -c "$CA" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
fi
chk "مدیر وارد شد" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' "$B/api/users")"

# ---------- ساخت کاربر غیرمدیر (ورود داده) ----------
R=$RANDOM
curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d "{\"username\":\"de$R\",\"full_name\":\"ورود داده\",\"role\":\"data_entry\",\"level\":\"user\",\"password\":\"De#12345\"}" \
  -o /tmp/tpl_u.json
DE=$(/home/z/my-project/venv/bin/python3 -c "import json; print(json.load(open('/tmp/tpl_u.json'))['record']['username'])")

CD=/tmp/tpl_de.txt; rm -f "$CD"
LOC=$(curl -s -c "$CD" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=$DE&password=De#12345")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CD" -c "$CD" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=De#12345&new_password=De#99999&new_password2=De#99999"
fi

# ---------- asserts ----------
chk "GET contact-options برای غیرمدیر → 200 (باگ ۴۰۳ رفع شد)" "200" \
  "$(curl -s -b "$CD" -o /dev/null -w '%{http_code}' "$B/api/template/contact-options")"
chk "GET contact-options?form=group برای غیرمدیر → 200" "200" \
  "$(curl -s -b "$CD" -o /dev/null -w '%{http_code}' "$B/api/template/contact-options?form=group")"
chk "GET questions برای غیرمدیر → 200" "200" \
  "$(curl -s -b "$CD" -o /dev/null -w '%{http_code}' "$B/api/template/questions?form=tel")"
chk "GET contact-options بدون ورود → 401/403 (داده عمومی نیست)" "401" \
  "$(curl -s -o /dev/null -w '%{http_code}' "$B/api/template/contact-options")"
chk "POST contact-options برای غیرمدیر → 403 (نوشتن فقط مدیر)" "403" \
  "$(curl -s -b "$CD" -o /dev/null -w '%{http_code}' -X POST "$B/api/template/contact-options" -H 'Content-Type: application/json' -d '{"form":"tel","text":"تست"}')"
chk "GET contact-options برای مدیر → 200" "200" \
  "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' "$B/api/template/contact-options")"
chk "facets برای غیرمدیر → 200" "200" \
  "$(curl -s -b "$CD" -o /dev/null -w '%{http_code}' "$B/api/surveys/facets")"

echo "-------------------------------------"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = "0" ]
