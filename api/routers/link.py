"""Standalone text linking endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps import api_key_required
from ..models import LinkRequest, LinkResponse
from ..service import link_text

router = APIRouter(prefix="", tags=["link"], dependencies=[Depends(api_key_required)])


@router.post("/link", response_model=LinkResponse)
def link(req: LinkRequest) -> LinkResponse:
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    return link_text(doc_id=None, text=req.text, top_k=req.top_k)
