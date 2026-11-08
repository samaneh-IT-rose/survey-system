# -*- coding: utf-8 -*-
"""خروجی PDF هر رکورد — از نمای چاپ تأییدشده، دقیقاً یک صفحه A4.

کوکی سشن کاربر به Chromium منتقل می‌شود تا صفحهٔ چاپ که اکنون محافظت‌شده
است بتواند بارگذاری شود (بدون این کار PDF پس از فعال‌شدن ورود می‌شکست).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import api_require_perm
from ..constants import PERM_PRINT
from ..database import get_db
from ..models import Survey, User
from ..services.pdf_export import render_pdf_for_record
from ..utils.security import SESSION_COOKIE

router = APIRouter(prefix="/api/surveys", tags=["exports"])


@router.get("/{survey_id}/pdf")
async def survey_pdf(survey_id: int, request: Request, user: User = Depends(api_require_perm(PERM_PRINT)), db: Session = Depends(get_db)):
    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(404, detail={"message": "رکورد یافت نشد."})

    session_cookie = request.cookies.get(SESSION_COOKIE)
    pdf_bytes = await render_pdf_for_record(survey_id, session_cookie=session_cookie)
    filename = f"survey-{survey_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
