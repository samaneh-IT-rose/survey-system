#!/bin/bash
# اجرای یک‌جای سرور تست + مجموعهٔ کامل تست‌های احراز هویت/وب‌سرویس
# (محیط تست بین فراخوانی‌ها پروسهٔ پس‌زمینه را می‌بندد؛ پس همه‌چیز در یک نشست)
set -u
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
export SURVEY_DATABASE_URL="sqlite:////$APP_DIR/data/test_auth.db"
export SURVEY_SELF_URL="http://127.0.0.1:3010"
LOG="$APP_DIR/logs/test-server.log"

# پایگاه دادهٔ تازه برای نتیجهٔ قطعی
rm -f data/test_auth.db
python3 -c "
from app.database import Base, engine
import app.models  # noqa
Base.metadata.create_all(engine)
print('tables ok')"
python3 scripts/seed.py | tail -1

# اجرای سرور در همان نشست
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 3010 --log-level warning >> "$LOG" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT

# آماده شدن سرور
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3010/app/login || true)
  [ "$code" = "200" ] && break
  sleep 0.5
done
echo "server ready: $code"

bash scripts/test_auth.sh
RC=$?
exit $RC
