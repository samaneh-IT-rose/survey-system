#!/bin/bash
# تست قابلیت‌های نسخهٔ 1.9.0:
#   ۱) ادغام استان‌ها/شهرستان‌های اکسل رسمی در استارت (۳۱ استان / ۱۱۳۲ شهرستان، idempotent)
#   ۲) دو لایهٔ دسترسی «سطح استان» و «ادارهٔ استان» + صفحهٔ «سطح دسترسی فرم‌ها»
#      — فرم بدون تیک لایهٔ ادارات: در منو، صفحهٔ ثبت، ثبت API، آرشیو، استخراج،
#        داشبورد و انتقادات دیده نمی‌شود
#   ۳) انتقادات و پیشنهادات: ثبت در فرم، صفحهٔ اختصاصی، قیدهای دسترسی، خروجی اکسل، PATCH جزئی
#   ۴) کاربران: لایهٔ دسترسی + ادارهٔ استان در API و ورود گروهی اکسل (لایه بر اساس نام شیت)
set -u
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
mkdir -p "$APP_DIR/logs"
VPY=/home/z/my-project/venv/bin/python3
export SURVEY_DATABASE_URL="sqlite:////$APP_DIR/data/test_v190.db"
LOG="$APP_DIR/logs/test-server.log"

rm -f data/test_v190.db
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

# کدهای ملی معتبر برای رکوردهای آزمایشی
NC1=$($VPY -c "import sys; sys.path.insert(0,'.'); from app.utils.national_code import make_valid_national_code; print(make_valid_national_code('057375437'))")
NC2=$($VPY -c "import sys; sys.path.insert(0,'.'); from app.utils.national_code import make_valid_national_code; print(make_valid_national_code('057375438'))")
NC3=$($VPY -c "import sys; sys.path.insert(0,'.'); from app.utils.national_code import make_valid_national_code; print(make_valid_national_code('057375439'))")
NC4=$($VPY -c "import sys; sys.path.insert(0,'.'); from app.utils.national_code import make_valid_national_code; print(make_valid_national_code('057375430'))")

