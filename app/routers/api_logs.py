# -*- coding: utf-8 -*-
"""مشاهدهٔ لاگ فعالیت‌ها — فقط مدیر."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import api_admin
from ..database import get_db
from ..models import ActivityLog, User
from ..utils.activity import ACTION_LABELS

router = APIRouter(prefix="/api/logs", tags=["logs"])


def _fa_time(dtval):
    if not dtval:
        return "—"
    import zoneinfo
    from ..config import TZ_NAME
    from ..utils.jalali import gdate_to_jalali_str

    local = dtval.astimezone(zoneinfo.ZoneInfo(TZ_NAME))
    return gdate_to_jalali_str(local.date()) + " — " + local.strftime("%H:%M")


def serialize_log(row: ActivityLog) -> dict:
    return {
        "id": row.id,
        "username": row.username or "—",
        "action": row.action,
        "action_label": ACTION_LABELS.get(row.action, row.action),
        "detail": row.detail,
        "ip": row.ip,
        "created_at": _fa_time(row.created_at),
    }


@router.get("")
def list_logs(
    page: int = 1,
    per_page: int = 50,
    action: str | None = None,
    username: str | None = None,
    admin: User = Depends(api_admin),
    db: Session = Depends(get_db),
):
    per_page = max(1, min(per_page, 200))
    page = max(1, page)

    stmt = select(ActivityLog)
    if action:
        stmt = stmt.where(ActivityLog.action == action)
    if username:
        stmt = stmt.where(ActivityLog.username.ilike(f"%{username.strip()}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ActivityLog.id.desc()).offset((page - 1) * per_page).limit(per_page)
    ).all()

    return {
        "items": [serialize_log(r) for r in rows],
        "total": total,
        "page": page,
        "pages": max(1, -(-total // per_page)),
    }
