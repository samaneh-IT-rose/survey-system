# -*- coding: utf-8 -*-
"""انتقال یک‌بارهٔ داده‌ها از SQLite به PostgreSQL — بدون از دست رفتن هیچ رکوردی.

کاربرد (روی سرور ویندوزی پس از اجرای deploy/setup-postgres-windows.ps1):
    set SURVEY_DATABASE_URL=postgresql+psycopg2://survey:survey@127.0.0.1:5432/surveydb
    venv\\Scripts\\python scripts\\migrate_sqlite_to_postgres.py

- ساختار جداول در مقصد خودکار ساخته می‌شود (create_all).
- رکوردها با حفظ شناسه‌ها کپی می‌شوند؛ رکوردهای تکراری رد می‌شوند
  (اجرای دوباره اسکریپت خطا نمی‌دهد — idempotent).
- در پایان شمارندهٔ شناسه‌ها (sequence) در پستگرس تنظیم می‌شود.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# ترتیب جداول برای رعایت کلیدهای خارجی
TABLE_ORDER = [
    "provinces",
    "counties",
    "questions",
    "contact_options",
    "users",
    "api_keys",
    "activity_logs",
    "surveys",
    "survey_answers",
]

DEFAULT_SQLITE = BASE_DIR / "data" / "survey.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="انتقال داده از SQLite به PostgreSQL")
    parser.add_argument("--sqlite", default=str(DEFAULT_SQLITE), help="مسیر فایل survey.db")
    args = parser.parse_args()

    from sqlalchemy import MetaData, Table, create_engine, inspect, text

    from app.config import DATABASE_URL

    src_path = Path(args.sqlite)
    if not src_path.exists():
        print(f"❌ فایل SQLite پیدا نشد: {src_path}")
        return 1

    target_url = os.environ.get("SURVEY_DATABASE_URL") or DATABASE_URL
    if not target_url.startswith("postgresql"):
        print("❌ متغیر SURVEY_DATABASE_URL باید به PostgreSQL اشاره کند. مثال:")
        print("   set SURVEY_DATABASE_URL=postgresql+psycopg2://survey:survey@127.0.0.1:5432/surveydb")
        return 1
    if "survey:survey" not in target_url:
        print("⚠️ توجه: نشانی مقصد با کاربر پیش‌فرضِ اسکریپت نصب (survey/survey) فرق دارد — ادامه می‌دهیم…")

    src_engine = create_engine(f"sqlite:///{src_path}")
    dst_engine = create_engine(target_url, pool_pre_ping=True)

    # اتصال مقصد و ساخت ساختار
    import app.models  # noqa: F401 — ثبت همهٔ مدل‌ها
    from app.database import Base

    Base.metadata.create_all(dst_engine)
    # ستون‌های جدید فرم (در دیتابیسی که با نسخهٔ قدیم ساخته شده)
    from app.database import ensure_schema_updates

    ensure_schema_updates(dst_engine)

    src_ins = inspect(src_engine)
    src_tables = set(src_ins.get_table_names())
    dst_meta = MetaData()

    total_copied = 0
    print("—" * 46)
    for tname in TABLE_ORDER:
        if tname not in src_tables:
            print(f"  {tname:16s} — در مبدأ نیست، رد شد")
            continue
        table = Table(tname, dst_meta, autoload_with=dst_engine)
        dst_cols = {c.name for c in table.columns}
        with src_engine.connect() as sconn:
            rows = [dict(r._mapping) for r in sconn.execute(text(f"SELECT * FROM {tname}"))]

        pk = list(table.primary_key.columns)[0].name if table.primary_key.columns else None
        copied = skipped = 0
        with dst_engine.begin() as dconn:
            for row in rows:
                row = {k: v for k, v in row.items() if k in dst_cols}
                if pk:
                    exists = dconn.execute(
                        table.select().where(table.c[pk] == row.get(pk))
                    ).first()
                    if exists:
                        skipped += 1
                        continue
                dconn.execute(table.insert().values(**row))
                copied += 1
        # تنظیم sequence برای درج‌های بعدی توسط برنامه
        if pk:
            with dst_engine.begin() as dconn:
                dconn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{tname}', '{pk}'), "
                    f"GREATEST(COALESCE((SELECT MAX({pk}) FROM {tname}), 1), 1), "
                    f"COALESCE((SELECT MAX({pk}) FROM {tname}) IS NOT NULL, true))"
                ))
        total_copied += copied
        print(f"  {tname:16s} — کپی: {copied}، تکراری (رد شده): {skipped}")
    print("—" * 46)
    print(f"✅ انتقال کامل شد — مجموع {total_copied} رکورد جدید به PostgreSQL منتقل شد.")
    print("   حالا سرویس را ری‌استارت کنید تا برنامه از PostgreSQL بخواند:")
    print('   cmd /c \'schtasks /End /TN "SurveySystem"\'')
    print('   cmd /c \'schtasks /Run /TN "SurveySystem"\'')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
