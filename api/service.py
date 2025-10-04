"""Service layer bridging FastAPI and the Medparse pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

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


def run_full_extraction(
    doc_id: str,
    pdf_bytes: bytes,
    *,
    document_type: str | None = None,
) -> ExtractionResult:
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
                document_type=document_type,
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
        from scripts.cache_manager import CacheManager
        from scripts.linking.enhanced_linker import link_medical_concepts
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to import linking utilities: %s", exc)
        return LinkResponse(doc_id=doc_id, umls_links=[])

    cache = CacheManager(Path("cache"))
    concepts = link_medical_concepts(
        text,
        top_k=top_k,
        quickumls_path=settings.QUICKUMLS_PATH,
        cache=cache,
    )

    if not concepts:
        logger.warning("Enhanced linker produced no concepts for supplied text")
        return LinkResponse(doc_id=doc_id, umls_links=[])

    links = [UmlsLink(**concept) for concept in concepts]
    return LinkResponse(doc_id=doc_id, umls_links=links)


__all__ = ["run_full_extraction", "link_text"]
