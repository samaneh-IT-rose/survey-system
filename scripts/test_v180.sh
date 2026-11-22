#!/bin/bash
# تست قابلیت‌های نسخهٔ 1.8.0:
#   ۱) seed خودکار کاربران سازمانی از فایل رسمی اکسل (idempotent — ۴۱ کاربر)
#   ۲) محدودیت استانی: کاربرِ دارای استان فقط رکوردهای استان خودش را می‌بیند و ثبت می‌کند
#      (آرشیو، رکورد تکی، ثبت، ویرایش، داشبورد، استخراج، اکسل، کمبوباکس استان/شهرستان)
#   ۳) کاربر بدون استان و مدیر: همهٔ استان‌ها
#   ۴) تغییر استان کاربر توسط مدیر → محدودیت بلافاصله اعمال می‌شود
set -u
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
mkdir -p "$APP_DIR/logs"
VPY=/home/z/my-project/venv/bin/python3
export SURVEY_DATABASE_URL="sqlite:////$APP_DIR/data/test_v180.db"
LOG="$APP_DIR/logs/test-server.log"

rm -f data/test_v180.db
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

# کدهای ملی معتبر برای رکوردهای آزمایشی (با الگوریتم کنترلی)
NC1=$($VPY -c "import sys; sys.path.insert(0,'.'); from app.utils.national_code import make_valid_national_code; print(make_valid_national_code('057375437'))")
NC2=$($VPY -c "import sys; sys.path.insert(0,'.'); from app.utils.national_code import make_valid_national_code; print(make_valid_national_code('057375438'))")
NC3=$($VPY -c "import sys; sys.path.insert(0,'.'); from app.utils.national_code import make_valid_national_code; print(make_valid_national_code('057375439'))")
NC4=$($VPY -c "import sys; sys.path.insert(0,'.'); from app.utils.national_code import make_valid_national_code; print(make_valid_national_code('057375430'))")

