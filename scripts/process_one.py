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
from scripts.local_linkers import link_with_quickumls, link_with_scispacy
from scripts.qa_logger import write_qa
from scripts.cache_manager import CacheManager
from scripts.validator import validate_extraction
from scripts.stats_extractor import extract_statistics
from scripts.section_classifier import classify_section
from scripts.drug_extractor import extract_drugs_dosages
from scripts.env_loader import load_env

def process_pdf(pdf_path: Path, out_json: Path, cfg_path: Path, linker: str):
    env = load_env()
    grobid_url = env["GROBID_URL"]
    umls_key = env["UMLS_API_KEY"]
    ncbi_key = env["NCBI_API_KEY"]
    ncbi_email = env["NCBI_EMAIL"]
    quick_path = env["QUICKUMLS_PATH"]
    
    cache = CacheManager(Path("cache"))
    grobid = Grobid(url=grobid_url)
    
    # Docling: use DocumentConverter API with GPU if available
    logger.info(f"Docling parsing (DocumentConverter): {pdf_path.name}")
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    
    # For docling 2.48.0, configure to generate images
    from docling.document_converter import PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    
    pdf_options = PdfFormatOption(
        pipeline_options=PdfPipelineOptions(
            generate_picture_images=True,
            generate_table_images=True
        )
    )
    
    converter = DocumentConverter(
        format_options={'pdf': pdf_options}
    )
    dl_doc = converter.convert(str(pdf_path)).model_dump()
    
    logger.info("Cropping figure images with EXIF captions")
    fig_stats = crop_figures(pdf_path, dl_doc, Path("out/figures"))
    
    logger.info("GROBID metadata & references")
    meta_tei = grobid.process_fulltext(str(pdf_path))
    refs_tei = grobid.process_biblio(str(pdf_path))
    meta = parse_grobid_metadata(meta_tei["tei_xml"])
    
    logger.info("Writing references CSV (AMA)")
    refs_csv = Path("out/references") / f"{pdf_path.stem}.refs.csv"
    n_refs_csv = write_references_csv(refs_tei["references_tei"], refs_csv)
    
    # Merge & UMLS (online) as base; we'll swap/augment by linker choice below
    from json import loads
    abbrev = json.loads(Path("config/abbreviations_med.json").read_text(encoding="utf-8"))
    umls = UMLSClient(api_key=umls_key, cache=cache) if umls_key else None
    merged = merge_outputs(dl_doc, meta, refs_tei, umls, abbrev) if umls else {
        "metadata": meta, "structure": dl_doc.get("structure", dl_doc), "grobid": {"references_tei": refs_tei["references_tei"]}
    }
    
    # Build full text once
    full_text = concat_text(merged)
    
    # Linker switch
    fallback_used = "none"
    if linker == "umls":
        # merged already contains umls_links from merge_outputs (if umls provided)
        if not merged.get("umls_links") and umls_key:
            logger.warning("UMLS key present but no links found by base pass.")
        linker_tag = "umls"
    elif linker == "scispacy":
        linked = link_with_scispacy(full_text, model="en_core_sci_md")
        if linked:
            merged.setdefault("umls_links_local", []).extend(linked)
        fallback_used = "scispaCy"
        linker_tag = "scispacy"
    elif linker == "quickumls":
        linked = link_with_quickumls(full_text, quickumls_path=quick_path)
        if linked:
            merged.setdefault("umls_links_local", []).extend(linked)
        fallback_used = "QuickUMLS"
        linker_tag = "quickumls"
    else:
        raise ValueError("linker must be one of: umls | scispacy | quickumls")
    
    # Enrich references via PubMed if key present
    references_enriched = None
    if ncbi_key:
        logger.info("NCBI enrichment: resolving PubMed metadata for references")
        from scripts.ncbi_client import NCBIClient
        ncbi = NCBIClient(api_key=ncbi_key, email=ncbi_email)
        items = extract_ref_items(refs_tei["references_tei"])
        references_enriched = enrich_items_with_ncbi(items, ncbi=ncbi, cache=cache)
        merged["references_enriched"] = references_enriched
    
    # Extractions
    logger.info("Extracting statistics, drugs/doses, and trial IDs")
    merged["statistics"] = extract_statistics(full_text)
    merged["drugs"] = extract_drugs_dosages(full_text)
    merged["trial_ids"] = extract_trial_ids(full_text)
    
    # Section classification
    for sec in merged.get("structure", {}).get("sections", []):
        sec["category"] = classify_section(sec.get("title",""))
    
    resolve_cross_references(merged)
    
    # Validation
    validation = validate_extraction(merged)
    merged["validation"] = validation
    if not validation["is_valid"]:
        logger.warning(f"Validation issues: {validation['issues']}")
    
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    
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
    args = ap.parse_args()
    
    if args.pdf and args.out:
        process_pdf(Path(args.pdf), Path(args.out), Path(args.cfg), linker=args.linker)
    else:
        print("Use run_batch.py for folder processing.")