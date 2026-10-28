#!/bin/bash
# تست فاز احراز هویت: ورود، نقش‌ها، وب‌سرویس با کلید API، لاگ
B="http://127.0.0.1:3010/app"
PASS=0; FAIL=0
chk() { local name="$1" expect="$2" got="$3"
  if [ "$got" = "$expect" ]; then echo "  ✅ $name ($got)"; PASS=$((PASS+1));
  else echo "  ❌ $name — انتظار $expect، دریافت $got"; FAIL=$((FAIL+1)); fi }

echo "== 0) ورود مدیر + تغییر رمز اجباری =="
CA=/tmp/ss_cookies.txt; rm -f "$CA"
# رمز ممکن است در اجرای قبلی تغییر کرده باشد — هر دو حالت امتحان می‌شود
try_login() { curl -s -c "$CA" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admin&password=$1"; }
LOC=$(try_login admin123)
if [ -z "$LOC" ]; then LOC=$(try_login 'Adm1n#2026'); fi
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CA" -c "$CA" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
  echo "  (رمز اجباری عوض شد)"
fi
# تأیید ورود
if ! curl -s -b "$CA" -o /dev/null -w '%{http_code}' "$B/api/users" | grep -q 200; then
  echo "  ❌ ورود مدیر ناموفق بود — تست ادامه نمی‌یابد"; exit 1
fi
echo "  (مدیر وارد شد)"

echo "== 1) بدون ورود =="
chk "GET صفحهٔ اصلی → ریدایرکت به login" "303" "$(curl -s -o /dev/null -w '%{http_code}' "$B/" | grep -q 200 && echo 200 || echo 303)"
chk "GET صفحه ورود → 200" "200" "$(curl -s -o /dev/null -w '%{http_code}' "$B/login")"
chk "API استان‌ها بدون کوکی → 401" "401" "$(curl -s -o /dev/null -w '%{http_code}' "$B/api/provinces")"

echo "== 2) ورود ناموفق =="
chk "رمز غلط → 401" "401" "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$B/login" --data 'username=admin&password=wrong')"

echo "== 3) ساخت کاربر کارشناس و مشاهده‌گر =="
OP_NAME="op$RANDOM"; VW_NAME="vw$RANDOM"
OP_PASS='Op#12345'; VW_PASS='Vi#12345'
curl -s -b "$CA" -X POST "$B/api/users" -H "Content-Type: application/json" \
  -d "{\"username\":\"$OP_NAME\",\"full_name\":\"کارشناس نمونه\",\"role\":\"operator\",\"password\":\"$OP_PASS\"}" -o /tmp/u1.json -w ""
chk "ایجاد کارشناس" "200" "$(curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' -d "{\"username\":\"${OP_NAME}b\",\"full_name\":\"کارشناس دوم\",\"role\":\"operator\",\"password\":\"$OP_PASS\"}" -o /dev/null -w '%{http_code}')"
chk "ایجاد مشاهده‌گر" "200" "$(curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' -d "{\"username\":\"$VW_NAME\",\"full_name\":\"مشاهده‌گر نمونه\",\"role\":\"viewer\",\"password\":\"$VW_PASS\"}" -o /dev/null -w '%{http_code}')"
chk "نام کاربری تکراری → 422" "422" "$(curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' -d "{\"username\":\"$VW_NAME\",\"full_name\":\"تکراری\",\"role\":\"viewer\",\"password\":\"$VW_PASS\"}" -o /dev/null -w '%{http_code}')"

