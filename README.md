# سامانه فرم نظرسنجی تلفنی — راه زندگی

سامانه وب فارسی (راست‌به‌چپ) برای ثبت، ویرایش، گزارش‌گیری و تحلیل فرم‌های نظرسنجی تلفنی.

**بک‌اند:** Python + FastAPI · **دیتابیس:** PostgreSQL · **رابط کاربری:** HTML/CSS/JS (RTL، قالب‌های Jinja2) · **نمودارها:** Apache ECharts (میزبانی محلی) · **PDF:** Playwright/Chromium

| فرم | داشبورد | چاپ/PDF |
|---|---|---|
| ![فرم](docs/screenshots/shot_form.png) | ![داشبورد](docs/screenshots/shot_dashboard.png) | ![چاپ](docs/screenshots/shot_print.png) |

---

## امکانات

| قابلیت | توضیح |
|---|---|
| ثبت فرم | فرم فارسی واکنش‌گرا با اعتبارسنجی سمت مرورگر **و** سرور |
| ویرایش رکورد | بازکردن رکورد ذخیره‌شده با `?id=شماره` و ویرایش امن |
| آرشیو | جست‌وجو (نام/کد ملی/تلفن)، فیلتر استان/شهرستان/وضعیت تماس/بازه تاریخ شمسی، صفحه‌بندی |
| خروجی اکسل | فایل XLSX راست‌به‌چپ با ستون‌های پویا مطابق سؤال‌های فعال |
| خروجی PDF | دقیقاً یک صفحه A4، تولید سمت سرور با قالب چاپ مستقل و لوگوی سازمان |
| چاپ | نمای چاپ A4 با دکمه چاپ (کاغذ A4، مقیاس ۱۰۰٪) |
| داشبورد | شاخص‌های کلیدی، نمودار فراوانی هر سؤال، وضعیت تماس، برترین استان‌ها، روند روزانه — با فیلتر |
| تم‌های رنگی | حالت روز/شب + ۴ پالت (صورتی، آبی، سبز، بنفش) با ذخیره ترجیح کاربر؛ تم روی چاپ/PDF اثر نمی‌گذارد |
| مدیریت الگو | افزودن/ویرایش/ترتیب/فعال‌سازی سؤال‌ها و وضعیت‌های تماس بدون تغییر کد |

## الگوریتم کد ملی (نسخه اصلاح‌شده)

اعتبارسنجی کد ملی در **هر دو سمت** انجام می‌شود — سرور (`app/utils/national_code.py`) و مرورگر (`app/static/js/common.js` تابع `S.checkCodeMeli`).

ایرادهای نسخه پرکاربرد قدیمی که در این نسخه رفع شده است:

1. `return true;` انتهای تابع هرگز اجرا نمی‌شد (کد مرده) — حذف شد.
2. کدهایی با همه ارقام یکسان (مثل `1111111111`) از محاسبه رقم کنترل **عبور می‌کردند** — اکنون صریحاً رد می‌شوند.
3. ورودی غیررقمی کنترل نمی‌شد — اکنون فقط رقم مجاز است.
4. برای ورودی بیش از ۱۰ رقم، `substr(L+4-10)` رشته‌ای با طول اشتباه برمی‌گرداند — اکنون طول سخت‌گیرانه کنترل می‌شود.
5. ارقام فارسی/عربی (`۰-۹` / `٠-٩`) پشتیبانی نمی‌شد — اکنون خودکار تبدیل می‌شوند.
6. تکمیل صفر ابتدایی با `('0000'+code).substr(...)` جایگزین مطمئن شد (`while (code.length < 10) code = "0" + code;`).

قواعد پذیرش: ۸ تا ۱۰ رقم، تبدیل ارقام فارسی/عربی، تکمیل صفر ابتدایی، رد ارقام تکراری، رد خط تیره/فاصله داخلی و کنترل رقم کنترل (وزن‌های ۱۰ تا ۲، باقیمانده ۱۱). کد ملی به‌صورت **رشته** ذخیره می‌شود تا صفر ابتدایی از بین نرود.

## ساختار پروژه

```
survey-system/
├── app/
│   ├── main.py                  # نقطه ورود FastAPI (همه مسیرها زیر /app)
│   ├── config.py                # تنظیمات (متغیر محیطی SURVEY_*)
│   ├── database.py, models.py   # SQLAlchemy + جداول
│   ├── utils/
│   │   ├── jalali.py            # تبدیل/اعتبارسنجی تاریخ شمسی
│   │   └── national_code.py     # اعتبارسنجی کد ملی (سمت سرور)
│   ├── services/
│   │   ├── validation.py        # اعتبارسنجی کامل سمت سرور
│   │   ├── dashboard.py         # محاسبات آماری داشبورد
│   │   ├── excel_export.py      # خروجی XLSX
│   │   ├── pdf_export.py        # تولید PDF با Playwright
│   │   └── sheet.py             # زمینه مشترک ورقه A4
│   ├── routers/                 # APIها و صفحات
│   ├── seed_data/               # استان‌ها/شهرستان‌ها، سؤال‌ها، وضعیت‌های تماس
│   ├── templates/               # قالب‌های Jinja2 (sheet.html = قالب چاپ/PDF)
│   └── static/                  # css, js, فونت وزیرمتن, echarts, لوگو
├── scripts/
│   ├── setup_postgres.sh        # آماده‌سازی PostgreSQL (سیستم یا نسخه قابل‌حمل)
│   ├── seed.py                  # داده پایه + رکورد نمونه اختیاری
│   ├── start_survey.sh          # اجرای محلی بک‌اند
│   ├── test_utils.py            # آزمون جلالی و کد ملی
│   └── test_api.sh              # ۱۰ سناریوی آزمون API
├── deploy/
│   ├── install.sh               # نصب کامل روی سرور — بدون داکر
│   ├── survey-system.service    # نمونه سرویس systemd
│   └── nginx.conf.example       # نمونه پیکربندی nginx
├── docs/screenshots/            # تصاویر رابط کاربری
├── .env.example
├── requirements.txt
└── README.md
```

