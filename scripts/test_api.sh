#!/bin/bash
# تست‌های ۱۰ سناریوی اصلی — اکنون با ورود مدیر (فاز احراز هویت)
B="http://127.0.0.1:3010/app"
J() { python3 -c "import json,sys; d=json.load(sys.stdin); $1"; }

# ---------- ورود مدیر ----------
C=/tmp/ss_cookies.txt; rm -f "$C"
LOC=$(curl -s -c "$C" -o /dev/null -w "%{redirect_url}" -X POST "$B/login" --data "username=admin&password=admin123")
if echo "$LOC" | grep -q "change-password"; then
  curl -s -b "$C" -c "$C" -o /dev/null -X POST "$B/change-password" \
    --data "current_password=admin123&new_password=Adm1n#2026&new_password2=Adm1n#2026"
  echo "(رمز مدیر در این دیتابیس تازه تغییر یافت)"
fi

# استان/شهرستان/وضعیت تماس با جست‌وجوی نام — ترتیب فهرست رسمی ثابت نیست (نسخهٔ 1.9.0)
PID_T=$(curl -s -b "$C" "$B/api/provinces" | python3 -c "import json,sys; print([p['id'] for p in json.load(sys.stdin) if p['name']=='تهران'][0])")
CNTY_T=$(curl -s -b "$C" "$B/api/counties?province_id=$PID_T" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
CT_REQ=$(curl -s -b "$C" "$B/api/template/contact-options?form=individual" | python3 -c "import json,sys; d=json.load(sys.stdin); c=[x for x in d if x['requires_answers']]; print(c[0]['id'] if c else d[0]['id'])")
CT_FREE=$(curl -s -b "$C" "$B/api/template/contact-options?form=individual" | python3 -c "import json,sys; d=json.load(sys.stdin); c=[x for x in d if not x['requires_answers']]; print(c[0]['id'] if c else d[0]['id'])")

echo "== 1) ثبت فرم معتبر (با ارقام فارسی) =="
curl -s -b "$C" -X POST "$B/api/surveys" -H "Content-Type: application/json" -d "{
  \"first_name\": \"زهرا\", \"last_name\": \"کریمی\",
  \"national_code\": \"۰۱۲۳۴۵۶۷۸۹\", \"phone\": \"۰۹۱۲۳۴۵۶۷۸۹\",
  \"province_id\": $PID_T, \"county_id\": $CNTY_T,
  \"survey_date\": \"۱۴۰۵/۰۸/۰۵\",
  \"form_key\": \"individual\",
  \"contact_option_id\": $CT_REQ,
  \"answers\": [{\"question_id\":1,\"value\":\"خیلی زیاد\"},{\"question_id\":2,\"value\":\"زیاد\"},{\"question_id\":3,\"value\":\"متوسط\"},{\"question_id\":4,\"value\":\"خیلی زیاد\"},{\"question_id\":5,\"value\":\"زیاد\"},{\"question_id\":6,\"value\":\"خیلی زیاد\"},{\"question_id\":7,\"value\":\"خیلی زیاد\"},{\"question_id\":8,\"value\":\"زیاد\"},{\"question_id\":9,\"value\":\"متوسط\"}]
}" | J "print('id:', d['id'], '| code:', d['record']['national_code'], '| date:', d['record']['survey_date_jalali'])"

echo "== 2) کد ملی نامعتبر =="
curl -s -b "$C" -X POST "$B/api/surveys" -H "Content-Type: application/json" -d '{"first_name":"تست","last_name":"تستی","national_code":"1234567890","phone":"09123456789","province_id":'"$PID_T"',"county_id":'"$CNTY_T"',"survey_date":"1405/08/05","contact_option_id":'"$CT_REQ"',"answers":[],"form_key":"individual"}' -o /tmp/t2.bin -w "HTTP %{http_code} (انتظار 422)\n"