# ---------- ورود مدیر ----------
CA=/tmp/v190_admin.txt; rm -f "$CA"
LOC=$(curl -s -c "$CA" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admin&password=admin123")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CA" -c "$CA" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
fi
chk "مدیر وارد شد" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' "$B/api/users")"

# ---------- ۱) ادغام استان‌ها/شهرستان‌های اکسل رسمی ----------
$VPY -c "
import sys; sys.path.insert(0,'.')
from sqlalchemy import func, select
from app.database import SessionLocal
from app.models import County, Province
from app.services.geo import ensure_official_locations
with SessionLocal() as db:
    p = db.scalar(select(func.count()).select_from(Province))
    c = db.scalar(select(func.count()).select_from(County))
    print(f'LOC {p} {c}')
    again = ensure_official_locations(db)
    print(f'AGAIN {again[\"provinces_added\"]} {again[\"counties_added\"]}')
    ard = db.scalar(select(Province).where(Province.name == 'اردبیل'))
    towns = {t.name for t in db.scalars(select(County).where(County.province_id == ard.id)).all()} if ard else set()
    print(f'ARD {\"بیله سوار\" in towns}')
" > /tmp/v190_geo.txt
chk "۳۱ استان رسمی در دیتابیس" "$(grep -o 'LOC 31 [0-9]*' /tmp/v190_geo.txt | awk '{print ($3>=1132)?"31":"کمتر:"$3}')" "31"
chk "ادغام idempotent (اجرای دوباره هیچ ردیفی نمی‌سازد)" "$(grep -o 'AGAIN 0 0' /tmp/v190_geo.txt)" "AGAIN 0 0"
chk "شهرستان اکسل رسمی (بیله سوار) در اردبیل" "$(grep -o 'ARD True' /tmp/v190_geo.txt)" "ARD True"

# ---------- ۲) قواعد پیش‌فرض دو لایه + گارد مدیر ----------
curl -s -b "$CA" "$B/api/form-access" -o /tmp/v190_fa.json
chk "قواعد پیش‌فرض هر سه فرم ساخته شد" "$(J /tmp/v190_fa.json "print(len(d['rules']))")" "3"
chk "پیش‌فرض: هر دو لایه می‌بینند" "$(J /tmp/v190_fa.json "print(all(r['visible_to_province'] and r['visible_to_department'] for r in d['rules']))")" "True"

# کاربر عادی: گارد مدیریتی
R=$RANDOM
curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d "{\"username\":\"ro$R\",\"full_name\":\"کاربر ساده\",\"role\":\"data_entry\",\"level\":\"user\",\"password\":\"Ro#12345\"}" -o /dev/null
CR=/tmp/v190_ro.txt; rm -f "$CR"
LOC=$(curl -s -c "$CR" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=ro$R&password=Ro#12345")
echo "$LOC" | grep -q "change-password" && curl -s -b "$CR" -c "$CR" -o /dev/null -X POST "$B/change-password" \
  --data "current_password=Ro#12345&new_password=Ro#99999&new_password2=Ro#99999"
chk "کاربر عادی: GET قواعد → 403" "$(curl -s -b "$CR" -o /dev/null -w '%{http_code}' "$B/api/form-access")" "403"
chk "کاربر عادی: PUT قواعد → 403" "$(curl -s -b "$CR" -o /dev/null -w '%{http_code}' -X PUT "$B/api/form-access" -H 'Content-Type: application/json' -d '{"rules":[]}')" "403"

# ---------- ۳) کاربران دو لایه ----------
# U_DEP: لایهٔ «ادارهٔ استان» + استان تهران | U_PROV: لایهٔ «سطح استان» + استان تهران
curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d "{\"username\":\"dep$R\",\"full_name\":\"ادارهٔ تهران\",\"role\":\"data_entry\",\"level\":\"user\",\"password\":\"De#12345\",\"access_layer\":\"department\",\"department\":\"تربیت بدنی\",\"province_name\":\"تهران\",\"national_id\":\"$NC1\"}" -o /tmp/v190_dep.json
chk "کاربر لایهٔ ادارهٔ استان ساخته شد (ادارهٔ تربیت بدنی)" "$(J /tmp/v190_dep.json "print(d['record']['access_layer'], d['record']['department'], d['record']['access_layer_label'])")" "department تربیت بدنی ادارهٔ استان"

curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d "{\"username\":\"prv$R\",\"full_name\":\"مسئول استانی\",\"role\":\"data_entry\",\"level\":\"user\",\"password\":\"Pv#12345\",\"access_layer\":\"province\",\"province_name\":\"تهران\",\"national_id\":\"$NC2\"}" -o /tmp/v190_prv.json
chk "کاربر لایهٔ سطح استان ساخته شد" "$(J /tmp/v190_prv.json "print(d['record']['access_layer'], d['record']['access_layer_label'])")" "province سطح استان"

chk "لایهٔ نامعتبر → 422" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d "{\"username\":\"bad$R\",\"full_name\":\"خطا\",\"role\":\"data_entry\",\"level\":\"user\",\"password\":\"Ba#12345\",\"access_layer\":\"city\"}")" "422"

# تغییر لایه با PATCH
DEP_ID=$(J /tmp/v190_dep.json "print(d['record']['id'])")
curl -s -b "$CA" -X PATCH "$B/api/users/$DEP_ID" -H 'Content-Type: application/json' -d '{"access_layer":"province","department":""}' -o /tmp/v190_dep2.json
chk "تغییر لایهٔ کاربر با PATCH" "$(J /tmp/v190_dep2.json "print(d['record']['access_layer'])")" "province"
curl -s -b "$CA" -X PATCH "$B/api/users/$DEP_ID" -H 'Content-Type: application/json' -d '{"access_layer":"department","department":"تربیت بدنی"}' -o /tmp/v190_dep3.json
chk "بازگشت لایهٔ ادارهٔ استان" "$(J /tmp/v190_dep3.json "print(d['record']['access_layer'])")" "department"

# ---------- ۴) ورود گروهی اکسل: لایه بر اساس نام شیت ----------
$VPY -c "
from openpyxl import Workbook
import sys; sys.path.insert(0,'.')
from app.utils.national_code import make_valid_national_code
wb = Workbook(); wb.remove(wb.active)
h = ['استان', 'نام و نام خانوادگی', 'کد ملی', 'شماره همراه']
ws1 = wb.create_sheet('مسئولین اجرایی'); ws1.append(h)
ws1.append(['تهران', 'واردشده استانی', make_valid_national_code('057375445'), '09121110001'])
ws2 = wb.create_sheet('مدیران کلینیک'); ws2.append(h)
ws2.append(['تهران', 'واردشده کلینیک', make_valid_national_code('057375446'), '09121110002'])
wb.save('/tmp/v190_imp.xlsx')
print('xlsx ok')"
chk "ورود گروهی اکسل → 200" "$(curl -s -b "$CA" -o /tmp/v190_imp.json -w '%{http_code}' -X POST "$B/api/users/import-excel" -F "file=@/tmp/v190_imp.xlsx" -F "role=data_entry" -F "level=user")" "200"
chk "هر دو کاربر اکسل ساخته شدند" "$(J /tmp/v190_imp.json "print(len(d['created']))")" "2"
curl -s -b "$CA" "$B/api/users" -o /tmp/v190_users.json
chk "لایهٔ شیت «مسئولین اجرایی» = سطح استان" "$(J /tmp/v190_users.json "print([u['access_layer'] for u in d if u['position']=='مسئولین اجرایی' and u['full_name']=='واردشده استانی'][0])")" "province"
chk "لایهٔ شیت «مدیران کلینیک» = ادارهٔ استان" "$(J /tmp/v190_users.json "print([u['access_layer'] for u in d if u['position']=='مدیران کلینیک' and u['full_name']=='واردشده کلینیک'][0])")" "department"

# ---------- ۵) دادهٔ آزمایشی در دو استان (شناسهٔ استان با نام از API) ----------
PID_W=$(curl -s -b "$CA" "$B/api/provinces" | $VPY -c "import json,sys; print([p['id'] for p in json.load(sys.stdin) if p['name']=='آذربایجان غربی'][0])")
PID_T=$(curl -s -b "$CA" "$B/api/provinces" | $VPY -c "import json,sys; print([p['id'] for p in json.load(sys.stdin) if p['name']=='تهران'][0])")
CNTY_W=$(curl -s -b "$CA" "$B/api/counties?province_id=$PID_W" | $VPY -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
CNTY_T=$(curl -s -b "$CA" "$B/api/counties?province_id=$PID_T" | $VPY -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
CT=$(curl -s -b "$CA" "$B/api/template/contact-options?form=tel" | $VPY -c "import json,sys; d=json.load(sys.stdin); c=[x for x in d if not x['requires_answers']]; print(c[0]['id'] if c else d[0]['id'])")
CI=$(curl -s -b "$CA" "$B/api/template/contact-options?form=individual" | $VPY -c "import json,sys; d=json.load(sys.stdin); c=[x for x in d if not x['requires_answers']]; print(c[0]['id'] if c else d[0]['id'])")

mk_rec() { # $1=form $2=prov $3=cnty $4=first $5=last $6=NC $7=crit $8=contact
  curl -s -b "$CA" -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d "{
    \"form_key\":\"$1\",\"first_name\":\"$4\",\"last_name\":\"$5\",\"national_code\":\"$6\",
    \"phone\":\"09120000000\",\"province_id\":$2,\"county_id\":$3,\"survey_date\":\"1404/08/01\",
    \"contact_option_id\":$8,\"criticism\":$7,\"answers\":[]}" | $VPY -c "import json,sys; d=json.load(sys.stdin); print(d.get('id','ERR'))"
}
R_TEL_T=$(mk_rec tel "$PID_T" "$CNTY_T" "انتقاد" "تلفنی" "$NC1" '"کیفیت پاسخگویی تلفنی باید بهتر شود"' "$CT")
R_IND_T=$(mk_rec individual "$PID_T" "$CNTY_T" "انتقاد" "فردی" "$NC2" '"سالن گروه‌ها کوچک است"' "$CI")
R_TEL_W=$(mk_rec tel "$PID_W" "$CNTY_W" "انتقاد" "غرب" "$NC3" '"مکمل‌ها دیر می‌رسد"' "$CT")
R_TEL_NOC=$(mk_rec tel "$PID_T" "$CNTY_T" "بدون" "انتقاد" "$NC4" '""' "$CT")
chk "رکورد تلفنی با انتقاد ساخته شد" "$([ "$R_TEL_T" != "ERR" ] && [ -n "$R_TEL_T" ] && echo yes || echo no)" "yes"
chk "رکورد فردی با انتقاد ساخته شد" "$([ "$R_IND_T" != "ERR" ] && [ -n "$R_IND_T" ] && echo yes || echo no)" "yes"
chk "رکورد بدون انتقاد ساخته شد" "$([ "$R_TEL_NOC" != "ERR" ] && [ -n "$R_TEL_NOC" ] && echo yes || echo no)" "yes"

# ---------- ۶) قاعدهٔ فرم تلفنی فقط برای سطح استان ----------
curl -s -b "$CA" -X PUT "$B/api/form-access" -H 'Content-Type: application/json' \
  -d '{"rules":[{"form_key":"tel","visible_to_province":true,"visible_to_department":false}]}' -o /tmp/v190_put.json
chk "ذخیرهٔ قاعده: فرم تلفنی بدون ادارهٔ استان" "$(J /tmp/v190_put.json "print(d['changed'])")" "['tel']"

# ورود کاربر لایهٔ ادارهٔ استان
CD=/tmp/v190_dep.txt; rm -f "$CD"
LOC=$(curl -s -c "$CD" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=dep$R&password=De#12345")
echo "$LOC" | grep -q "change-password" && curl -s -b "$CD" -c "$CD" -o /dev/null -X POST "$B/change-password" \
  --data "current_password=De#12345&new_password=De#99999&new_password2=De#99999"

chk "صفحهٔ ثبت فرم تلفنی → 403" "$(curl -s -b "$CD" -o /dev/null -w '%{http_code}' "$B/form/tel")" "403"
chk "صفحهٔ ثبت فرم فردی → 200" "$(curl -s -b "$CD" -o /dev/null -w '%{http_code}' "$B/form/individual")" "200"
MENU_HTML=$(curl -s -b "$CD" "$B/records")
chk "منو: فرم تلفنی نیست" "$(echo "$MENU_HTML" | grep -c '/form/tel"' || true)" "0"
chk "منو: فرم فردی هست" "$(echo "$MENU_HTML" | grep -c '/form/individual"' | awk '{print ($1>=1)?"yes":"no"}')" "yes"
chk "ثبت API فرم تلفنی → 403" "$(curl -s -b "$CD" -o /dev/null -w '%{http_code}' -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d "{
  \"form_key\":\"tel\",\"first_name\":\"اداره\",\"last_name\":\"تلفنی\",\"national_code\":\"$NC3\",
  \"phone\":\"09120000009\",\"province_id\":$PID_T,\"county_id\":$CNTY_T,\"survey_date\":\"1404/08/02\",
  \"contact_option_id\":$CT,\"answers\":[]}")" "403"
R_DEP_IND=$(curl -s -b "$CD" -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d "{
  \"form_key\":\"individual\",\"first_name\":\"اداره\",\"last_name\":\"فردی\",\"national_code\":\"$NC4\",
  \"phone\":\"09120000009\",\"province_id\":$PID_T,\"county_id\":$CNTY_T,\"survey_date\":\"1404/08/02\",
  \"contact_option_id\":$CI,\"answers\":[]}" | $VPY -c "import json,sys; d=json.load(sys.stdin); print(d.get('id','ERR'))")
chk "ثبت API فرم فردی → موفق" "$([ "$R_DEP_IND" != "ERR" ] && [ -n "$R_DEP_IND" ] && echo yes || echo no)" "yes"

# آرشیو لایهٔ اداره: رکورد تلفنی دیده نمی‌شود (۲ رکورد فردی تهران: اداری + خودش)
curl -s -b "$CD" "$B/api/surveys" -o /tmp/v190_list_dep.json
chk "آرشیو ادارهٔ استان: بدون رکورد تلفنی" "$(J /tmp/v190_list_dep.json "print(all((i['form_key'] or 'tel') != 'tel' for i in d['items']), len(d['items']))")" "True 2"
# استخراج دادهٔ لایهٔ اداره: بدون فرم تلفنی
chk "استخراج دادهٔ اداره: بدون تلفنی" "$(curl -s -b "$CD" "$B/api/extract?forms=tel,individual" | $VPY -c "
import json,sys; d=json.load(sys.stdin)
print(d['forms'] == ['individual'], d['total'])")" "True 2"
# داشبورد لایهٔ اداره: رکورد تلفنی ندارد
curl -s -b "$CD" "$B/api/dashboard" -o /tmp/v190_dash_dep.json
chk "داشبورد اداره: مجموع = ۲ (فقط فردی تهران)" "$(J /tmp/v190_dash_dep.json "print(d['total'])")" "2"

# کاربر لایهٔ سطح استان: تلفنی هنوز باز است
CP=/tmp/v190_prv.txt; rm -f "$CP"
LOC=$(curl -s -c "$CP" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=prv$R&password=Pv#12345")
echo "$LOC" | grep -q "change-password" && curl -s -b "$CP" -c "$CP" -o /dev/null -X POST "$B/change-password" \
  --data "current_password=Pv#12345&new_password=Pv#99999&new_password2=Pv#99999"
chk "صفحهٔ فرم تلفنی برای سطح استان → 200" "$(curl -s -b "$CP" -o /dev/null -w '%{http_code}' "$B/form/tel")" "200"

# ---------- ۷) انتقادات و پیشنهادات ----------
curl -s -b "$CA" "$B/api/criticisms" -o /tmp/v190_crit.json
chk "مدیر: سه رکورد دارای انتقاد (بدون رکورد خالی)" "$(J /tmp/v190_crit.json "print(d['total'])")" "3"

# کاربر لایهٔ ادارهٔ استان (تهران): فقط انتقاد رکورد فردی تهران
curl -s -b "$CD" "$B/api/criticisms" -o /tmp/v190_crit_dep.json
chk "ادارهٔ استان: ۱ انتقاد (فردی تهران — تلفنی و استان دیگر حذف)" "$(J /tmp/v190_crit_dep.json "print(d['total'], d['items'][0]['form_key'] if d['items'] else '-')")" "1 individual"

# کاربر آذربایجان غربی (سطح استان): فقط انتقاد رکورد استان خودش
curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d "{\"username\":\"oth$R\",\"full_name\":\"مسئول غرب\",\"role\":\"data_entry\",\"level\":\"user\",\"password\":\"Ot#12345\",\"province_name\":\"آذربایجان غربی\"}" -o /dev/null
CO=/tmp/v190_oth.txt; rm -f "$CO"
LOC=$(curl -s -c "$CO" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=oth$R&password=Ot#12345")
echo "$LOC" | grep -q "change-password" && curl -s -b "$CO" -c "$CO" -o /dev/null -X POST "$B/change-password" \
  --data "current_password=Ot#12345&new_password=Ot#99999&new_password2=Ot#99999"
curl -s -b "$CO" "$B/api/criticisms" -o /tmp/v190_crit_oth.json
chk "سطح استان غرب: فقط انتقاد استان خودش" "$(J /tmp/v190_crit_oth.json "print(d['total'], d['items'][0]['province'] if d['items'] else '-')")" "1 آذربایجان غربی"

# ویرایش انتقاد با PATCH جزئی (فقط فیلد انتقاد) + حذف انتقاد از فهرست
curl -s -b "$CA" -X PATCH "$B/api/surveys/$R_TEL_T" -H 'Content-Type: application/json' \
  -d '{"criticism":"متن جدید انتقاد"}' -o /tmp/v190_patch.json
chk "PATCH جزئی انتقاد ذخیره شد" "$(J /tmp/v190_patch.json "print(d['record']['criticism'])")" "متن جدید انتقاد"
chk "PATCH جزئی: بقیهٔ داده‌ها دست‌نخورده" "$(J /tmp/v190_patch.json "print(d['record']['first_name'], d['record']['province']['name'])")" "انتقاد تهران"
curl -s -b "$CA" -X PATCH "$B/api/surveys/$R_TEL_T" -H 'Content-Type: application/json' -d '{"criticism":""}' -o /tmp/v190_patch2.json
chk "انتقاد خالی از فهرست خارج شد" "$(curl -s -b "$CA" "$B/api/criticisms" | $VPY -c "import json,sys; print(json.load(sys.stdin)['total'])")" "2"

# خروجی اکسل انتقادات
chk "خروجی اکسل انتقادات → 200 + فایل معتبر" "$(curl -s -b "$CA" -o /tmp/v190_crit.xlsx -w '%{http_code} %{content_type}' "$B/api/criticisms/export/excel" | grep -c "200 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")" "1"
chk "اکسل انتقادات: فقط رکوردهای دارای متن" "$($VPY -c "
from openpyxl import load_workbook
ws = load_workbook('/tmp/v190_crit.xlsx').active
rows = list(ws.iter_rows(min_row=3, values_only=True))
print(len(rows))")" "2"

# ستون انتقادات در خروجی اکسل آرشیو
curl -s -b "$CA" "$B/api/surveys/export/excel" -o /tmp/v190_arch.xlsx
chk "اکسل آرشیو: ستون انتقادات و پیشنهادات" "$($VPY -c "
from openpyxl import load_workbook
ws = load_workbook('/tmp/v190_arch.xlsx').active
hdr = [c.value for c in ws[2]]
print('انتقادات و پیشنهادات' in hdr)")" "True"

# صفحهٔ انتقادات برای کاربر عادی باز است و صفحهٔ قواعد فقط مدیر
chk "صفحهٔ انتقادات برای کاربر عادی → 200" "$(curl -s -b "$CR" -o /dev/null -w '%{http_code}' "$B/criticisms")" "200"
chk "صفحهٔ سطح دسترسی فرم‌ها برای کاربر عادی → ریدایرکت" "$(curl -s -b "$CR" -o /dev/null -w '%{http_code}' "$B/form-access")" "303"
chk "صفحهٔ سطح دسترسی فرم‌ها برای مدیر → 200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' "$B/form-access")" "200"

# ---------- جمع‌بندی ----------
echo ""
echo "==== نتیجهٔ تست نسخهٔ 1.9.0: $PASS موفق، $FAIL ناموفق ===="
[ "$FAIL" = "0" ]