## اجرای محلی

```bash
# ۱) دیتابیس (PostgreSQL سیستم، یا در نبود آن نسخه قابل‌حمل)
bash scripts/setup_postgres.sh

# ۲) وابستگی‌ها
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium             # فقط بار اول برای تولید PDF

# ۳) داده اولیه (استان‌ها، سؤال‌ها) + ۴۰ رکورد نمونه اختیاری
python scripts/seed.py --demo 40

# ۴) اجرای بک‌اند (پورت 3030)
bash scripts/start_survey.sh
```

برنامه روی `http://127.0.0.1:3030/app/` در دسترس است. مستندات OpenAPI: `/docs`.

### متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `SURVEY_DATABASE_URL` | `postgresql+psycopg2://survey:survey@127.0.0.1:5432/surveydb` | نشانی دیتابیس |
| `SURVEY_ORG_NAME` | `راه زندگی` | نام سازمان در سربرگ‌ها |
| `SURVEY_LOGO_URL` | `/app/static/logo/logo.png` | نشانی لوگو |
| `SURVEY_SELF_URL` | `http://127.0.0.1:3030` | نشانی خود سرویس برای رندر PDF |

نمونه کامل در `.env.example` آمده است.

## آزمون‌ها

```bash
python scripts/test_utils.py     # جلالی (تطبیق jdatetime) + الگوریتم کد ملی
bash scripts/test_api.sh         # ۱۰ سناریو: ثبت با ارقام فارسی، کد ملی غلط، ناهمخوانی
                                 # شهرستان/استان، تاریخ کبیسه، پاسخ ناقص، ویرایش،
                                 # داشبورد، اکسل، PDF
```

## بارگذاری روی گیت‌هاب

مخزن به‌صورت آماده با تاریخچه کامیت‌ها ارائه شده است. برای بارگذاری در حساب خودتان:

```bash
cd survey-system
git remote add origin https://github.com/USERNAME/REPO-NAME.git
git branch -M main
git push -u origin main
```

(در صورت استفاده از توکن: `https://TOKEN@github.com/USERNAME/REPO-NAME.git`)

## استقرار روی سرور — بدون داکر

اسکریپت نصب، همه چیز را خودکار انجام می‌دهد: PostgreSQL، محیط مجازی، Chromium (برای PDF)، سرویس systemd و nginx.

```bash
# روی سرور Ubuntu 22.04+ یا Debian 12+
git clone https://github.com/USERNAME/REPO-NAME.git
cd REPO-NAME
sudo bash deploy/install.sh
```

تنظیمات اختیاری قبل از اجرا:

```bash
sudo DOMAIN=survey.example.com APP_PORT=8000 ORG_NAME="راه زندگی" bash deploy/install.sh
```

پس از نصب، برنامه روی `http://SERVER_IP/app/` در دسترس است و:

- سرویس: `systemctl status survey-system` — ری‌استارت: `sudo systemctl restart survey-system`
- لاگ زنده: `journalctl -u survey-system -f`
- اطلاعات اتصال دیتابیس در `/opt/survey-system/.env` (دسترسی 600)
- به‌روزرسانی کد: `git pull && sudo bash deploy/install.sh` — فایل `.env` حفظ می‌شود
- HTTPS: `sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx`

<details>
<summary>مراحل دستی (بدون اسکریپت)</summary>

1. `apt install python3-venv python3-pip postgresql nginx`
2. ساخت کاربر و دیتابیس PostgreSQL و ثبت `SURVEY_DATABASE_URL` در `.env`
3. `python3 -m venv venv && venv/bin/pip install -r requirements.txt && venv/bin/playwright install chromium`
4. `python scripts/seed.py` (داده پایه)
5. کپی `deploy/survey-system.service` در `/etc/systemd/system/` و `systemctl enable --now survey-system`
6. کپی `deploy/nginx.conf.example` در `/etc/nginx/sites-available/survey-system` و فعال‌سازی

</details>

## پشتیبان‌گیری و بازیابی

```bash
# پشتیبان‌گیری
pg_dump -h 127.0.0.1 -U survey -d surveydb -Fc -f backup.dump

# بازیابی
pg_restore -h 127.0.0.1 -U survey -d surveydb --clean backup.dump
```

## عیب‌یابی سریع

| نشانه | راهکار |
|---|---|
| خطای اتصال دیتابیس | `bash scripts/setup_postgres.sh` و بررسی با `pg_isready -h 127.0.0.1 -p 5432` |
| صفحه `/app` باز نمی‌شود | لاگ: `journalctl -u survey-system -f` یا `logs/survey-server.log` |
| PDF ساخته نمی‌شود | `venv/bin/playwright install chromium` را روی سرور اجرا کنید |
| خطای 502 در nginx | سرویس در حال اجراست؟ `systemctl status survey-system` |
| تاریخ ۳۰ اسفند رد می‌شود | درست است؛ کنترل کبیسه در سرور فعال است |
| فونت فارسی در PDF ناخوانا | فونت‌های وزیرمتن در `app/static/fonts` هست؛ `fc-cache -f` اجرا کنید |

## مجوز

MIT — متن کامل در فایل [LICENSE](LICENSE).
