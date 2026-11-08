#!/bin/bash
# تست سطوح کاربری، نقش‌ها، سطوح دسترسی، خروجی اکسل و ستون‌های جدید
# (پیش‌نیاز: سرور تست با دیتابیس تازه بالا باشد — مثل run_auth_tests_once.sh)
B="http://127.0.0.1:3010/app"
PASS=0; FAIL=0
chk() { local name="$1" expect="$2" got="$3"
  if [ "$got" = "$expect" ]; then echo "  ✅ $name ($got)"; PASS=$((PASS+1));
  else echo "  ❌ $name — انتظار $expect، دریافت $got"; FAIL=$((FAIL+1)); fi }

J() { python3 -c "import json,sys; d=json.load(open('$1')); $2"; }

# ---------- ورود مدیر ----------
CA=/tmp/rbac_admin.txt; rm -f "$CA"
try_login() { curl -s -c "$CA" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admin&password=$1"; }
LOC=$(try_login admin123)
if [ -z "$LOC" ]; then LOC=$(try_login 'Adm1n#2026'); fi
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$CA" -c "$CA" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
fi
chk "مدیر وارد شد" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' "$B/api/users")"

echo "== 1) متادیتای نقش‌ها و دسترسی‌ها =="
curl -s -b "$CA" "$B/api/users/meta" -o /tmp/rbac_meta.json
chk "تعداد نقش‌ها = ۶" "6" "$(J /tmp/rbac_meta.json "print(len(d['roles']))")"
chk "تعداد سطوح کاربری = ۲" "2" "$(J /tmp/rbac_meta.json "print(len(d['levels']))")"
chk "تعداد سطوح دسترسی = ۵" "5" "$(J /tmp/rbac_meta.json "print(len(d['permissions']))")"

echo "== 2) ساخت کاربران با نقش‌ها و سطح‌های مختلف =="
mk() { # mk name role level perms pass
  curl -s -b "$CA" -X POST "$B/api/users" -H 'Content-Type: application/json' \
    -d "{\"username\":\"$1$RANDOM\",\"full_name\":\"$1\",\"role\":\"$2\",\"level\":\"$3\",\"password\":\"$5\"}" \
    -o /tmp/rbac_u.json
  U=$(J /tmp/rbac_u.json "print(d['record']['username'])")
  if [ -n "$4" ]; then
    curl -s -b "$CA" -X PATCH "$B/api/users/$(J /tmp/rbac_u.json "print(d['record']['id'])")" \
      -H 'Content-Type: application/json' -d "{\"permissions\":$4}" -o /tmp/rbac_u.json
  fi
  echo "$U"
}
DE=$(mk "de" "data_entry" "user" "" 'De#12345')
SUP=$(mk "sup" "supervisor" "user" "" 'Su#12345')
REP=$(mk "rep" "reporter" "user" "" 'Rp#12345')
VW2=$(mk "vw" "viewer" "user" "" 'Vw#12345')
AD2=$(mk "ad" "admin" "admin" "" 'Ad2#12345')
chk "نقش ورود داده ساخته شد" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X POST "$B/api/users" -H 'Content-Type: application/json' -d "{\"username\":\"de2$RANDOM\",\"role\":\"data_entry\",\"password\":\"De#12345\"}")"
chk "سطح نامعتبر → 422" "422" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X POST "$B/api/users" -H 'Content-Type: application/json' -d "{\"username\":\"bad$RANDOM\",\"role\":\"viewer\",\"level\":\"boss\",\"password\":\"Bd#12345\"}")"
chk "دسترسی نامعتبر → 422" "422" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X PATCH "$B/api/users/3" -H 'Content-Type: application/json' -d '{"permissions":["fly"]}')" 2>/dev/null

