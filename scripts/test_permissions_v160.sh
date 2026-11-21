#!/bin/bash
# تست قابلیت‌های نسخهٔ 1.6.0:
#   ۱) دسترسی «فقط داده‌های خودش» (own_data) — آرشیو/جزئیات/داشبورد
#   ۲) «فرم‌های مجاز» هر کاربر — آرشیو/صفحهٔ ثبت/facets/خروجی اکسل
#   ۳) نقش‌های جدید (roles) — ساخت/ویرایش/حذف + تخصیص به کاربر
set -u
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
mkdir -p "$APP_DIR/logs"
VPY=/home/z/my-project/venv/bin/python3
export SURVEY_DATABASE_URL="sqlite:////$APP_DIR/data/test_v160.db"
export SURVEY_SELF_URL="http://127.0.0.1:3010"
LOG="$APP_DIR/logs/test-server.log"

rm -f data/test_v160.db
$VPY -c "
from app.database import Base, engine
import app.models  # noqa
Base.metadata.create_all(engine)
print('tables ok')"
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
chk() { local name="$1" expect="$2" got="$3"
  if [ "$got" = "$expect" ]; then echo "  ✅ $name ($got)"; PASS=$((PASS+1));
  else echo "  ❌ $name — انتظار $expect، دریافت $got"; FAIL=$((FAIL+1)); fi }
J() { $VPY -c "import json,sys; d=json.load(open('$1')); $2"; }

login() { # login user pass cookiefile
  local C="$3"; rm -f "$C"
  local L=$(curl -s -c "$C" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=$1&password=$2")
  if echo "$L" | grep -q "change-password"; then
    curl -s -b "$C" -c "$C" -o /dev/null -X POST "$B/change-password" \
      --data "current_password=$2&new_password=Nw#99111&new_password2=Nw#99111"
  fi
}

# ---------- ورود مدیر ----------
CA=/tmp/v160_admin.txt; rm -f "$CA"
LOC=$(curl -s -c "$CA" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admin&password=admin123")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CA" -c "$CA" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
fi
chk "مدیر وارد شد" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' "$B/api/users")"

# ---------- ۱) نقش‌های سفارشی ----------
curl -s -b "$CA" "$B/api/roles" -o /tmp/v160_roles0.json
chk "فهرست نقش‌ها = ۶ نقش سیستمی" "6" "$(J /tmp/v160_roles0.json 'print(len(d))')"
curl -s -b "$CA" -X POST "$B/api/roles" -H 'Content-Type: application/json' \
  -d '{"name":"کارشناس تلفنی","description":"فقط فرم تلفنی","level":"user","permissions":["view","export"]}' \
  -o /tmp/v160_role.json
RKEY=$(J /tmp/v160_role.json "print(d['record']['key'])")
RID=$(J /tmp/v160_role.json "print(d['record']['id'])")
if echo "$RKEY" | grep -q "^role_"; then chk "نقش جدید با کلید خودکار ساخته شد" "ok" "ok"; PASS=$((PASS+1)); else echo "  ❌ کلید نقش سفارشی غلط: $RKEY"; FAIL=$((FAIL+1)); fi
chk "نقش تکراری → 422" "422" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X POST "$B/api/roles" -H 'Content-Type: application/json' -d '{"name":"کارشناس تلفنی","level":"user"}')"
chk "حذف نقش سیستمی → 422" "422" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X DELETE "$B/api/roles/1")"
chk "ویرایش دسترسی نقش سفارشی → 200" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X PATCH "$B/api/roles/$RID" -H 'Content-Type: application/json' -d '{"permissions":["view","export","print"]}')"
# نقش سفارشی بلااستفاده برای تست حذف
curl -s -b "$CA" -X POST "$B/api/roles" -H 'Content-Type: application/json' \
  -d '{"name":"موقت حذف","level":"user","permissions":["view"]}' -o /tmp/v160_role_tmp.json
RTMP=$(J /tmp/v160_role_tmp.json "print(d['record']['id'])")
chk "حذف نقش سفارشی بلااستفاده → 200" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X DELETE "$B/api/roles/$RTMP")"

