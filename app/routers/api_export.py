# -*- coding: utf-8 -*-
"""خروجی PDF هر رکورد — از نمای چاپ تأییدشده، دقیقاً یک صفحه A4."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Survey
from ..services.pdf_export import render_pdf_for_record

router = APIRouter(prefix="/api/surveys", tags=["exports"])


@router.get("/{survey_id}/pdf")
async def survey_pdf(survey_id: int, db: Session = Depends(get_db)):
    s = db.get(Survey, survey_id)
    if s is None:
        raise HTTPException(404, detail={"message": "رکورد یافت نشد."})

    pdf_bytes = await render_pdf_for_record(survey_id)
    filename = f"survey-{survey_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