login() { # login user pass cookiefile
  local C="$3"; rm -f "$C"
  local L=$(curl -s -c "$C" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=$1&password=$2")
  if echo "$L" | grep -q "change-password"; then
    curl -s -b "$C" -c "$C" -o /dev/null -X POST "$B/change-password" \
      --data "current_password=$2&new_password=New#99111&new_password2=New#99111"
  fi
}
login "$DE" 'De#12345' /tmp/rbac_de.txt
login "$SUP" 'Su#12345' /tmp/rbac_sup.txt
login "$REP" 'Rp#12345' /tmp/rbac_rep.txt
login "$VW2" 'Vw#12345' /tmp/rbac_vw.txt
login "$AD2" 'Ad2#12345' /tmp/rbac_ad2.txt

echo "== 3) نقش ورود داده: ثبت دارد، اکسل/حذف ندارد =="
chk "ورود داده: ثبت فرم → 200" "200" "$(curl -s -b /tmp/rbac_de.txt -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d '{"first_name":"ورود","last_name":"داده","national_code":"0123456789","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1405/08/05","contact_option_id":3,"answers":[],"counselor":"مشاور تست"}' -o /dev/null -w '%{http_code}')"
chk "ورود داده: اکسل → 403" "403" "$(curl -s -b /tmp/rbac_de.txt "$B/api/surveys/export/excel" -o /dev/null -w '%{http_code}')"
chk "ورود داده: حذف رکورد ۱ → 403" "403" "$(curl -s -b /tmp/rbac_de.txt -X DELETE "$B/api/surveys/1" -o /dev/null -w '%{http_code}')"

echo "== 4) نقش گزارش‌گیر: اکسل و چاپ دارد، ثبت ندارد =="
chk "گزارش‌گیر: ثبت فرم → 403" "403" "$(curl -s -b /tmp/rbac_rep.txt -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d '{"first_name":"گ","last_name":"ر","national_code":"0123456789","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1405/08/05","contact_option_id":3,"answers":[]}' -o /dev/null -w '%{http_code}')"
chk "گزارش‌گیر: اکسل → 200" "200" "$(curl -s -b /tmp/rbac_rep.txt "$B/api/surveys/export/excel" -o /tmp/rbac.xlsx -w '%{http_code}')"
python3 -c "
from openpyxl import load_workbook
wb = load_workbook('/tmp/rbac.xlsx')
ws = wb.active
heads = [c.value for c in ws[2]]
need = ['مشاور', 'نوع خدمت', 'تاریخ دریافت خدمت (شمسی)', 'نقاط قوت مشاوره تلفنی', 'پیشنهاد بهبود', 'کارشناس نظارت حرفه‌ای']
missing = [h for h in need if h not in heads]
print('  ✅ ستون‌های فیلدهای جدید در اکسل هست' if not missing else f'  ❌ ستون‌های جاافتاده: {missing}')"
chk "گزارش‌گیر: کاربران → 403" "403" "$(curl -s -b /tmp/rbac_rep.txt "$B/api/users" -o /dev/null -w '%{http_code}')"

echo "== 5) سطح مدیر سامانه (کاربر دوم) =="
chk "مدیر دوم: کاربران → 200" "200" "$(curl -s -b /tmp/rbac_ad2.txt "$B/api/users" -o /dev/null -w '%{http_code}')"
chk "مدیر دوم: حذف رکورد → 200" "200" "$(curl -s -b /tmp/rbac_ad2.txt -X DELETE "$B/api/surveys/1" -o /dev/null -w '%{http_code}')"
AD2_ID=$(J /tmp/rbac_u.json "print(d['record']['id'])")
chk "غیرفعال‌کردن مدیر دوم (مدیر اول فعال است) → 200" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X PATCH "$B/api/users/$AD2_ID" -H 'Content-Type: application/json' -d '{"is_active":false}')"
chk "تنزل سطح مدیر دوم → 200" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X PATCH "$B/api/users/$AD2_ID" -H 'Content-Type: application/json' -d '{"level":"user","role":"viewer"}')"
chk "فعال‌کردن دوباره مدیر دوم → 200" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X PATCH "$B/api/users/$AD2_ID" -H 'Content-Type: application/json' -d '{"is_active":true}')"

echo "== 6) دسترسی سفارشی: به مشاهده‌گر، اکسل بده =="
VW2_ID=$(curl -s -b "$CA" "$B/api/users" -o /tmp/rbac_list.json; J /tmp/rbac_list.json "print([u['id'] for u in d if u['username']=='$VW2'][0])")
chk "دادن دسترسی اکسل به مشاهده‌گر → 200" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X PATCH "$B/api/users/$VW2_ID" -H 'Content-Type: application/json' -d '{"permissions":["view","export"]}')"
chk "مشاهده‌گر با اکسل: خروجی → 200" "200" "$(curl -s -b /tmp/rbac_vw.txt "$B/api/surveys/export/excel" -o /dev/null -w '%{http_code}')"
chk "مشاهده‌گر با اکسل: ثبت هنوز → 403" "403" "$(curl -s -b /tmp/rbac_vw.txt -X POST "$B/api/surveys" -H 'Content-Type: application/json' -d '{"first_name":"x","last_name":"y","national_code":"0123456789","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1405/08/05","contact_option_id":3,"answers":[]}' -o /dev/null -w '%{http_code}')"
chk "پس‌گرفتن اکسل مشاهده‌گر → 200" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' -X PATCH "$B/api/users/$VW2_ID" -H 'Content-Type: application/json' -d '{"permissions":["view"]}')"
chk "مشاهده‌گر بدون اکسل: خروجی → 403" "403" "$(curl -s -b /tmp/rbac_vw.txt "$B/api/surveys/export/excel" -o /dev/null -w '%{http_code}')"

echo "== 7) صفحهٔ مدیریت کاربران =="
chk "صفحه کاربران برای مدیر → 200" "200" "$(curl -s -b "$CA" -o /dev/null -w '%{http_code}' "$B/users")"
chk "صفحه کاربران برای کارشناس → 303" "303" "$(curl -s -b /tmp/rbac_sup.txt -o /dev/null -w '%{http_code}' "$B/users")"

echo ""
echo "========================================"
echo "نتیجه RBAC: $PASS موفق، $FAIL ناموفق"
[ "$FAIL" = "0" ] && echo "ALL PASSED ✅" || echo "SOME FAILED ❌"
exit $FAIL
