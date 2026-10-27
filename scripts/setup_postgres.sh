#!/bin/bash
# راه‌اندازی PostgreSQL برای توسعه محلی سامانه نظرسنجی.
# - اگر PostgreSQL سیستم نصب باشد از همان استفاده می‌کند (sudo لازم است)
# - در غیر این صورت نسخه قابل‌حمل pgserver (پکیج پایتون) بالا می‌آید
# کاربر/دیتابیس ساخته‌شده: survey / survey / surveydb
set -e

DB_USER="${SURVEY_DB_USER:-survey}"
DB_PASS="${SURVEY_DB_PASS:-survey}"
DB_NAME="${SURVEY_DB_NAME:-surveydb}"

if command -v psql >/dev/null 2>&1; then
  echo ">> PostgreSQL سیستم پیدا شد."
  sudo systemctl enable --now postgresql || sudo service postgresql start || true
  sleep 2

  sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
  sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER ENCODING 'UTF8';"

  PSQL="psql -h 127.0.0.1 -U $DB_USER -d $DB_NAME"
  export PGPASSWORD="$DB_PASS"
else
  echo ">> PostgreSQL سیستم نیست؛ از نسخه قابل‌حمل pgserver استفاده می‌شود."
  python3 -m pip install --quiet "pgserver>=0.13"
  PGBIN="$(python3 -c 'import pgserver, os; print(os.path.join(os.path.dirname(pgserver.__file__), "pginstall", "bin"))')"
  PGDATA="${SURVEY_PGDATA:-$HOME/survey-pgdata}"
  LOG="${SURVEY_PGLOG:-$HOME/survey-pgdata.log}"
  export LD_LIBRARY_PATH="$PGBIN/../lib:$LD_LIBRARY_PATH"

  if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo ">> initdb ..."
    "$PGBIN/initdb" -D "$PGDATA" -U postgres -E UTF8 --no-locale --auth=trust >/dev/null
    {
      echo "listen_addresses = '127.0.0.1'"
      echo "port = 5432"
      echo "unix_socket_directories = '/tmp'"
    } >> "$PGDATA/postgresql.conf"
  fi

  if ! "$PGBIN/pg_isready" -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    "$PGBIN/pg_ctl" -D "$PGDATA" -l "$LOG" start >/dev/null
    sleep 2
  fi

  "$PGBIN/psql" -h 127.0.0.1 -p 5432 -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    "$PGBIN/psql" -h 127.0.0.1 -p 5432 -U postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" >/dev/null
  "$PGBIN/psql" -h 127.0.0.1 -p 5432 -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    "$PGBIN/psql" -h 127.0.0.1 -p 5432 -U postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER ENCODING 'UTF8';" >/dev/null

  PSQL="$PGBIN/psql -h 127.0.0.1 -p 5432 -U $DB_USER -d $DB_NAME"
  export PGPASSWORD="$DB_PASS"
fi

$PSQL -c "SELECT version();" | head -3
echo ">> آماده است: postgresql://$DB_USER:$DB_PASS@127.0.0.1:5432/$DB_NAME"