# ---------- ساخت کاربران ----------
CU=/tmp/v160_u.json
mku() { curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' -d "$1" -o "$CU"; J "$CU" "print(d['record']['id'])"; }
UOWN_ID=$(mku '{"username":"vown'$RANDOM'","full_name":"داده‌های خودش","role":"viewer","level":"user","password":"Ow#12345","permissions":["view","own_data"]}')
UOWN=$(J "$CU" "print(d['record']['username'])")
UFORM_ID=$(mku '{"username":"uform'$RANDOM'","full_name":"فقط تلفنی","role":"operator","level":"user","password":"Fm#12345","allowed_forms":["tel"]}')
UFORM=$(J "$CU" "print(d['record']['username'])")
UCUST_ID=$(mku "{\"username\":\"ucust$RANDOM\",\"full_name\":\"کارشناس تلفنی\",\"role\":\"$RKEY\",\"level\":\"user\",\"password\":\"Cu#12345\"}")
UCUST=$(J "$CU" "print(d['record']['username'])")
chk "کاربر با نقش سفارشی ساخته شد" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' "$B/api/users")"

# ---------- ۲) رکوردهای نمونه (مستقیم در دیتابیس) ----------
$VPY - <<PY
from app.database import SessionLocal
from app.models import Survey
import datetime as dt
db = SessionLocal()
def add(fn, ln, nc, form, cb, counselor):
    db.add(Survey(first_name=fn, last_name=ln, national_code=nc, phone="0912000000",
                  province_id=1, county_id=1, survey_date=dt.date(2025, 1, 1),
                  form_key=form, created_by=cb, counselor=counselor))
add("علی", "مدیرساخت", "0011111111", "tel", 1, "مشاور تلفنی")          # A — رکورد مدیر
add("مریم", "خودش", "0022222222", "tel", $UOWN_ID, "مشاور تلفنی")       # B — رکورد خودش
add("رضا", "خودش_فردی", "0033333333", "individual", $UOWN_ID, "مشاور گروهی")  # C — رکورد خودش از فرم دیگر
add("قدیمی", "بدون‌مالک", "0044444444", "tel", None, "مشاور قدیمی")     # D — رکورد قدیمی بدون ثبت‌کننده
db.commit()
print("seeded 4 surveys")
PY

login "$UOWN" 'Ow#12345' /tmp/v160_own.txt
login "$UFORM" 'Fm#12345' /tmp/v160_form.txt
login "$UCUST" 'Cu#12345' /tmp/v160_cust.txt

# ---------- ۳) «فقط داده‌های خودش» ----------
curl -s -b "$CA" "$B/api/surveys?per_page=100" -o /tmp/v160_l_admin.json
chk "مدیر همهٔ ۴ رکورد را می‌بیند" "4" "$(J /tmp/v160_l_admin.json 'print(d["total"])')"
curl -s -b /tmp/v160_own.txt "$B/api/surveys?per_page=100" -o /tmp/v160_l_own.json
chk "own_data: فقط رکوردهای خودش + قدیمی‌ها (۳)" "3" "$(J /tmp/v160_l_own.json 'print(d["total"])')"
chk "own_data: رکورد مدیر در فهرستش نیست" "False" "$(J /tmp/v160_l_own.json "print(any(i['id']==1 for i in d['items']))")"
chk "own_data: GET رکورد مدیر → 403" "403" "$(curl -s -b /tmp/v160_own.txt -o /dev/null -w '%{http_code}' "$B/api/surveys/1")"
chk "own_data: GET رکورد خودش → 200" "200" "$(curl -s -b /tmp/v160_own.txt -o /dev/null -w '%{http_code}' "$B/api/surveys/3")"
chk "own_data: ویرایش رکورد مدیر → 403" "403" "$(curl -s -b /tmp/v160_own.txt -o /dev/null -w '%{http_code}' -X PATCH "$B/api/surveys/1" -H 'Content-Type: application/json' -d '{"form_key":"tel"}')"
curl -s -b /tmp/v160_own.txt "$B/api/dashboard" -o /tmp/v160_d_own.json
chk "own_data: داشبورد فقط داده‌های خودش (۳)" "3" "$(J /tmp/v160_d_own.json 'print(d["total"])')"

# ---------- ۴) فرم‌های مجاز ----------
curl -s -b /tmp/v160_form.txt "$B/api/surveys?per_page=100" -o /tmp/v160_l_form.json
chk "فرم مجاز: فقط رکوردهای تلفنی (۳)" "3" "$(J /tmp/v160_l_form.json 'print(d["total"])')"
chk "فرم مجاز: فیلتر individual → ۰" "0" "$(curl -s -b /tmp/v160_form.txt "$B/api/surveys?form=individual" | $VPY -c "import json,sys; print(json.load(sys.stdin)['total'])")"
NC1=$(/home/z/my-project/venv/bin/python3 -c "from app.utils.national_code import make_valid_national_code; print(make_valid_national_code('112345678'))")
NC2=$(/home/z/my-project/venv/bin/python3 -c "from app.utils.national_code import make_valid_national_code; print(make_valid_national_code('223456789'))")
# فرم غیرمجاز: حتی با payload ساده، 403 قبل از اعتبارسنجی برمی‌گردد
chk "فرم مجاز: ثبت فردی → 403" "403" "$(curl -s -b /tmp/v160_form.txt -o /dev/null -w '%{http_code}' -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d '{"form_key":"individual","first_name":"تست","last_name":"تست","national_code":"'$NC1'","phone":"09120009999","province_id":1,"county_id":1,"survey_date":"1404/01/01"}')"
# فرم مجاز با payload کامل (سؤال‌ها و وضعیت تماس از الگوی همان فرم)
curl -s -b /tmp/v160_form.txt "$B/api/template/questions?form=tel" -o /tmp/v160_q.json
curl -s -b /tmp/v160_form.txt "$B/api/template/contact-options?form=tel" -o /tmp/v160_c.json
/home/z/my-project/venv/bin/python3 - <<'PY'
import json
qs = [q for q in json.load(open("/tmp/v160_q.json")) if q["is_active"]]
cs = [c for c in json.load(open("/tmp/v160_c.json")) if c["is_active"]]
req = next((c for c in cs if c["requires_answers"]), cs[0])
payload = {
    "form_key": "tel", "first_name": "تست", "last_name": "تست",
    "national_code": "placeholder", "phone": "09120008888",
    "province_id": 1, "county_id": 1, "survey_date": "1404/01/01",
    "contact_option_id": req["id"],
    "answers": [{"question_id": q["id"], "value": "زیاد"} for q in qs],
    "counselor": "مشاور تست", "service_type": "خدمت تست", "service_date": "1404/01/01",
}
json.dump(payload, open("/tmp/v160_payload.json", "w"), ensure_ascii=False)
PY
sed -i "s/\"national_code\": \"placeholder\"/\"national_code\": \"$NC2\"/" /tmp/v160_payload.json
chk "فرم مجاز: ثبت تلفنی → 200" "200" "$(curl -s -b /tmp/v160_form.txt -o /dev/null -w '%{http_code}' -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d @/tmp/v160_payload.json)"
chk "فرم مجاز: صفحهٔ ثبت فردی → 403" "403" "$(curl -s -b /tmp/v160_form.txt -o /dev/null -w '%{http_code}' "$B/form/individual")"
chk "فرم مجاز: صفحهٔ ثبت تلفنی → 200" "200" "$(curl -s -b /tmp/v160_form.txt -o /dev/null -w '%{http_code}' "$B/form/tel")"
curl -s -b /tmp/v160_form.txt "$B/records" -o /tmp/v160_records.html
if grep -q "window.__FORMS__" /tmp/v160_records.html && ! grep '__FORMS__' /tmp/v160_records.html | grep -q '"individual"'; then
  chk "منوی/فیلتر فرم‌ها فقط تلفنی است" "ok" "ok"; PASS=$((PASS+1));
else echo "  ❌ __FORMS__ باید فقط tel باشد"; FAIL=$((FAIL+1)); fi
chk "فرم مجاز: facets بدون مشاور فردی" "False" "$(curl -s -b /tmp/v160_form.txt "$B/api/surveys/facets" | $VPY -c "import json,sys; print('مشاور گروهی' in json.load(sys.stdin)['counselors'])")"
chk "فرم مجاز: اکسل → 200" "200" "$(curl -s -b /tmp/v160_form.txt -o /dev/null -w '%{http_code}' "$B/api/surveys/export/excel")"

# ---------- ۵) نقش سفارشی روی کاربر ----------
chk "کاربر نقش سفارشی: ثبت → 403 (دسترسی ثبت ندارد)" "403" "$(curl -s -b /tmp/v160_cust.txt -o /dev/null -w '%{http_code}' -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d '{"form_key":"tel","first_name":"ت","last_name":"ت","national_code":"0077777777","phone":"09120007777","province_id":1,"county_id":1,"survey_date":"1404/01/01"}')"
curl -s -b "$CA" "$B/api/users" -o /tmp/v160_users.json
chk "برچسب نقش سفارشی درست است" "True" "$(J /tmp/v160_users.json "print(any(u['id']==$UCUST_ID and u['role_label']=='کارشناس تلفنی' for u in d))")"
chk "دسترسی‌های نقش سفارشی اعمال شد" "True" "$(J /tmp/v160_users.json "print(any(u['id']==$UCUST_ID and set(u['effective_permissions'])=={'view','export','print'} for u in d))")"

# نقش سفارشیِ در حال استفاده → حذف 422
chk "حذف نقشِ در حال استفاده → 422" "422" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X DELETE "$B/api/roles/$RID")"

# ---------- ۶) صفحه‌های مدیریتی ----------
chk "صفحهٔ نقش‌ها برای مدیر → 200" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' "$B/roles")"
chk "صفحهٔ نقش‌ها برای غیرمدیر → 303" "303" "$(curl -s -b /tmp/v160_form.txt -o /dev/null -w '%{http_code}' "$B/roles")"

echo "-------------------------------------"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = "0" ]
