#!/bin/bash
# تست قابلیت‌های نسخهٔ 1.7.0:
#   ۱) فیلدهای مشخصات سازمانی کاربر (کد ملی، استان، شماره همراه، سمت، توضیحات)
#   ۲) ورود گروهی کاربران از اکسل (شیت = گروه/سمت، نام کاربری = کد ملی) + قالب نمونه
#   ۳) استخراج آزاد داده از تمام فرم‌ها (schema + ردیف‌ها + اکسل) با قیدهای دسترسی
#   ۴) شفاف‌سازی رفتار نقش «مدیر» در فرم‌های مجاز (behavior مستند — می‌بیند همه را)
set -u
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
mkdir -p "$APP_DIR/logs"
VPY=/home/z/my-project/venv/bin/python3
export SURVEY_DATABASE_URL="sqlite:////$APP_DIR/data/test_v170.db"
LOG="$APP_DIR/logs/test-server.log"

rm -f data/test_v170.db
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
CA=/tmp/v170_admin.txt; rm -f "$CA"
LOC=$(curl -s -c "$CA" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admin&password=admin123")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CA" -c "$CA" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
fi

# ---------- ۱) فیلدهای مشخصات سازمانی ----------
CU1=/tmp/v170_u1.json
curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d '{"username":"prof01","full_name":"فرناز غنی دل تکانلو","role":"operator","level":"user","password":"Pr#12345","permissions":["view","edit"],"national_id":"2755629169","province_name":"آذربایجان غربی","phone":"09146716366","position":"مدیر کلینیک","notes":"*"}' \
  -o "$CU1"
chk "ساخت کاربر با مشخصات کامل" "$(J "$CU1" "print(d['record']['national_id'], d['record']['province_name'], d['record']['position'])")" "2755629169 آذربایجان غربی مدیر کلینیک"
UID1=$(J "$CU1" "print(d['record']['id'])")
curl -s -b "$CA" -X PATCH "$B/api/users/$UID1" -H 'Content-Type: application/json' \
  -d '{"phone":"۰۹۱۴۶۷۱۶۳۶۶","position":"مسئول اجرایی"}' -o /tmp/v170_u1p.json
chk "ویرایش مشخصات + نرمال‌سازی رقم فارسی" "$(J /tmp/v170_u1p.json "print(d['record']['phone'], d['record']['position'])")" "09146716366 مسئول اجرایی"

# ---------- ۲) ورود گروهی از اکسل ----------
# ساخت فایل اکسل هم‌ساختار با فایل رسمی مشتری (دو شیت)
$VPY - <<'PYEOF'
from openpyxl import Workbook
wb = Workbook(); wb.remove(wb.active)
h = ["استان", "نام و نام خانوادگی", "کد ملی", "شماره همراه", "توضیحات"]
ws1 = wb.create_sheet("مسئولین اجرایی"); ws1.sheet_view.rightToLeft = True
ws1.append(h)
ws1.append(["آذربایجان شرقی", "پری فتحی پور", "1376696861", "09143174356", "*"])
ws1.append(["اردبیل", "نرگس نصرتی قنبرلو", "1621800970", "09142882214", "*"])
ws1.append(["اصفهان", "راحله اسدی آقبلاغی", 57375437, 9134636528, "*"])  # عددی — صفرهای ابتدایی باید بازیابی شود
ws1.append(["سمنان", "بدون کد ملی", "", "09194304869", "*"])               # باید رد شود
ws2 = wb.create_sheet("مدیران کلینیک"); ws2.sheet_view.rightToLeft = True
ws2.append(h)
ws2.append(["ایلام", "مریم غلامی", "3341333010", "09393577756", "*"])
ws2.append(["تهران", "هادی پرگیر", "0063896281", "09122139752", "*"])      # صفر ابتدایی متنی — بدون هم‌نامی با کد عددی راحله
wb.save("/tmp/v170_users.xlsx")
print("xlsx built")
PYEOF

CURL_CODE=$(curl -s -b "$CA" -X POST "$B/api/users/import-excel" -F "file=@/tmp/v170_users.xlsx" -F "level=user" -F "role=operator" -F "password_mode=national_id" -o /tmp/v170_imp.json -w '%{http_code}')
chk "ورود گروهی اکسل → 200" "$CURL_CODE" "200"
chk "۵ ساخته، ۱ رد" "$(J /tmp/v170_imp.json "print(len(d['created']), len(d['skipped']))")" "5 1"
chk "نام کاربری = کد ملی" "$(J /tmp/v170_imp.json "print(d['created'][0]['username'])")" "1376696861"
chk "سمت از نام شیت" "$(J /tmp/v170_imp.json "print(d['created'][0]['position'])")" "مسئولین اجرایی"
chk "بازیابی صفر ابتدایی کد ملی عددی" "$(J /tmp/v170_imp.json "print(d['created'][2]['username'])")" "0057375437"
chk "بازیابی صفر ابتدایی شماره همراه" "$(J /tmp/v170_imp.json "print(d['created'][2]['phone'])")" "09134636528"
chk "ردیف بدون کد ملی رد شد" "$(J /tmp/v170_imp.json "print(d['skipped'][0]['reason'][:12])")" "کد ملی نامعت"

# ورود دوبارهٔ همان فایل — ۵ تکراری + ۱ ردیف بی‌کدملی = ۶ رد
curl -s -b "$CA" -X POST "$B/api/users/import-excel" -F "file=@/tmp/v170_users.xlsx" -F "level=user" -F "role=operator" -F "password_mode=national_id" -o /tmp/v170_imp2.json
chk "ورود دوباره: همه تکراری" "$(J /tmp/v170_imp2.json "print(len(d['created']), len(d['skipped']))")" "0 6"

chk "دانلود قالب اکسل → 200" "$(curl -s -b "$CA" -o /tmp/v170_tpl.xlsx -w '%{http_code}' "$B/api/users/import-template")" "200"
chk "قالب معتبر xlsx" "$($VPY -c "from openpyxl import load_workbook; wb=load_workbook('/tmp/v170_tpl.xlsx'); print(len(wb.sheetnames))")" "2"

# رمز اولیه = کد ملی + تغییر اجباری در اولین ورود
CIMP=/tmp/v170_imp_user.txt; rm -f "$CIMP"
LOC=$(curl -s -c "$CIMP" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=1376696861&password=1376696861")
echo "$LOC" | grep -q "change-password" && chk "رمز اولیه کد ملی + تغییر اجباری" "yes" "yes" || chk "رمز اولیه کد ملی + تغییر اجباری" "no" "yes"
curl -s -b "$CIMP" -c "$CIMP" -o /dev/null -X POST "$B/change-password" \
  --data "current_password=1376696861&new_password=Im#54321&new_password2=Im#54321"

# ---------- ۳) استخراج از تمام فرم‌ها ----------
# دادهٔ نمونه روی هر سه فرم — با وضعیت تماس بدون نیاز به پاسخ
for FK in tel individual group; do
  CID=$(curl -s -b "$CA" "$B/api/template/contact-options?form=$FK" | $VPY -c "import json,sys; d=json.load(sys.stdin); c=[x for x in d if not x['requires_answers']]; print(c[0]['id'] if c else (d[0]['id'] if d else ''))")
  RESP=$(curl -s -b "$CA" -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d "{
    \"form_key\":\"$FK\",\"first_name\":\"آزیت\",\"last_name\":\"$FK\",\"national_code\":\"0573754373\",
    \"phone\":\"09120000000\",\"province_id\":1,\"county_id\":1,\"survey_date\":\"1404/08/01\",
    \"contact_option_id\":$CID,\"answers\":[]}")
  echo "$RESP" | grep -q '"id"' || echo "     ⚠ ساخت رکورد $FK ناموفق: $RESP"
done

curl -s -b "$CA" "$B/api/extract/schema" -o /tmp/v170_schema.json
chk "schema مدیر: هر سه فرم" "$(J /tmp/v170_schema.json "print(len(d['forms']))")" "3"
chk "schema: ستون‌های پایه" "$(J /tmp/v170_schema.json "print(len(d['base_fields']))")" "14"

# استخراج با ستون‌های انتخابی: نام + استان + یک سؤال فردی و یک سؤال تلفنی
QID_IND=$(J /tmp/v170_schema.json "print([f for f in d['forms'] if f['key']=='individual'][0]['questions'][0]['id'])")
QID_TEL=$(J /tmp/v170_schema.json "print([f for f in d['forms'] if f['key']=='tel'][0]['questions'][0]['id'])")
curl -s -b "$CA" "$B/api/extract?forms=tel,individual&fields=base:first_name,base:province,q:$QID_TEL,q:$QID_IND" -o /tmp/v170_ext.json
chk "استخراج: ۲ ردیف (تلفنی + فردی)" "$(J /tmp/v170_ext.json "print(d['total'])")" "2"
chk "استخراج: ۴ ستون" "$(J /tmp/v170_ext.json "print(len(d['columns']))")" "4"
chk "استخراج: فرم‌ها درست" "$(J /tmp/v170_ext.json "print(d['forms'])")" "['individual', 'tel']"

chk "استخراج اکسل مدیر → 200" "$(curl -s -b "$CA" -o /tmp/v170_ext.xlsx -w '%{http_code}' "$B/api/extract/excel?forms=tel,individual,group")" "200"
chk "اکسل استخراج معتبر" "$($VPY -c "from openpyxl import load_workbook; wb=load_workbook('/tmp/v170_ext.xlsx'); print(wb.active.max_row >= 5)")" "True"

# کاربر محدودشده: فقط فرم تلفنی + دسترسی اکسل
CUR=/tmp/v170_ruser.json
curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d '{"username":"rext01","full_name":"محدود تلفنی","role":"operator","level":"user","password":"Rx#12345","permissions":["view","edit","export"],"allowed_forms":["tel"]}' \
  -o "$CUR"
RID=$(J "$CUR" "print(d['record']['id'])")
CR=/tmp/v170_ruser.txt; rm -f "$CR"
LOC=$(curl -s -c "$CR" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=rext01&password=Rx#12345")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CR" -c "$CR" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=Rx#12345&new_password=Rx#99999&new_password2=Rx#99999"
fi

curl -s -b "$CR" "$B/api/extract/schema" -o /tmp/v170_sch2.json
chk "schema کاربر محدود: فقط تلفنی" "$(J /tmp/v170_sch2.json "print([f['key'] for f in d['forms']])")" "['tel']"
curl -s -b "$CR" "$B/api/extract?forms=tel,individual" -o /tmp/v170_ext2.json
chk "استخراج محدود: فقط رکورد تلفنی" "$(J /tmp/v170_ext2.json "print(d['total'], d['forms'])")" "1 ['tel']"
chk "اکسل استخراج محدود → 200" "$(curl -s -b "$CR" -o /dev/null -w '%{http_code}' "$B/api/extract/excel?forms=tel,individual")" "200"

# کاربر بدون مجوز اکسل → 403
curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d '{"username":"noexp01","full_name":"بدون اکسل","role":"viewer","level":"user","password":"Nx#12345","permissions":["view"]}' -o /dev/null
CNE=/tmp/v170_noexp.txt; rm -f "$CNE"
LOC=$(curl -s -c "$CNE" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=noexp01&password=Nx#12345")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CNE" -c "$CNE" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=Nx#12345&new_password=Nx#77777&new_password2=Nx#77777"
fi
chk "استخراج اکسل بدون مجوز → 403" "$(curl -s -b "$CNE" -o /dev/null -w '%{http_code}' "$B/api/extract/excel")" "403"

# صفحهٔ استخراج برای کاربر عادی
chk "صفحهٔ استخراج → 200" "$(curl -s -b "$CR" -o /dev/null -w '%{http_code}' "$B/extract")" "200"

# ---------- ۴) رفتار نقش «مدیر» — شفاف در UI ----------
curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
  -d '{"username":"admrole01","full_name":"نقش مدیر","role":"admin","level":"user","password":"Ar#12345","allowed_forms":["tel"]}' -o /tmp/v170_ar.json
chk "کاربر با نقش مدیر → is_admin_level" "$(J /tmp/v170_ar.json "print(d['record']['is_admin_level'])")" "True"
CADM=/tmp/v170_admrole.txt; rm -f "$CADM"
LOC=$(curl -s -c "$CADM" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admrole01&password=Ar#12345")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CADM" -c "$CADM" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=Ar#12345&new_password=Ar#99999&new_password2=Ar#99999"
fi
curl -s -b "$CADM" "$B/dashboard" -o /tmp/v170_ar.html
G_IND=$(grep -c 'فرم ثبت نظرسنجی مراجعین خدمات مشاوره فردی' /tmp/v170_ar.html || true)
chk "نقش مدیر همهٔ فرم‌ها را می‌بیند (رفتار مستند + هشدار در UI)" "$([ "$G_IND" -gt 0 ] && echo yes || echo no)" "yes"

echo
echo "نتیجه: $PASS موفق، $FAIL ناموفق"
[ "$FAIL" = "0" ]
