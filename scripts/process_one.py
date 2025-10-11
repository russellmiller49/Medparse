"""
MedParse document processing pipeline.

IMPORTANT: Follow the canonical implementation playbook at:
/home/rjm/projects/ip_knowledge/medparse/medparse-docling/complete_medparse_implementation.md
for build, run, and QA steps. Treat that document as source-of-truth.
"""
from __future__ import annotations
import json, argparse, sys, os
from pathlib import Path
from typing import Any, Dict, List, Tuple
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.append(str(ROOT))

# Docling API note: we assume your code already calls DocumentConverter elsewhere if needed.
from docling.document_converter import DocumentConverter  # current API

from scripts.grobid_client import Grobid
from scripts.postprocess import merge_outputs, parse_grobid_metadata, extract_trial_ids, resolve_cross_references
from scripts.recommendation_extractor import extract_recommendations
from scripts.umls_linker import UMLSClient
from scripts.figure_cropper import crop_figures
from scripts.references_csv import write_references_csv
from scripts.ref_items_from_tei import extract_ref_items
from scripts.references_enricher import enrich_items_with_ncbi
from scripts.grobid_references import parse_references_tei
from scripts.ref_enricher import enrich_refs_from_struct
from scripts.grobid_authors import parse_authors_from_tei
from scripts.section_filters import drop_author_sections
from scripts.text_normalize import normalize_for_nlp
from scripts.fig_ocr import ocr_if_textual
from scripts.qa_logger import write_qa
from scripts.cache_manager import CacheManager
from scripts.validator import validate_extraction
from scripts.linking.enhanced_linker import link_medical_concepts
from scripts.linking.umls_only_linker import link_medical_concepts_umls_only
# Import extraction fix modules
from scripts.statistics_enhanced import extract_statistics as extract_statistics_enhanced
from scripts.statistics_gated import extract_statistics as extract_statistics_legacy
from scripts.umls_filters import filter_umls_links, cluster_umls_links
from scripts.caption_linker import link_captions
from scripts.authors_fallback import extract_authors_from_frontmatter, enrich_authors_with_affiliations
from scripts.abstract_fallback import extract_abstract
from scripts.reference_manager import ensure_references_enriched
from scripts.http_retry import with_retries, fetch_with_retry
from scripts.section_classifier import classify_section
from scripts.drug_extractor import extract_drugs_dosages
from scripts.env_loader import load_env
from scripts.safe_json import safe_write_json
from scripts.table_extractor import extract_structured_tables
from scripts.graph_export import build_graph_payload
from medparse.layout.cleaning import sanitize_sections
from medparse.layout.page_map import build_full_text_with_spans
from medparse.extractors import infer_doc_type, run_structured_extractors


