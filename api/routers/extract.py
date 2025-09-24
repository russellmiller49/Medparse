"""Extraction endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from ..deps import api_key_required
from ..models import ExtractionResult
from ..service import run_full_extraction
from ..config import settings

router = APIRouter(prefix="", tags=["extract"], dependencies=[Depends(api_key_required)])


@router.post("/extract", response_model=ExtractionResult)
async def extract(pdf: UploadFile, doc_id: str = Form(...)) -> ExtractionResult:
    if pdf.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=415, detail="Only application/pdf supported")
    data = await pdf.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (> {settings.MAX_UPLOAD_MB} MB)")
    return run_full_extraction(doc_id=doc_id, pdf_bytes=data)
