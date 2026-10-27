#!/bin/bash
# اجرای محلی بک‌اند FastAPI سامانه نظرسنجی (پورت پیش‌فرض 3030)
# استفاده: bash scripts/start_survey.sh
set -e

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
mkdir -p "$APP_DIR/logs"

export SURVEY_DATABASE_URL="${SURVEY_DATABASE_URL:-postgresql+psycopg2://survey:survey@127.0.0.1:5432/surveydb}"
export SURVEY_SELF_URL="${SURVEY_SELF_URL:-http://127.0.0.1:${SURVEY_PORT:-3030}}"
PORT="${SURVEY_PORT:-3030}"

# اجرا با محیط مجازی در صورت وجود
PY="$APP_DIR/venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

# توقف نمونه قبلی (در صورت وجود)
if [ -f "$APP_DIR/logs/survey.pid" ]; then
  kill "$(cat "$APP_DIR/logs/survey.pid")" 2>/dev/null || true
  rm -f "$APP_DIR/logs/survey.pid"
  sleep 1
fi

nohup "$PY" -m uvicorn app.main:app \
  --host 127.0.0.1 --port "$PORT" \
  --log-level warning \
  >> "$APP_DIR/logs/survey-server.log" 2>&1 &

echo $! > "$APP_DIR/logs/survey.pid"
echo "survey backend started on port $PORT, pid $(cat "$APP_DIR/logs/survey.pid")"
