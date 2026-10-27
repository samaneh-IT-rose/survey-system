#!/bin/bash
B="http://127.0.0.1:3030/app/api"
J() { python3 -c "import json,sys; d=json.load(sys.stdin); $1"; }

echo "== 1) ثبت فرم معتبر (با ارقام فارسی) =="
curl -s -X POST "$B/surveys" -H "Content-Type: application/json" -d '{
  "first_name": "زهرا", "last_name": "کریمی",
  "national_code": "۰۱۲۳۴۵۶۷۸۹", "phone": "۰۹۱۲۳۴۵۶۷۸۹",
  "province_id": 8, "county_id": 96,
  "survey_date": "۱۴۰۵/۰۸/۰۵",
  "contact_option_id": 1,
  "answers": [{"question_id":1,"value":"خیلی زیاد"},{"question_id":2,"value":"زیاد"},{"question_id":3,"value":"متوسط"},{"question_id":4,"value":"خیلی زیاد"},{"question_id":5,"value":"زیاد"},{"question_id":6,"value":"خیلی زیاد"}]
}' | J "print('id:', d['id'], '| code:', d['record']['national_code'], '| date:', d['record']['survey_date_jalali'])"

echo "== 2) کد ملی نامعتبر =="
curl -s -X POST "$B/surveys" -H "Content-Type: application/json" -d '{"first_name":"تست","last_name":"تستی","national_code":"1234567890","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1405/08/05","contact_option_id":1,"answers":[]}' -o /tmp/t2.bin -w "HTTP %{http_code} (انتظار 422)\n"

echo "== 3) شهرستان ناهمخوان با استان (درخواست مستقیم) =="
curl -s -X POST "$B/surveys" -H "Content-Type: application/json" -d '{"first_name":"تست","last_name":"تستی","national_code":"0123456789","phone":"09123456789","province_id":1,"county_id":96,"survey_date":"1405/08/05","contact_option_id":1,"answers":[]}' | J "print('errors:', d['detail']['errors'])"

echo "== 4) تاریخ نامعتبر (۳۰ اسفند سال غیرکبیسه ۱۴۰۴) =="
curl -s -X POST "$B/surveys" -H "Content-Type: application/json" -d '{"first_name":"تست","last_name":"تستی","national_code":"0123456789","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1404/12/30","contact_option_id":1,"answers":[]}' | J "print('errors:', d['detail']['errors'].get('survey_date'))"

echo "== 5) پاسخ ناقص با وضعیت تماس الزامی =="
curl -s -X POST "$B/surveys" -H "Content-Type: application/json" -d '{"first_name":"تست","last_name":"تستی","national_code":"0123456789","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1405/08/05","contact_option_id":1,"answers":[{"question_id":1,"value":"زیاد"}]}' | J "print('errors:', d['detail']['errors'].get('answers'))"

echo "== 6) وضعیت تماس بدون نیاز به جدول + بدون پاسخ =="
curl -s -X POST "$B/surveys" -H "Content-Type: application/json" -d '{"first_name":"تست","last_name":"تستی","national_code":"0123456789","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1405/08/05","contact_option_id":3,"answers":[]}' | J "print('id:', d['id'], '| answers:', len(d['record']['answers']), '| contact:', d['record']['contact_option']['text'])"

echo "== 7) ویرایش رکورد 1 =="
curl -s -X PATCH "$B/surveys/1" -H "Content-Type: application/json" -d '{"first_name":"زهرا","last_name":"کریمی‌نژاد","national_code":"0123456789","phone":"09123456789","province_id":8,"county_id":96,"survey_date":"1405/08/01","contact_option_id":1,"answers":[{"question_id":1,"value":"خیلی کم"},{"question_id":2,"value":"کم"},{"question_id":3,"value":"متوسط"},{"question_id":4,"value":"زیاد"},{"question_id":5,"value":"خیلی زیاد"},{"question_id":6,"value":"زیاد"}]}' | J "print('message:', d['message'], '| last:', d['record']['last_name'], '| a1:', d['record']['answers'][0]['value'])"

echo "== 8) داشبورد =="
curl -s "$B/dashboard" | J "print('total:', d['total'], '| completed:', d['completed'], '| rate:', d['completion_rate'], '| provinces:', len(d['by_province']), '| days:', len(d['by_day']))"

echo "== 9) خروجی اکسل =="
curl -s "$B/surveys/export/excel" -o /tmp/excel_test.xlsx -w "HTTP %{http_code}, " && du -h /tmp/excel_test.xlsx | cut -f1

echo "== 10) PDF رکورد 1 =="
curl -s "$B/surveys/1/pdf" -o /tmp/pdf_test.pdf -w "HTTP %{http_code}, " && du -h /tmp/pdf_test.pdf | cut -f1 && python3 -c "
import re
data = open('/tmp/pdf_test.pdf','rb').read()
m = re.findall(rb'/Type\s*/Page[^s]', data)
print('pages:', len(m))"
