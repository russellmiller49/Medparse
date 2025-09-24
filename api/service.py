"""Service layer bridging FastAPI and the Medparse pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List

from loguru import logger

from .config import settings
from .models import ExtractionResult, LinkResponse, UmlsLink


def _build_stub_result(doc_id: str) -> ExtractionResult:
    logger.warning("Pipeline disabled; returning stub response for doc_id=%s", doc_id)
    return ExtractionResult(doc_id=doc_id)


def _normalize_links(raw_links: list[dict] | None) -> list[dict]:
    if not raw_links:
        return []
    normalized: list[dict] = []
    for link in raw_links:
        if not isinstance(link, dict):
            continue
        text = link.get("text") or link.get("phrase") or link.get("preferred") or ""
        norm = dict(link)
        norm["text"] = text
        if "tui" in norm and isinstance(norm["tui"], str):
            norm["tui"] = [norm["tui"]]
        normalized.append(norm)
    return normalized


def run_full_extraction(doc_id: str, pdf_bytes: bytes) -> ExtractionResult:
    """Run the Medparse pipeline for a PDF and normalize the response."""
    if not settings.ENABLE_PIPELINE:
        return _build_stub_result(doc_id)
    try:
        from scripts.process_one import process_pdf  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive import guard
        logger.exception("Failed to import Medparse pipeline: %s", exc)
        return _build_stub_result(doc_id)

    with TemporaryDirectory(prefix="medparse_api_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        pdf_path = tmp_path / f"{doc_id}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        out_json = tmp_path / f"{doc_id}.json"

        try:
            process_pdf(
                pdf_path=pdf_path,
                out_json=out_json,
                cfg_path=Path("config/docling_medical_config.yaml"),
                linker="umls",
                dump_docling_debug=False,
                work_dir=tmp_path,
            )
        except Exception as exc:  # pragma: no cover - pipeline failures logged and stubbed
            logger.exception("Pipeline execution failed: %s", exc)
            return _build_stub_result(doc_id)

        if not out_json.exists():
            logger.error("Expected pipeline output missing: %s", out_json)
            return _build_stub_result(doc_id)

        content = out_json.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except Exception as exc:
            logger.exception("Invalid JSON from pipeline: %s", exc)
            return _build_stub_result(doc_id)

    data["doc_id"] = doc_id
    data["umls_links"] = _normalize_links(data.get("umls_links"))
    data["umls_links_local"] = _normalize_links(data.get("umls_links_local"))
    return ExtractionResult.model_validate(data)


def link_text(doc_id: str | None, text: str, top_k: int) -> LinkResponse:
    """Run lightweight text linking using available linkers."""
    try:
        from scripts.linker_router import link_umls_primary, link_quickumls
        from scripts.umls_linker import UMLSClient
        from scripts.cache_manager import CacheManager
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to import linking utilities: %s", exc)
        return LinkResponse(doc_id=doc_id, umls_links=[])

    quick_path = settings.QUICKUMLS_PATH
    cache = CacheManager(Path("cache"))
    assembled: List[UmlsLink] = []

    def _convert(raw: dict, default_source: str | None = None) -> UmlsLink:
        tui = raw.get("tui")
        if isinstance(tui, str):
            tui_list = [tui]
        elif isinstance(tui, list):
            tui_list = tui
        elif raw.get("tuis"):
            tui_list = list(raw.get("tuis"))
        elif raw.get("semtypes"):
            tui_list = list(raw.get("semtypes"))
        else:
            tui_list = []

        return UmlsLink(
            cui=raw.get("cui", ""),
            text=raw.get("text") or raw.get("phrase") or raw.get("name") or "",
            tui=tui_list,
            score=float(raw.get("score", 0.0) or 0.0),
            preferred_name=raw.get("preferred") or raw.get("preferred_term"),
            source=raw.get("source") or default_source,
        )

    # Primary: remote UMLS API if configured
    if settings.UMLS_API_KEY:
        client = UMLSClient(api_key=settings.UMLS_API_KEY, cache=cache)
        try:
            hits = link_umls_primary(text, client)
            for hit in hits[:top_k]:
                assembled.append(_convert(hit, "UMLS"))
        except Exception as exc:  # pragma: no cover - allow QuickUMLS fallback
            logger.warning("UMLS API linking failed; attempting QuickUMLS fallback: %s", exc)

    # Fallback / standalone: QuickUMLS local index
    if (not assembled or len(assembled) < top_k) and quick_path:
        try:
            hits = link_quickumls(text, quick_path)
            for hit in hits:
                assembled.append(_convert(hit, "QuickUMLS"))
        except Exception as exc:  # pragma: no cover
            logger.warning("QuickUMLS linking failed: %s", exc)

    if not assembled:
        if settings.UMLS_API_KEY or quick_path:
            logger.warning("Linking produced no results for supplied text")
        else:
            logger.warning(
                "No linking method configured (missing UMLS_API_KEY and QUICKUMLS_PATH)"
            )
        return LinkResponse(doc_id=doc_id, umls_links=[])

    # Deduplicate by (cui, text) while respecting top_k
    deduped: List[UmlsLink] = []
    seen = set()
    for link in assembled:
        key = (link.cui, link.text)
        if key in seen or not link.text:
            continue
        seen.add(key)
        deduped.append(link)
        if len(deduped) >= top_k:
            break

    return LinkResponse(doc_id=doc_id, umls_links=deduped)


__all__ = ["run_full_extraction", "link_text"]
