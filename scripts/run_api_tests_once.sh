#!/bin/bash
# اجرای یک‌جای سرور تست + مجموعهٔ تست‌های اصلی API (روی دیتابیس تازه با رکوردهای نمونه)
set -u
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
export SURVEY_DATABASE_URL="sqlite:////$APP_DIR/data/test_api.db"
export SURVEY_SELF_URL="http://127.0.0.1:3010"
LOG="$APP_DIR/logs/test-server.log"

rm -f data/test_api.db
python3 -c "
from app.database import Base, engine
import app.models  # noqa
Base.metadata.create_all(engine)"
python3 scripts/seed.py --demo | tail -1

python3 -m uvicorn app.main:app --host 127.0.0.1 --port 3010 --log-level warning >> "$LOG" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3010/app/login || true)
  [ "$code" = "200" ] && break
  sleep 0.5
done
echo "server ready: $code"

bash scripts/test_api.sh