echo "== 3) شهرستان ناهمخوان با استان (درخواست مستقیم) =="
curl -s -b "$C" -X POST "$B/api/surveys" -H "Content-Type: application/json" -d '{"first_name":"تست","last_name":"تستی","national_code":"0123456789","phone":"09123456789","province_id":1,"county_id":'"$CNTY_T"',"survey_date":"1405/08/05","contact_option_id":'"$CT_REQ"',"answers":[],"form_key":"individual"}' | J "print('errors:', d['detail']['errors'])"

echo "== 4) تاریخ نامعتبر (۳۰ اسفند سال غیرکبیسه ۱۴۰۴) =="
curl -s -b "$C" -X POST "$B/api/surveys" -H "Content-Type: application/json" -d '{"first_name":"تست","last_name":"تستی","national_code":"0123456789","phone":"09123456789","province_id":'"$PID_T"',"county_id":'"$CNTY_T"',"survey_date":"1404/12/30","contact_option_id":'"$CT_REQ"',"answers":[],"form_key":"individual"}' | J "print('errors:', d['detail']['errors'].get('survey_date'))"

echo "== 5) پاسخ ناقص با وضعیت تماس الزامی =="
curl -s -b "$C" -X POST "$B/api/surveys" -H "Content-Type: application/json" -d '{"first_name":"تست","last_name":"تستی","national_code":"0123456789","phone":"09123456789","province_id":'"$PID_T"',"county_id":'"$CNTY_T"',"survey_date":"1405/08/05","contact_option_id":'"$CT_REQ"',"answers":[{"question_id":1,"value":"زیاد"}],"form_key":"individual"}' | J "print('errors:', d['detail']['errors'].get('answers'))"

echo "== 6) وضعیت تماس بدون نیاز به جدول + بدون پاسخ =="
curl -s -b "$C" -X POST "$B/api/surveys" -H "Content-Type: application/json" -d '{"first_name":"تست","last_name":"تستی","national_code":"0123456789","phone":"09123456789","province_id":'"$PID_T"',"county_id":'"$CNTY_T"',"survey_date":"1405/08/05","contact_option_id":'"$CT_FREE"',"answers":[],"form_key":"individual"}' | J "print('id:', d['id'], '| answers:', len(d['record']['answers']), '| contact:', d['record']['contact_option']['text'])"

echo "== 7) ویرایش رکورد 1 =="
curl -s -b "$C" -X PATCH "$B/api/surveys/1" -H "Content-Type: application/json" -d '{"first_name":"زهرا","last_name":"کریمی‌نژاد","national_code":"0123456789","phone":"09123456789","province_id":'"$PID_T"',"county_id":'"$CNTY_T"',"survey_date":"1405/08/01","contact_option_id":'"$CT_REQ"',"answers":[{"question_id":1,"value":"خیلی کم"},{"question_id":2,"value":"کم"},{"question_id":3,"value":"متوسط"},{"question_id":4,"value":"زیاد"},{"question_id":5,"value":"خیلی زیاد"},{"question_id":6,"value":"زیاد"},{"question_id":7,"value":"زیاد"},{"question_id":8,"value":"خیلی زیاد"},{"question_id":9,"value":"خیلی کم"}]}' | J "print('message:', d['message'], '| last:', d['record']['last_name'], '| a1:', d['record']['answers'][0]['value'])"

echo "== 8) داشبورد =="
curl -s -b "$C" "$B/api/dashboard" | J "print('total:', d['total'], '| completed:', d['completed'], '| rate:', d['completion_rate'], '| provinces:', len(d['by_province']), '| days:', len(d['by_day']))"

echo "== 9) خروجی اکسل =="
curl -s -b "$C" "$B/api/surveys/export/excel" -o /tmp/excel_test.xlsx -w "HTTP %{http_code}, " && du -h /tmp/excel_test.xlsx | cut -f1

echo "== 10) PDF رکورد 1 =="
curl -s -b "$C" "$B/api/surveys/1/pdf" -o /tmp/pdf_test.pdf -w "HTTP %{http_code}, " && du -h /tmp/pdf_test.pdf | cut -f1 && python3 -c "
import re
data = open('/tmp/pdf_test.pdf','rb').read()
m = re.findall(rb'/Type\s*/Page[^s]', data)
print('pages:', len(m))"