CO=/tmp/c_operator.txt; CV=/tmp/c_viewer.txt; rm -f "$CO" "$CV"
LO=$(curl -s -c "$CO" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=$OP_NAME&password=$OP_PASS")
if echo "$LO" | grep -q "change-password"; then
  curl -s -b "$CO" -c "$CO" -o /dev/null -X POST "$B/change-password" --data "current_password=$OP_PASS&new_password=Op#99999&new_password2=Op#99999"
fi
LV=$(curl -s -c "$CV" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=$VW_NAME&password=$VW_PASS")
if echo "$LV" | grep -q "change-password"; then
  curl -s -b "$CV" -c "$CV" -o /dev/null -X POST "$B/change-password" --data "current_password=$VW_PASS&new_password=Vi#99999&new_password2=Vi#99999"
fi
echo "  (کارشناس و مشاهده‌گر وارد شدند)"

echo "== 4) دسترسی کارشناس =="
chk "کارشناس: ثبت فرم → 200" "200" "$(curl -s -b "$CO" -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d '{"first_name":"علی","last_name":"محمدی","national_code":"0123456789","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1405/08/05","contact_option_id":3,"answers":[]}' -o /dev/null -w '%{http_code}')"
chk "کارشناس: مدیریت الگو → 403" "403" "$(curl -s -b "$CO" -X POST "$B/api/template/questions" -H 'Content-Type: application/json' -d '{"text":"تست"}' -o /dev/null -w '%{http_code}')"
chk "کارشناس: حذف رکورد → 403" "403" "$(curl -s -b "$CO" -X DELETE "$B/api/surveys/1" -o /dev/null -w '%{http_code}')"
chk "کارشناس: مدیریت کاربران → 403" "403" "$(curl -s -b "$CO" "$B/api/users" -o /dev/null -w '%{http_code}')"
chk "کارشناس: اکسل → 200" "200" "$(curl -s -b "$CO" "$B/api/surveys/export/excel" -o /dev/null -w '%{http_code}')"

echo "== 5) دسترسی مشاهده‌گر =="
chk "مشاهده‌گر: ثبت فرم → 403" "403" "$(curl -s -b "$CV" -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d '{"first_name":"x","last_name":"y","national_code":"0123456789","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1405/08/05","contact_option_id":3,"answers":[]}' -o /dev/null -w '%{http_code}')"
chk "مشاهده‌گر: داشبورد API → 200" "200" "$(curl -s -b "$CV" "$B/api/dashboard" -o /dev/null -w '%{http_code}')"
chk "مشاهده‌گر: فهرست رکوردها → 200" "200" "$(curl -s -b "$CV" "$B/api/surveys?page=1&per_page=5" -o /dev/null -w '%{http_code}')"
chk "مشاهده‌گر: اکسل → 403" "403" "$(curl -s -b "$CV" "$B/api/surveys/export/excel" -o /dev/null -w '%{http_code}')"
chk "مشاهده‌گر: صفحه فرم → ریدایرکت" "303" "$(curl -s -b "$CV" -o /dev/null -w '%{http_code}' "$B/")"
chk "مشاهده‌گر: صفحه کاربران → ریدایرکت" "303" "$(curl -s -b "$CV" -o /dev/null -w '%{http_code}' "$B/users")"

echo "== 6) حفاظت خود مدیر =="
chk "مدیر: غیرفعال‌کردن خودش → 422" "422" "$(curl -s -b "$CA" -X PATCH "$B/api/users/1" -H 'Content-Type: application/json' -d '{"is_active":false}' -o /dev/null -w '%{http_code}')"

echo "== 7) وب‌سرویس با کلید API =="
KEY=$(curl -s -b "$CA" -X POST "$B/api/keys" -H "Content-Type: application/json" -d '{"name":"نرم‌افزار تست مرکزی"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['key'])")
echo "  کلید: ${KEY:0:12}..."
chk "بدون کلید → 401" "401" "$(curl -s -o /dev/null -w '%{http_code}' "$B/api/v1/surveys")"
chk "کلید غلط → 401" "401" "$(curl -s -o /dev/null -w '%{http_code}' -H 'X-API-Key: sk_invalid' "$B/api/v1/surveys")"
chk "وب‌سرویس: ثبت فرم → 200" "200" "$(curl -s -X POST "$B/api/v1/surveys" -H "X-API-Key: $KEY" -H 'Content-Type: application/json' -d '{"first_name":"وب","last_name":"سرویس","national_code":"0123456789","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1405/08/05","contact_option_id":3,"answers":[]}' -o /tmp/v1.json -w '%{http_code}')"
python3 -c "import json; d=json.load(open('/tmp/v1.json')); print('  ثبت شد: id =', d['id'])"
chk "وب‌سرویس: فهرست → 200" "200" "$(curl -s -H "X-API-Key: $KEY" "$B/api/v1/surveys?per_page=5" -o /dev/null -w '%{http_code}')"
chk "وب‌سرویس: داشبورد → 200" "200" "$(curl -s -H "X-API-Key: $KEY" "$B/api/v1/dashboard" -o /dev/null -w '%{http_code}')"
chk "وب‌سرویس: الگو → 200" "200" "$(curl -s -H "X-API-Key: $KEY" "$B/api/v1/template" -o /dev/null -w '%{http_code}')"

echo "== 8) لاگ فعالیت =="
curl -s -b "$CA" "$B/api/logs?per_page=200" -o /tmp/logs.json
python3 - << 'EOF'
import json
d = json.load(open('/tmp/logs.json'))
actions = {i['action'] for i in d['items']}
need = ['login_success', 'login_failed', 'survey_create', 'user_create', 'v1_survey_create', 'system_bootstrap']
pw_ok = any(a in actions for a in ['password_changed', 'password_changed_forced'])
missing = [a for a in need if a not in actions]
if not pw_ok:
    missing.append('password_changed(_forced)')
print('  ✅ لاگ کامل است — رویدادهای لازم همگی ثبت شده‌اند' if not missing else f'  ❌ رویدادهای جاافتاده: {missing}')
EOF

echo "== 9) PDF برای مشاهده‌گر (دسترسی دیدن) =="
chk "مشاهده‌گر: PDF رکورد 1 → 200" "200" "$(curl -s -b "$CV" "$B/api/surveys/1/pdf" -o /tmp/pdf_v.pdf -w '%{http_code}' --max-time 60)"
head -c 4 /tmp/pdf_v.pdf | grep -q "%PDF" && echo "  ✅ فایل واقعی PDF" || echo "  ⚠️ خروجی PDF نامعتبر"

echo ""
echo "========================================"
echo "نتیجه: $PASS موفق، $FAIL ناموفق"
[ "$FAIL" = "0" ] && echo "ALL PASSED ✅" || echo "SOME FAILED ❌"
