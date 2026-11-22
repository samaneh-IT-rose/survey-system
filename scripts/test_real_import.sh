#!/bin/bash
# ورود فایل واقعی اکسل مشتری روی سرور تست + بررسی صفحهٔ کاربران و استخراج
set -u
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
VPY=/home/z/my-project/venv/bin/python3
export SURVEY_DATABASE_URL="sqlite:////$APP_DIR/data/test_real.db"
LOG="$APP_DIR/logs/test-server.log"

rm -f data/test_real.db
$VPY scripts/seed.py | tail -1

$VPY -m uvicorn app.main:app --host 127.0.0.1 --port 3010 --log-level warning >> "$LOG" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT

for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3010/app/login || true)
  [ "$code" = "200" ] && break
  sleep 0.5
done

B="http://127.0.0.1:3010/app"
CA=/tmp/real_admin.txt; rm -f "$CA"
LOC=$(curl -s -c "$CA" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admin&password=admin123")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CA" -c "$CA" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
fi

echo "── ورود فایل رسمی مشتری ──"
curl -s -b "$CA" -X POST "$B/api/users/import-excel" \
  -F "file=@/home/z/my-project/upload/مدیران کلینیک و مسئولین اجرایی.xlsx" \
  -F "level=user" -F "role=operator" -F "password_mode=national_id" \
  -o /tmp/real_imp.json -w "HTTP %{http_code}\n"

$VPY - <<'PYEOF'
import json
d = json.load(open('/tmp/real_imp.json'))
print('message:', d['message'])
print('created:', len(d['created']), '| skipped:', len(d['skipped']))
by_pos = {}
for c in d['created']:
    by_pos[c['position']] = by_pos.get(c['position'], 0) + 1
print('by position:', by_pos)
print('نمونه اول:', d['created'][0])
print('نمونه آخر:', d['created'][-1])
for s in d['skipped'][:5]:
    print('skipped:', s)
PYEOF

echo "── بررسی فهرست کاربران (فیلدهای پروفایل) ──"
curl -s -b "$CA" "$B/api/users" -o /tmp/real_users.json
$VPY - <<'PYEOF'
import json
rows = json.load(open('/tmp/real_users.json'))
print('کل کاربران:', len(rows))
managers = [u for u in rows if u['position'] == 'مدیران کلینیک']
execs = [u for u in rows if u['position'] == 'مسئولین اجرایی']
print('مدیران کلینیک:', len(managers), '| مسئولین اجرایی:', len(execs))
u = managers[0] if managers else rows[0]
print('نمونه:', u['full_name'], '|', u['national_id'], '|', u['province_name'], '|', u['phone'], '|', u['position'])
PYEOF

echo "── عناصر جدید صفحهٔ کاربران و استخراج ──"
curl -s -b "$CA" "$B/users" -o /tmp/real_users.html
for token in "u_national_id" "u_province" "u_phone" "u_position" "u_notes" "importModal" "btnImportUsers" "import-template" "00" ; do
  if grep -q "$token" /tmp/real_users.html; then echo "  ✅ users.html: $token"; else echo "  ❌ users.html فاقد: $token"; fi
done
curl -s -b "$CA" "$B/extract" -o /tmp/real_extract.html
for token in "ex_forms" "ex_base" "ex_q_tel" "ex_q_individual" "ex_q_group" "exRunBtn" "exExcelBtn" "استخراج داده از فرم‌ها"; do
  if grep -q "$token" /tmp/real_extract.html; then echo "  ✅ extract.html: $token"; else echo "  ❌ extract.html فاقد: $token"; fi
done
curl -s -b "$CA" "$B/records" -o /tmp/real_records.html
if grep -q 'extract' /tmp/real_records.html; then echo "  ✅ منو: لینک استخراج داده هست"; else echo "  ❌ منو فاقد لینک استخراج"; fi

echo "── ورود مجدد همان فایل (تکراری‌ها) ──"
curl -s -b "$CA" -X POST "$B/api/users/import-excel" \
  -F "file=@/home/z/my-project/upload/مدیران کلینیک و مسئولین اجرایی.xlsx" \
  -F "level=user" -F "role=operator" -F "password_mode=national_id" \
  -o /tmp/real_imp2.json -w "HTTP %{http_code}\n"
$VPY -c "import json; d=json.load(open('/tmp/real_imp2.json')); print('message:', d['message'])"