# ---------- ورود مدیر ----------
CA=/tmp/v180_admin.txt; rm -f "$CA"
LOC=$(curl -s -c "$CA" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admin&password=admin123")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CA" -c "$CA" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
fi

# ---------- ۱) seed خودکار کاربران از فایل رسمی اکسل ----------
OUT1=$($VPY -m app.seed_users --file app/seed_data/users_seed.xlsx 2>&1)
echo "$OUT1" | head -3
chk "seed: ۴۱ کاربر ساخته شد" "$(echo "$OUT1" | grep -o '41 کاربر ساخته شد؛ 0 ردیف رد شد' | head -1)" "41 کاربر ساخته شد؛ 0 ردیف رد شد"
OUT2=$($VPY -m app.seed_users --file app/seed_data/users_seed.xlsx 2>&1)
chk "seed دوباره: هیچ کاربر تکراری" "$(echo "$OUT2" | grep -o '0 کاربر ساخته شد؛ 41 ردیف رد شد' | head -1)" "0 کاربر ساخته شد؛ 41 ردیف رد شد"

# ---------- ۲) دادهٔ آزمایشی: رکورد در دو استان ----------
# استان ۲ = آذربایجان غربی، استان ۸ = تهران
CNTY2=$(curl -s -b "$CA" "$B/api/counties?province_id=2" | $VPY -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
CNTY8=$(curl -s -b "$CA" "$B/api/counties?province_id=8" | $VPY -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
CID=$(curl -s -b "$CA" "$B/api/template/contact-options?form=tel" | $VPY -c "import json,sys; d=json.load(sys.stdin); c=[x for x in d if not x['requires_answers']]; print(c[0]['id'] if c else d[0]['id'])")

mk_rec() { # $1=form_key $2=province $3=county $4=first $5=last $6=national
  curl -s -b "$CA" -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d "{
    \"form_key\":\"$1\",\"first_name\":\"$4\",\"last_name\":\"$5\",\"national_code\":\"$6\",
    \"phone\":\"09120000000\",\"province_id\":$2,\"county_id\":$3,\"survey_date\":\"1404/08/01\",
    \"contact_option_id\":$CID,\"answers\":[]}" | $VPY -c "import json,sys; d=json.load(sys.stdin); print(d.get('id','ERR'))"
}
R_P2=$(mk_rec tel 2 "$CNTY2" "رکورد" "غرب" "$NC1")
R_P8=$(mk_rec tel 8 "$CNTY8" "رکورد" "تهران" "$NC2")
chk "رکورد استان ۲ ساخته شد" "$([ "$R_P2" != "ERR" ] && [ -n "$R_P2" ] && echo yes || echo no)" "yes"
chk "رکورد استان ۸ ساخته شد" "$([ "$R_P8" != "ERR" ] && [ -n "$R_P8" ] && echo yes || echo no)" "yes"

# ---------- ۳) کاربر استانی seed‌شده: فرناز غنی دل تکانلو (آذربایجان غربی) ----------
CU=/tmp/v180_prov.txt; rm -f "$CU"
LOC=$(curl -s -c "$CU" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=2755629169&password=2755629169")
echo "$LOC" | grep -q "change-password" && chk "ورود کاربر seed + تغییر اجباری رمز" "yes" "yes" || chk "ورود کاربر seed + تغییر اجباری رمز" "no" "yes"
curl -s -b "$CU" -c "$CU" -o /dev/null -X POST "$B/change-password" \
  --data "current_password=2755629169&new_password=Pr#54321&new_password2=Pr#54321"

curl -s -b "$CU" "$B/api/provinces" -o /tmp/v180_prov_list.json
chk "کمبوباکس استان: فقط استان خودش" "$(J /tmp/v180_prov_list.json "print(d[0]['name'], len(d))")" "آذربایجان غربی 1"
chk "شهرستان استان دیگر → 403" "$(curl -s -b "$CU" -o /dev/null -w '%{http_code}' "$B/api/counties?province_id=8")" "403"
chk "شهرستان استان خودش → 200" "$(curl -s -b "$CU" -o /dev/null -w '%{http_code}' "$B/api/counties?province_id=2")" "200"

# آرشیو: فقط رکورد استان خودش
curl -s -b "$CU" "$B/api/surveys" -o /tmp/v180_list.json
chk "آرشیو: فقط رکورد استان خودش" "$(J /tmp/v180_list.json "print(d['total'], d['items'][0]['province']['name'])")" "1 آذربایجان غربی"
chk "رکورد استان دیگر → 403" "$(curl -s -b "$CU" -o /dev/null -w '%{http_code}' "$B/api/surveys/$R_P8")" "403"

# ثبت فرم استان دیگر → 403؛ ثبت فرم استان خودش → 200
chk "ثبت فرم استان دیگر → 403" "$(curl -s -b "$CU" -o /dev/null -w '%{http_code}' -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d "{
  \"form_key\":\"tel\",\"first_name\":\"تست\",\"last_name\":\"خارج\",\"national_code\":\"$NC4\",
  \"phone\":\"09120000009\",\"province_id\":8,\"county_id\":$CNTY8,\"survey_date\":\"1404/08/02\",
  \"contact_option_id\":$CID,\"answers\":[]}")" "403"
R_OWN=$(curl -s -b "$CU" -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d "{
  \"form_key\":\"tel\",\"first_name\":\"ثبت\",\"last_name\":\"خودش\",\"national_code\":\"$NC3\",
  \"phone\":\"09120000008\",\"province_id\":2,\"county_id\":$CNTY2,\"survey_date\":\"1404/08/02\",
  \"contact_option_id\":$CID,\"answers\":[]}" | $VPY -c "import json,sys; d=json.load(sys.stdin); print(d.get('id','ERR'))")
chk "ثبت فرم استان خودش → موفق" "$([ "$R_OWN" != "ERR" ] && [ -n "$R_OWN" ] && echo yes || echo no)" "yes"

# ویرایش و تلاش برای بردن رکورد به استان دیگر → 403
chk "انتقال رکورد به استان دیگر → 403" "$(curl -s -b "$CU" -o /dev/null -w '%{http_code}' -X PATCH "$B/api/surveys/$R_OWN" -H 'Content-Type: application/json' -d "{
  \"form_key\":\"tel\",\"first_name\":\"ثبت\",\"last_name\":\"خودش\",\"national_code\":\"$NC3\",
  \"phone\":\"09120000008\",\"province_id\":8,\"county_id\":$CNTY8,\"survey_date\":\"1404/08/02\",
  \"contact_option_id\":$CID,\"answers\":[]}")" "403"

# داشبورد: فقط رکوردهای استان خودش (1 اداری + 1 خودش = 2)
curl -s -b "$CU" "$B/api/dashboard" -o /tmp/v180_dash.json
chk "داشبورد: فقط استان خودش" "$(J /tmp/v180_dash.json "print(d['total'])")" "2"

# استخراج داده: فقط رکوردهای استان خودش
curl -s -b "$CU" "$B/api/extract?forms=tel" -o /tmp/v180_ext.json
chk "استخراج: فقط استان خودش" "$(J /tmp/v180_ext.json "print(d['total'])")" "2"
chk "اکسل استخراج → 200" "$(curl -s -b "$CU" -o /tmp/v180_ext.xlsx -w '%{http_code}' "$B/api/extract/excel?forms=tel")" "200"
chk "اکسل استخراج: ردیف‌های فقط استان خودش" "$($VPY -c "
from openpyxl import load_workbook
wb = load_workbook('/tmp/v180_ext.xlsx')
ws = wb.active
provs = [row[0] for row in ws.iter_rows(min_row=3, min_col=7, max_col=7, values_only=True) if row[0]]
print(len(provs), set(provs) == {'آذربایجان غربی'})")" "2 True"

# خروجی اکسل آرشیو: فقط استان خودش
curl -s -b "$CU" "$B/api/surveys/export/excel" -o /tmp/v180_arch.xlsx
chk "اکسل آرشیو: فقط استان خودش" "$($VPY -c "
from openpyxl import load_workbook
wb = load_workbook('/tmp/v180_arch.xlsx')
ws = wb.active
provs = [row[0] for row in ws.iter_rows(min_row=3, min_col=7, max_col=7, values_only=True) if row[0]]
print(len(provs) > 0 and set(provs) == {'آذربایجان غربی'})")" "True"

# ---------- ۴) کاربر بدون استان: همهٔ استان‌ها ----------
curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d '{"username":"freeall01","full_name":"بدون محدودیت","role":"operator","level":"user","password":"Fr#12345","permissions":["view","edit","export"]}' -o /dev/null
CF=/tmp/v180_free.txt; rm -f "$CF"
LOC=$(curl -s -c "$CF" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=freeall01&password=Fr#12345")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CF" -c "$CF" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=Fr#12345&new_password=Fr#99999&new_password2=Fr#99999"
fi
chk "کاربر بدون استان: همهٔ ۳۱ استان" "$(curl -s -b "$CF" "$B/api/provinces" | $VPY -c "import json,sys; print(len(json.load(sys.stdin)))")" "31"
chk "کاربر بدون استان: هر دو رکورد" "$(curl -s -b "$CF" "$B/api/surveys" | $VPY -c "import json,sys; print(json.load(sys.stdin)['total'])")" "3"

# ---------- ۵) مدیر: تعیین استان برای کاربر → محدودیت بلافاصله ----------
UIDF=$(curl -s -b "$CA" "$B/api/users" | $VPY -c "import json,sys; print([u for u in json.load(sys.stdin) if u['username']=='freeall01'][0]['id'])")
curl -s -b "$CA" -X PATCH "$B/api/users/$UIDF" -H 'Content-Type: application/json' \
  -d '{"province_name":"تهران"}' -o /tmp/v180_patch.json
chk "تعیین استان توسط مدیر" "$(J /tmp/v180_patch.json "print(d['record']['province_name'])")" "تهران"
curl -s -b "$CF" -c "$CF" -o /dev/null "$B/api/surveys"
chk "بعد از تعیین استان: فقط رکورد تهران" "$(curl -s -b "$CF" "$B/api/surveys" | $VPY -c "import json,sys; d=json.load(sys.stdin); print(d['total'], d['items'][0]['province']['name'])")" "1 تهران"

echo
echo "نتیجه: $PASS موفق، $FAIL ناموفق"
[ "$FAIL" = "0" ]