def _enrich_figures(
    struct_figures: List[Dict[str, Any]] | None,
    asset_figures: List[Dict[str, Any]] | None,
    figure_infos: List[Dict[str, Any]] | None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    struct_figures = struct_figures or []
    asset_figures = asset_figures or []
    figure_infos = figure_infos or []

    info_map = {
        info.get("structure_index"): info
        for info in figure_infos
        if info.get("structure_index") is not None
    }

    enriched_struct: List[Dict[str, Any]] = []
    enriched_assets: List[Dict[str, Any]] = []
    figure_payloads: List[Dict[str, Any]] = []

    for idx, fig in enumerate(struct_figures):
        info = info_map.get(idx)
        if not info:
            continue

        caption = info.get("caption")
        asset_entry = None
        if idx < len(asset_figures):
            asset_entry = dict(asset_figures[idx])
            asset_entry["content"] = fig
            existing_caps = [cap for cap in asset_entry.get("captions", []) if cap]
            if not caption and existing_caps:
                caption = existing_caps[0]
            if caption and caption not in existing_caps:
                existing_caps.insert(0, caption)
            asset_entry["captions"] = existing_caps
        else:
            asset_entry = {
                "type": "figure",
                "content": fig,
                "captions": [caption] if caption else [],
                "footnotes": [],
            }

        fig_entry = dict(fig)
        fig_entry["caption"] = caption
        fig_entry["page"] = info.get("page")
        fig_entry["image_path"] = info.get("image_path")
        fig_entry["local_id"] = info.get("id")
        fig_entry["bbox"] = info.get("bbox_pdf")
        enriched_struct.append(fig_entry)

        asset_entry["content"] = fig_entry
        footnotes = list(asset_entry.get("footnotes", []))
        asset_entry["footnotes"] = footnotes
        enriched_assets.append(asset_entry)

        figure_payload = {
            "kind": "figure",
            "id": info.get("id"),
            "local_id": info.get("id"),
            "caption": caption,
            "page": info.get("page"),
            "image_path": info.get("image_path"),
            "bbox": info.get("bbox_pdf"),
            "bbox_pixels": info.get("bbox_pixels"),
            "width_px": info.get("width_px"),
            "height_px": info.get("height_px"),
            "footnotes": footnotes,
        }
        figure_payloads.append(figure_payload)

    return figure_payloads, enriched_struct, enriched_assets

def _prepare_normalized_sections(sections: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    section_blocks: List[str] = []
    for sec in sections:
        parts: List[str] = []
        title = (sec.get("title") or "").strip()
        if title:
            parts.append(title)
        for para in sec.get("paragraphs", []) or []:
            text = ""
            if isinstance(para, dict):
                text = (para.get("text") or "").strip()
            elif isinstance(para, str):
                text = para.strip()
            if text:
                parts.append(text)
        section_blocks.append("\n".join(parts))

    normalized_blocks = [normalize_for_nlp(block) for block in section_blocks]
    non_empty_indices = [i for i, block in enumerate(normalized_blocks) if block]
    normalized_text = "\n".join(normalized_blocks[i] for i in non_empty_indices)

    section_spans: List[Dict[str, Any]] = []
    cursor = 0
    for position, idx in enumerate(non_empty_indices):
        block = normalized_blocks[idx]
        start = cursor
        end = start + len(block)
        section_spans.append(
            {
                "index": idx,
                "title": sections[idx].get("title"),
                "category": sections[idx].get("category"),
                "start": start,
                "end": end,
            }
        )
        cursor = end
        if position != len(non_empty_indices) - 1:
            cursor += 1

    return normalized_text, section_spans


def process_pdf(
    pdf_path: Path,
    out_json: Path,
    cfg_path: Path,
    linker: str,
    dump_docling_debug: bool = False,
    work_dir: Path | None = None,
    document_type: str | None = None,
):
    env = load_env()
    grobid_url = env["GROBID_URL"]
    umls_key = env["UMLS_API_KEY"]
    ncbi_key = env["NCBI_API_KEY"]
    ncbi_email = env["NCBI_EMAIL"]
    quick_path = env["QUICKUMLS_PATH"]
    doc_id = pdf_path.stem
    
    cache = CacheManager(Path("cache"))
    grobid = Grobid(url=grobid_url)

    out_root = Path(work_dir) if work_dir else Path("out")
    figures_dir = out_root / "figures"
    tables_dir = out_root / "tables"
    references_dir = out_root / "references"
    qa_dir = out_root / "qa"
    
    # Docling: use DocumentConverter API
    logger.info(f"Docling parsing (DocumentConverter): {pdf_path.name}")
    converter = DocumentConverter()
    dl_raw = converter.convert(str(pdf_path)).model_dump()
    
    # Optional: small, safe Docling debug dump (strip base64 so it doesn't explode)
    if dump_docling_debug:
        debug_path = out_json.parent / f"{out_json.stem}.docling_debug.json"
        try:
            debug_copy = dl_raw.copy()
            for pic in debug_copy.get("pictures", []):
                # remove heavy payloads if present
                pic.pop("image", None)
            with debug_path.open("w", encoding="utf-8") as f:
                json.dump(debug_copy, f, ensure_ascii=False, indent=2)
            logger.info(f"Wrote Docling debug JSON (no base64) → {debug_path}")
        except Exception as e:
            logger.warning(f"Docling debug dump failed: {e}")
    
    logger.info("Cropping figure images with EXIF captions")
    fig_stats = crop_figures(pdf_path, dl_raw, figures_dir)
    figure_infos = fig_stats.pop("figures", [])
    
    logger.info("GROBID metadata & references")
    meta_tei = grobid.process_fulltext(str(pdf_path))
    refs_tei = grobid.process_biblio(str(pdf_path))
    meta = parse_grobid_metadata(meta_tei["tei_xml"])
    
    if not meta.get("authors"):
        meta_authors = parse_authors_from_tei(meta_tei["tei_xml"])
        if meta_authors:
            meta["authors"] = meta_authors
    
    enrich_authors_with_affiliations(meta, dl_raw)
    
    # Parse references into structured format
    refs = parse_references_tei(refs_tei["references_tei"])
    meta["references_raw"] = refs["references_raw"]
    meta["references_struct"] = refs["references_struct"]
    
    logger.info("Writing references CSV (AMA)")
    refs_csv = references_dir / f"{pdf_path.stem}.refs.csv"
    n_refs_csv = write_references_csv(refs["references_struct"], refs_csv)
    
    # Merge & UMLS (online) as base; we'll swap/augment by linker choice below
    from json import loads
    abbrev = json.loads(Path("config/abbreviations_med.json").read_text(encoding="utf-8"))
    umls = UMLSClient(api_key=umls_key, cache=cache) if umls_key else None
    merged = merge_outputs(
        dl_raw,
        meta,
        refs_tei,
        umls,
        abbrev,
        tei_xml=meta_tei["tei_xml"],
    )

    merged["recommendations"] = extract_recommendations(merged.get("structure", {}).get("sections", []))

    for sec in merged.get("structure", {}).get("sections", []):
        sec["category"] = classify_section(sec.get("title", ""))
    
    # Clean up author sections that may have leaked in
    drop_author_sections(merged.get("structure", {}))
    
    structure = merged.get("structure", {})
    sanitize_sections(structure)
    sections = structure.get("sections", [])
    full_text, page_spans = build_full_text_with_spans(
        sections,
        docling_body=dl_raw.get("assembled", {}).get("body"),
    )
    merged["full_text"] = full_text
    merged["page_map"] = page_spans
    full_text_normalized, section_spans = _prepare_normalized_sections(sections)

    merged["doc_id"] = doc_id
    doc_type_hint = infer_doc_type(merged, doc_id=doc_id, explicit=document_type)
    if doc_type_hint:
        merged.setdefault("metadata", {})["doc_type"] = doc_type_hint
    try:
        structured = run_structured_extractors(
            doc_id=doc_id,
            payload=merged,
            full_text=full_text,
            page_map=page_spans,
            doc_type=doc_type_hint,
        )
        if structured:
            merged["doc_specific"] = structured
    except Exception as exc:
        logger.exception("Structured extractor failed: %s", exc)
    
    if linker not in {"umls", "scispacy", "quickumls"}:
        raise ValueError("linker must be one of: umls | scispacy | quickumls")

    linker_tag = "enhanced"
    concept_top_k = 600 if len(full_text_normalized) > 10000 else 250
    try:
        concept_links = link_medical_concepts(
            full_text_normalized,
            top_k=concept_top_k,
            quickumls_path=quick_path,
            cache=cache,
            normalized_text=full_text_normalized,
            section_spans=section_spans,
        )
    except Exception as exc:
        logger.exception("Enhanced concept linking failed: %s", exc)
        concept_links = []
    
    # Fallback to UMLS-only linker if enhanced linker returns no results
    if not concept_links:
        logger.info("Enhanced linker returned no results, trying UMLS-only fallback")
        try:
            concept_links = link_medical_concepts_umls_only(
                full_text_normalized,
                top_k=concept_top_k,
            )
            logger.info("UMLS-only fallback found %d concepts", len(concept_links))
        except Exception as exc:
            logger.exception("UMLS-only fallback also failed: %s", exc)
            concept_links = []

    if concept_links:
        source_counts = {}
        for link in concept_links:
            source = link.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
        summary = ", ".join(f"{src}:{cnt}" for src, cnt in sorted(source_counts.items()))
        logger.info(
            "Enhanced concept linker produced %d concepts (%s)",
            len(concept_links),
            summary or "no sources reported",
        )
    else:
        logger.warning("Enhanced concept linker returned no concepts for %s", pdf_path.name)

    merged["umls_links"] = concept_links
    merged["umls_links_local"] = []
    
    # Enrich references via PubMed if key present (with retry logic)
    references_enriched = None
    if ncbi_key:
        logger.info("NCBI enrichment: resolving PubMed metadata for references")
        try:
            # Wrap the enrichment call with retry logic
            @with_retries(max_retries=3, initial_delay=1.0)
            def enrich_with_retry():
                return enrich_refs_from_struct(refs["references_struct"])
            
            references_enriched = enrich_with_retry()
            merged["references_enriched"] = references_enriched
        except Exception as e:
            logger.warning(f"Reference enrichment failed after retries: {e}")
    
    # Extract drugs and trial IDs
    logger.info("Extracting drugs/doses and trial IDs")
    merged["drugs"] = extract_drugs_dosages(full_text_normalized)
    merged["trial_ids"] = extract_trial_ids(full_text_normalized)
    
    # ========== APPLY EXTRACTION FIXES ==========
    
    # 1. Link captions and footnotes to tables/figures
    logger.info("Linking captions and footnotes to assets")
    merged = link_captions(merged)

    assets = merged.setdefault("assets", {})
    structure = merged.setdefault("structure", {})

    figure_payloads, struct_figs, asset_figs = _enrich_figures(
        structure.get("figures"),
        assets.get("figures"),
        figure_infos,
    )
    structure["figures"] = struct_figs
    assets["figures"] = asset_figs
    merged["figures"] = figure_payloads

    table_payloads, struct_tables, asset_tables = extract_structured_tables(
        structure.get("tables", []),
        assets.get("tables"),
        tables_dir,
        pdf_path.stem,
    )
    structure["tables"] = struct_tables
    assets["tables"] = asset_tables
    merged["tables"] = table_payloads
    
    # 2. Extract statistics with provenance-aware parser (fallback to legacy)
    logger.info("Extracting statistics with provenance metadata")
    stats_enhanced = extract_statistics_enhanced(merged, full_text, dl_raw)
    if stats_enhanced:
        merged["statistics"] = stats_enhanced
    else:
        logger.warning("Enhanced statistics extractor returned no results; using legacy gating")
        merged["statistics"] = extract_statistics_legacy(full_text_normalized)
    
    # 3. Filter UMLS links for quality
    if "umls_links" in merged:
        logger.info("Filtering UMLS links for quality")
        original_count = len(merged["umls_links"])
        merged["umls_links"] = filter_umls_links(merged["umls_links"])
        merged["umls_concepts"] = cluster_umls_links(merged["umls_links"])
        filtered_count = len(merged["umls_links"])
        logger.info(f"UMLS links: {original_count} → {filtered_count} after filtering")
    
    if "umls_links_local" in merged:
        merged["umls_links_local"] = filter_umls_links(merged["umls_links_local"])
    
    # 4. Author fallback extraction if needed
    if not merged.get("metadata", {}).get("authors"):
        logger.info("Attempting author extraction from front matter")
        authors = extract_authors_from_frontmatter(merged)
        if authors:
            merged.setdefault("metadata", {})["authors"] = authors
            logger.info(f"Extracted {len(authors)} authors from front matter")
    
    # 5. Abstract fallback extraction if needed
    if not merged.get("metadata", {}).get("abstract"):
        logger.info("Attempting abstract extraction from document structure")
        abstract = extract_abstract(merged)
        if abstract:
            merged.setdefault("metadata", {})["abstract"] = abstract
            logger.info(f"Extracted abstract ({len(abstract)} chars)")
    
    # 6. Ensure references are present (fallback to GROBID if needed)
    ensure_references_enriched(merged)
    refs_count = len(merged.get("metadata", {}).get("references_enriched", []))
    refs_source = merged.get("metadata", {}).get("references_source", "unknown")
    logger.info(f"References: {refs_count} from {refs_source}")

    # Re-run author affiliation enrichment now that metadata is finalized
    enrich_authors_with_affiliations(merged.get("metadata", {}), dl_raw, merged)
    author_meta = merged.get("metadata", {}).get("authors", [])
    missing_affs = sum(1 for a in author_meta if isinstance(a, dict) and not a.get("affiliations"))
    if missing_affs:
        logger.warning("Authors missing affiliations after enrichment: {}", missing_affs)
    else:
        logger.info("All authors enriched with affiliations")
    
    # 7. Set validation flags
    merged.setdefault("validation", {}).update({
        "has_authors": bool(merged.get("metadata", {}).get("authors")),
        "has_statistics": bool(merged.get("statistics")),
        "has_filtered_umls": True,
        "has_captions": bool(merged.get("assets", {}).get("tables") or merged.get("assets", {}).get("figures")),
        "extraction_quality": "enhanced"
    })
    
    merged["graph"] = build_graph_payload(merged)

    resolve_cross_references(merged)
    
    # Validation
    validation = validate_extraction(merged)
    merged["validation"] = validation
    if not validation["is_valid"]:
        logger.warning(f"Validation issues: {validation['issues']}")
    
    # --- guard: never write raw Docling documents as the final JSON ---
    if isinstance(merged, dict) and merged.get("schema_name") == "DoclingDocument":
        raise RuntimeError("Attempted to write Docling raw document; expected merged pipeline JSON.")
    
    # --- write final output (guarded) ---
    safe_write_json(merged, out_json)
    
    qa = {
        "pdf": pdf_path.name,
        "n_sections": len(merged.get("structure", {}).get("sections", [])),
        "n_tables": len(merged.get("structure", {}).get("tables", [])),
        "n_figures": len(merged.get("structure", {}).get("figures", [])),
        "n_fig_crops": fig_stats.get("n_saved", 0),
        "missing_fig_bbox": fig_stats.get("n_missing_bbox", 0),
        "n_refs_csv": n_refs_csv,
        "n_recommendations": len(merged.get("recommendations", [])),
        "n_umls_links": len(merged.get("umls_links", [])),
        "n_local_links": len(merged.get("umls_links_local", [])),
        "linker": linker_tag,
        "page_text_ratio": merged.get("metrics", {}).get("page_text_ratio"),
        "completeness_score": validation["completeness_score"],
        "is_valid": validation["is_valid"]
    }
    qa_dir.mkdir(parents=True, exist_ok=True)
    write_qa(qa_dir, f"{pdf_path.stem}__{linker_tag}", qa)
    logger.success(f"Done → {out_json}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=False, help="Single PDF path")
    ap.add_argument("--out", required=False, help="Single JSON path")
    ap.add_argument("--linker", choices=["umls","scispacy","quickumls"], default="umls")
    ap.add_argument("--cfg", default="config/docling_medical_config.yaml")
    ap.add_argument("--dump-docling-debug", action="store_true",
                   help="Write a Docling JSON snapshot with base64 stripped (for debugging only)")
    ap.add_argument("--document-type", default=None,
                    help="Optional document type hint (guideline, ifu, article, chapter)")
    args = ap.parse_args()
    
    if args.pdf and args.out:
        process_pdf(
            Path(args.pdf),
            Path(args.out),
            Path(args.cfg),
            linker=args.linker,
            dump_docling_debug=args.dump_docling_debug,
            document_type=args.document_type,
        )
    else:
        print("Use run_batch.py for folder processing.")
