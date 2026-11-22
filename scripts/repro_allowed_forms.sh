#!/bin/bash
# بازتولید گزارش کاربر: «کاربر همه انواع فرم‌ها را می‌بیند» —
# کاربری که فقط فرم تلفنی برایش مجاز است، در همهٔ مسیرها بررسی می‌شود.
set -u
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
mkdir -p "$APP_DIR/logs"
VPY=/home/z/my-project/venv/bin/python3
export SURVEY_DATABASE_URL="sqlite:////$APP_DIR/data/test_repro.db"
LOG="$APP_DIR/logs/test-server.log"

rm -f data/test_repro.db
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
PASS=0; FAIL=0
chk() { local name="$1" got="$2" expect="$3"
  if [ "$got" = "$expect" ]; then echo "  ✅ $name → $got"; PASS=$((PASS+1));
  else echo "  ❌ $name — دریافت $got، انتظار $expect"; FAIL=$((FAIL+1)); fi }
J() { $VPY -c "import json,sys; d=json.load(open('$1')); $2"; }

# ---------- ورود مدیر ----------
CA=/tmp/repro_admin.txt; rm -f "$CA"
LOC=$(curl -s -c "$CA" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admin&password=admin123")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CA" -c "$CA" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
fi

# ---------- دادهٔ نمونه روی هر سه فرم ----------
for FK in tel individual group; do
  CID=$(curl -s -b "$CA" "$B/api/template/contact-options?form=$FK" | $VPY -c "import json,sys; d=json.load(sys.stdin); c=[x for x in d if not x['requires_answers']]; print(c[0]['id'] if c else (d[0]['id'] if d else ''))")
  RESP=$(curl -s -b "$CA" -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d "{\"form_key\":\"$FK\",\"first_name\":\"آزیت\",\"last_name\":\"$FK\",\"national_code\":\"0573754373\",\"phone\":\"09120000000\",\"province_id\":1,\"county_id\":1,\"survey_date\":\"1404/08/01\",\"contact_option_id\":$CID,\"answers\":[]}")
  echo "$RESP" | grep -q '"id"' || echo "     ⚠ ساخت رکورد $FK ناموفق: $RESP"
done

# ---------- کاربر محدودشده: فقط فرم تلفنی ----------
UN="rtel$RANDOM"
curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$UN\",\"full_name\":\"کاربر تلفنی\",\"role\":\"operator\",\"level\":\"user\",\"password\":\"Rt#12345\",\"permissions\":[\"view\",\"edit\",\"export\"],\"allowed_forms\":[\"tel\"]}" \
  -o /tmp/repro_u.json
echo "  کاربر ساخته شد: $(J /tmp/repro_u.json "print(d['record']['username'], d['record']['allowed_forms'])")"

# ---------- ورود کاربر محدودشده ----------
CU=/tmp/repro_user.txt; rm -f "$CU"
LOC=$(curl -s -c "$CU" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=$UN&password=Rt#12345")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CU" -c "$CU" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=Rt#12345&new_password=Rt#99999&new_password2=Rt#99999"
fi

# ---------- ۱) منوی بالای صفحه (HTML داشبورد) ----------
curl -s -b "$CU" "$B/dashboard" -o /tmp/repro_dash.html
grep -o 'فرم رضایت‌سنجی مراجعین مشاوره تلفنی' /tmp/repro_dash.html | head -1 > /dev/null && MENU_TEL=yes || MENU_TEL=no
grep -c 'فرم ثبت نظرسنجی مراجعین خدمات مشاوره فردی' /tmp/repro_dash.html > /tmp/repro_c1 || true; C1=$(cat /tmp/repro_c1)
grep -c 'فرم ثبت نظرسنجی خدمات مشاوره گروهی' /tmp/repro_dash.html > /tmp/repro_c2 || true; C2=$(cat /tmp/repro_c2)
chk "منو: فرم تلفنی هست" "$MENU_TEL" "yes"
echo "     (تعداد عنوان فردی در صفحه: $C1 — تعداد عنوان گروهی: $C2)"

# ---------- ۲) آرشیو: فیلتر فرم و رکوردها ----------
curl -s -b "$CU" "$B/api/surveys" -o /tmp/repro_list.json
chk "آرشیو فقط رکورد تلفنی" "$(J /tmp/repro_list.json "print(sorted(set(i['form_key'] for i in d['items'])))")" "['tel']"
chk "آرشیو ۱ رکورد" "$(J /tmp/repro_list.json "print(d['total'])")" "1"
curl -s -b "$CU" "$B/records" -o /tmp/repro_records.html
python3 - <<'EOF'
import re
html = open('/tmp/repro_records.html').read()
m = re.search(r'window\.__FORMS__ = (\[.*?\]);</script>', html)
import json
forms = json.loads(m.group(1)) if m else []
print(f"     __FORMS__ آرشیو: {[f['key'] for f in forms]}")
EOF

# ---------- ۳) ثبت فرم غیرمجاز ----------
chk "POST فرم فردی → 403" "$(curl -s -b "$CU" -o /dev/null -w '%{http_code}' -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d '{"form_key":"individual","first_name":"اا","last_name":"اا","national_code":"0573754373","phone":"09120000000","province_id":1,"county_id":1,"survey_date":"1404/08/01","answers":[]}')" "403"

# ---------- ۴) صفحهٔ ثبت فرم غیرمجاز ----------
chk "GET /form/individual → 403" "$(curl -s -b "$CU" -o /dev/null -w '%{http_code}' "$B/form/individual")" "403"

# ---------- ۵) داشبورد: تحلیل تلفیقی ----------
curl -s -b "$CU" "$B/api/dashboard" -o /tmp/repro_db.json
chk "تحلیل تلفیقی فقط تلفنی" "$(J /tmp/repro_db.json "print([f['key'] for f in d['combined']['per_form']])")" "['tel']"

# ---------- ۶) فیسِت‌ها ----------
curl -s -b "$CU" "$B/api/surveys/facets" -o /tmp/repro_fac.json
chk "facets → 200" "$(curl -s -b "$CU" -o /dev/null -w '%{http_code}' "$B/api/surveys/facets")" "200"

# ---------- ۷) خروجی اکسل ----------
chk "اکسل → 200" "$(curl -s -b "$CU" -o /dev/null -w '%{http_code}' "$B/api/surveys/export/excel")" "200"

echo
echo "نتیجه: $PASS موفق، $FAIL ناموفق"
[ "$FAIL" = "0" ]
