"""
MedParse document processing pipeline.

IMPORTANT: Follow the canonical implementation playbook at:
/home/rjm/projects/ip_knowledge/medparse/medparse-docling/complete_medparse_implementation.md
for build, run, and QA steps. Treat that document as source-of-truth.
"""
from __future__ import annotations
import json, argparse, sys, os
from pathlib import Path
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.append(str(ROOT))

# Docling API note: we assume your code already calls DocumentConverter elsewhere if needed.
from docling.document_converter import DocumentConverter  # current API

from scripts.grobid_client import Grobid
from scripts.postprocess import merge_outputs, parse_grobid_metadata, concat_text, extract_trial_ids, resolve_cross_references
from scripts.umls_linker import UMLSClient
from scripts.figure_cropper import crop_figures
from scripts.references_csv import write_references_csv
from scripts.ref_items_from_tei import extract_ref_items
from scripts.references_enricher import enrich_items_with_ncbi
from scripts.grobid_references import parse_references_tei
from scripts.ref_enricher import enrich_refs_from_struct
from scripts.grobid_authors import parse_authors_from_tei
from scripts.section_filters import drop_author_sections
from scripts.local_linkers import link_with_quickumls, link_with_scispacy
from scripts.text_normalize import normalize_for_nlp
from scripts.linker_router import link_umls_primary, link_quickumls, link_scispacy as link_scispacy_filtered
from scripts.fig_ocr import ocr_if_textual
from scripts.qa_logger import write_qa
from scripts.cache_manager import CacheManager
from scripts.validator import validate_extraction
# Import extraction fix modules
from scripts.statistics_gated import extract_statistics
from scripts.umls_filters import filter_umls_links
from scripts.caption_linker import link_captions
from scripts.authors_fallback import extract_authors_from_frontmatter
from scripts.abstract_fallback import extract_abstract
from scripts.reference_manager import ensure_references_enriched
from scripts.http_retry import with_retries, fetch_with_retry
from scripts.section_classifier import classify_section
from scripts.drug_extractor import extract_drugs_dosages
from scripts.env_loader import load_env
from scripts.safe_json import safe_write_json

def process_pdf(pdf_path: Path, out_json: Path, cfg_path: Path, linker: str, dump_docling_debug: bool = False):
    env = load_env()
    grobid_url = env["GROBID_URL"]
    umls_key = env["UMLS_API_KEY"]
    ncbi_key = env["NCBI_API_KEY"]
    ncbi_email = env["NCBI_EMAIL"]
    quick_path = env["QUICKUMLS_PATH"]
    
    cache = CacheManager(Path("cache"))
    grobid = Grobid(url=grobid_url)
    
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
    fig_stats = crop_figures(pdf_path, dl_raw, Path("out/figures"))
    
    logger.info("GROBID metadata & references")
    meta_tei = grobid.process_fulltext(str(pdf_path))
    refs_tei = grobid.process_biblio(str(pdf_path))
    meta = parse_grobid_metadata(meta_tei["tei_xml"])
    
    # Parse authors from TEI only (not from Docling page text)
    meta_authors = parse_authors_from_tei(meta_tei["tei_xml"])
    # Clean metadata.authors - remove blanks and non-alpha entries
    cleaned_authors = [a for a in meta_authors if isinstance(a, str) and a.strip() and any(ch.isalpha() for ch in a)]
    meta["authors"] = cleaned_authors
    
    # Parse references into structured format
    refs = parse_references_tei(refs_tei["references_tei"])
    meta["references_raw"] = refs["references_raw"]
    meta["references_struct"] = refs["references_struct"]
    
    logger.info("Writing references CSV (AMA)")
    refs_csv = Path("out/references") / f"{pdf_path.stem}.refs.csv"
    n_refs_csv = write_references_csv(refs["references_struct"], refs_csv)
    
    # Merge & UMLS (online) as base; we'll swap/augment by linker choice below
    from json import loads
    abbrev = json.loads(Path("config/abbreviations_med.json").read_text(encoding="utf-8"))
    umls = UMLSClient(api_key=umls_key, cache=cache) if umls_key else None
    merged = merge_outputs(dl_raw, meta, refs_tei, umls, abbrev) if umls else {
        "metadata": meta, "structure": dl_raw.get("structure", dl_raw), "grobid": {"references_tei": refs_tei["references_tei"]}
    }
    
    # Clean up author sections that may have leaked in
    drop_author_sections(merged.get("structure", {}))
    
    # Build full text once
    full_text = concat_text(merged)
    # Normalize text for NLP (ligatures, hyphens, inline expansions)
    full_text_normalized = normalize_for_nlp(full_text)
    
    # Linker switch with semantic filtering
    fallback_used = "none"
    if linker == "umls":
        # Use UMLS with semantic filtering
        if umls:
            umls_hits = link_umls_primary(full_text_normalized, umls)
            merged["umls_links"] = umls_hits
            logger.info(f"UMLS linked {len(umls_hits)} entities with semantic filtering")
        linker_tag = "umls"
    elif linker == "scispacy":
        linked = link_scispacy_filtered(full_text_normalized, model="en_core_sci_md")
        if linked:
            merged.setdefault("umls_links_local", []).extend(linked)
        fallback_used = "scispaCy"
        linker_tag = "scispacy"
    elif linker == "quickumls":
        linked = link_quickumls(full_text_normalized, quick_path)
        if linked:
            merged.setdefault("umls_links_local", []).extend(linked)
        fallback_used = "QuickUMLS"
        linker_tag = "quickumls"
    else:
        raise ValueError("linker must be one of: umls | scispacy | quickumls")
    
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
    
    # 2. Extract statistics with context gating
    logger.info("Extracting statistics with context gating")
    merged["statistics"] = extract_statistics(full_text_normalized)
    
    # 3. Filter UMLS links for quality
    if "umls_links" in merged:
        logger.info("Filtering UMLS links for quality")
        original_count = len(merged["umls_links"])
        merged["umls_links"] = filter_umls_links(merged["umls_links"])
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
    
    # 7. Set validation flags
    merged.setdefault("validation", {}).update({
        "has_authors": bool(merged.get("metadata", {}).get("authors")),
        "has_statistics": bool(merged.get("statistics")),
        "has_filtered_umls": True,
        "has_captions": bool(merged.get("assets", {}).get("tables") or merged.get("assets", {}).get("figures")),
        "extraction_quality": "enhanced"
    })
    
    # Section classification
    for sec in merged.get("structure", {}).get("sections", []):
        sec["category"] = classify_section(sec.get("title",""))
    
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
        "n_umls_links": len(merged.get("umls_links", [])),
        "n_local_links": len(merged.get("umls_links_local", [])),
        "linker": linker_tag,
        "completeness_score": validation["completeness_score"],
        "is_valid": validation["is_valid"]
    }
    qa_dir = Path("out/qa"); qa_dir.mkdir(parents=True, exist_ok=True)
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
    args = ap.parse_args()
    
    if args.pdf and args.out:
        process_pdf(Path(args.pdf), Path(args.out), Path(args.cfg), linker=args.linker, dump_docling_debug=args.dump_docling_debug)
    else:
        print("Use run_batch.py for folder processing.")