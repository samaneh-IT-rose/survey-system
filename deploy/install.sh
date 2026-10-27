#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
#  نصب کامل سامانه فرم نظرسنجی روی سرور — بدون داکر (Ubuntu 22.04+ / Debian 12+)
#
#  روش استفاده:
#      ۱) کل مخزن را روی سرور کلون/کپی کنید
#      ۲) cd survey-system
#      ۳) sudo bash deploy/install.sh
#
#  متغیرهای اختیاری (قبل از اجرا تنظیم کنید):
#      DOMAIN=example.com  APP_PORT=8000  APP_DIR=/opt/survey-system
#      RUN_USER=surveyapp  DB_NAME=surveydb  DB_USER=survey  ORG_NAME="راه زندگی"
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── تنظیمات ──
APP_DIR="${APP_DIR:-/opt/survey-system}"
RUN_USER="${RUN_USER:-surveyapp}"
DB_NAME="${DB_NAME:-surveydb}"
DB_USER="${DB_USER:-survey}"
DB_PASS="${DB_PASS:-$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)}"
APP_PORT="${APP_PORT:-8000}"
DOMAIN="${DOMAIN:-_}"
ORG_NAME="${ORG_NAME:-راه زندگی}"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ "$(id -u)" -ne 0 ]; then
  echo ">> این اسکریپت باید با sudo اجرا شود:  sudo bash deploy/install.sh"
  exit 1
fi

echo "═══ ۱/۹  نصب بسته‌های سیستم ═══"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip postgresql nginx rsync curl
systemctl enable --now postgresql >/dev/null 2>&1 || service postgresql start
sleep 2

echo "═══ ۲/۹  ساخت دیتابیس PostgreSQL ═══"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER ENCODING 'UTF8';"

echo "═══ ۳/۹  کپی فایل‌های برنامه در $APP_DIR ═══"
mkdir -p "$APP_DIR"
rsync -a --delete \
  --exclude ".git" --exclude "venv" --exclude "__pycache__" \
  --exclude ".env" --exclude "logs" --exclude "docs/screenshots" \
  "$SRC_DIR"/ "$APP_DIR"/
mkdir -p "$APP_DIR/logs"

echo "═══ ۴/۹  ساخت محیط مجازی و نصب وابستگی‌ها ═══"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip >/dev/null
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "═══ ۵/۹  نصب Chromium برای تولید PDF (یک‌بار) ═══"
"$APP_DIR/venv/bin/playwright" install chromium || echo "!! هشدار: نصب Chromium ناموفق بود — بعداً دستی اجرا کنید"
"$APP_DIR/venv/bin/playwright" install-deps chromium >/dev/null 2>&1 || true

echo "═══ ۶/۹  ساخت فایل تنظیمات .env ═══"
if [ ! -f "$APP_DIR/.env" ]; then
  cat > "$APP_DIR/.env" <<EOF
SURVEY_DATABASE_URL=postgresql+psycopg2://$DB_USER:$DB_PASS@127.0.0.1:5432/$DB_NAME
SURVEY_ORG_NAME=$ORG_NAME
SURVEY_LOGO_URL=/app/static/logo/logo.png
SURVEY_SELF_URL=http://127.0.0.1:$APP_PORT
EOF
  chmod 600 "$APP_DIR/.env"
else
  echo "   .env موجود است — دست‌نخورده ماند."
fi

echo "═══ ۷/۹  کاربر سرویس و داده‌های پایه ═══"
id "$RUN_USER" >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin "$RUN_USER"
chown -R "$RUN_USER":"$RUN_USER" "$APP_DIR"
sudo -u "$RUN_USER" env SURVEY_DATABASE_URL="postgresql+psycopg2://$DB_USER:$DB_PASS@127.0.0.1:5432/$DB_NAME" \
  "$APP_DIR/venv/bin/python" "$APP_DIR/scripts/seed.py" || true

echo "═══ ۸/۹  سرویس systemd ═══"
cat > /etc/systemd/system/survey-system.service <<EOF
[Unit]
Description=Survey System (FastAPI + Uvicorn)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $APP_PORT --workers 2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now survey-system
sleep 3
systemctl --no-pager --lines 0 status survey-system || true

echo "═══ ۹/۹  پیکربندی nginx ═══"
cat > /etc/nginx/sites-available/survey-system <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 10m;

    location /app/static/ {
        alias $APP_DIR/app/static/;
        expires 30d;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF
ln -sf /etc/nginx/sites-available/survey-system /etc/nginx/sites-enabled/survey-system
if [ -f /etc/nginx/sites-enabled/default ] && [ "$DOMAIN" = "_" ]; then
  rm -f /etc/nginx/sites-enabled/default
  echo "   سایت پیش‌فرض nginx حذف شد تا تداخل پیش نیاید."
fi
nginx -t
systemctl reload nginx

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp  >/dev/null || true
  ufw allow 443/tcp >/dev/null || true
fi

IP="$(curl -s --max-time 4 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
cat <<EOF

════════════════════════════════════════════════════════════════
  نصب کامل شد
════════════════════════════════════════════════════════════════
  نشانی برنامه :  http://$IP/app/
  دامنه         :  $DOMAIN   (برای SSL: sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx)

  مدیریت سرویس :
     systemctl status survey-system
     sudo systemctl restart survey-system
     journalctl -u survey-system -f

  اطلاعات دیتابیس :  در فایل $APP_DIR/.env  (دسترسی محدود شده است)
  به‌روزرسانی کد  :  git pull && sudo bash deploy/install.sh   (تنظیمات .env حفظ می‌شود)
════════════════════════════════════════════════════════════════
EOF
