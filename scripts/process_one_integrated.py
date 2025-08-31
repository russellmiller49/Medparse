#!/usr/bin/env python3
# scripts/process_one_integrated.py
"""
Integrated processing pipeline using the new modular architecture.
"""

from __future__ import annotations
import json
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

# Add parent directory to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Import our new modules
from scripts.docling_adapter import convert_pdf
from scripts.grobid_tei import parse_article_metadata
from scripts.grobid_client import Grobid
from scripts.text_normalize import (
    normalize_for_nlp,
    create_normalized_copy,
    detect_ligature_ratio,
    remove_inline_expansions
)
from scripts.stats_extractor import extract_statistics
from scripts.figures import prepare_figures, filter_watermarks
from scripts.ref_extract import extract_refs_from_tei
from scripts.ref_enrich import enrich_references, write_references_csv
from scripts.crossrefs import resolve_cross_refs, extract_cross_refs_from_sections
from scripts.linking.linker_router import link_entities
from scripts.validator import validate_extraction, generate_validation_report
from scripts.drug_extractor import extract_drugs_dosages
from scripts.env_loader import load_env
from scripts.cache_manager import CacheManager


def process_pdf(
    pdf_path: Path,
    out_json: Path,
    linker: str = "auto",
    enrich_pubmed: bool = True,
    figure_mode: str = "caption_first",
    verbose: bool = False
) -> Path:
    """
    Process a PDF through the complete extraction pipeline.
    
    Args:
        pdf_path: Path to input PDF
        out_json: Path to output JSON
        linker: Entity linker to use ("auto", "umls", "quickumls", "scispacy")
        enrich_pubmed: Whether to enrich references with PubMed
        figure_mode: Figure extraction mode ("caption_first", "all")
        verbose: Verbose output
        
    Returns:
        Path to output JSON file
    """
    # Load environment
    env = load_env()
    grobid_url = env.get("GROBID_URL", "http://localhost:8070")
    
    # Initialize services
    cache = CacheManager(Path("cache"))
    grobid = Grobid(url=grobid_url)
    
    # Ensure output directory exists
    out_json.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Processing: {pdf_path.name}")
    
    # Step 1: Document structure extraction with Docling
    logger.info("1. Extracting document structure (Docling)...")
    try:
        docling_data = convert_pdf(pdf_path)
    except Exception as e:
        logger.error(f"Docling extraction failed: {e}")
        docling_data = {"texts": [], "figures": [], "tables": [], "sections": []}
    
    # Step 2: Metadata extraction with GROBID
    logger.info("2. Extracting metadata (GROBID)...")
    try:
        tei_xml = grobid.process_fulltext(str(pdf_path))
        refs_tei = grobid.process_biblio(str(pdf_path))
        
        # Parse metadata using new clean extraction
        metadata = parse_article_metadata(tei_xml)
    except Exception as e:
        logger.error(f"GROBID processing failed: {e}")
        metadata = {}
        refs_tei = ""
    
    # Step 3: Reference extraction and enrichment
    logger.info("3. Processing references...")
    references = extract_refs_from_tei(refs_tei) if refs_tei else []
    
    if enrich_pubmed and references:
        logger.info("   Enriching with PubMed...")
        references_enriched = enrich_references(references)
    else:
        references_enriched = references
    
    # Write references CSV
    refs_csv_path = out_json.parent / f"{pdf_path.stem}_references.csv"
    if references_enriched:
        write_references_csv(references_enriched, str(refs_csv_path))
    
    # Step 4: Figure processing
    logger.info("4. Processing figures...")
    figures = docling_data.get("figures", [])
    
    # Filter watermarks if page dimensions available
    if figures:
        # Get page dimensions from first text element if available
        page_dims = {}
        for text in docling_data.get("texts", []):
            if text.get("page") is not None and text.get("bbox"):
                page = text["page"]
                if page not in page_dims:
                    # Estimate page size from bbox
                    bbox = text["bbox"]
                    if bbox and len(bbox) >= 4:
                        page_dims[page] = (max(600, bbox[2]), max(800, bbox[3]))
        
        if page_dims:
            figures = filter_watermarks(figures, page_dims)
    
    # Prepare figure files
    fig_dir = out_json.parent / "figures"
    prepared_figures = prepare_figures(
        figures,
        fig_dir,
        base_name=pdf_path.stem,
        extract_text=(figure_mode == "all")
    )
    
    # Step 5: Build document structure
    doc = {
        "metadata": metadata,
        "structure": {
            "sections": docling_data.get("sections", []),
            "tables": docling_data.get("tables", []),
            "figures": prepared_figures,
        },
        "references": references,
        "references_enriched": references_enriched,
        "references_csv_path": str(refs_csv_path) if references else None,
    }
    
    # Step 6: Text normalization for NLP
    logger.info("5. Normalizing text for NLP...")
    
    # Create normalized copy (original unchanged)
    normalized_doc = create_normalized_copy(doc)
    
    # Concatenate normalized text for analysis
    fulltext_parts = []
    for section in normalized_doc["structure"]["sections"]:
        if section.get("title"):
            fulltext_parts.append(section["title"])
        for para in section.get("paragraphs", []):
            if isinstance(para, str):
                text = para
            elif isinstance(para, dict):
                text = para.get("text", "")
            else:
                continue
            # Remove inline expansions
            text = remove_inline_expansions(text)
            if text:
                fulltext_parts.append(text)
    
    fulltext = "\n\n".join(fulltext_parts)
    
    # Check ligature ratio for validation
    ligature_ratio = detect_ligature_ratio(fulltext)
    doc["text_quality"] = {
        "ligature_ratio": ligature_ratio,
        "ligatures_cleaned": ligature_ratio < 0.001
    }
    
    # Step 7: Statistics extraction (span-based)
    logger.info("6. Extracting statistics...")
    statistics = extract_statistics(fulltext)
    doc["statistics"] = statistics
    
    # Step 8: Drug extraction
    logger.info("7. Extracting drugs and dosages...")
    drugs = extract_drugs_dosages(fulltext)
    doc["drugs"] = drugs
    
    # Step 9: Trial ID extraction
    logger.info("8. Extracting trial IDs...")
    trial_ids = extract_trial_ids(fulltext)
    doc["trial_ids"] = trial_ids
    
    # Step 10: Cross-reference extraction
    logger.info("9. Extracting cross-references...")
    cross_refs = resolve_cross_refs(fulltext)
    section_refs = extract_cross_refs_from_sections(normalized_doc["structure"]["sections"])
    doc["cross_refs"] = cross_refs
    doc["section_cross_refs"] = section_refs
    
    # Step 11: Entity linking
    logger.info(f"10. Linking entities ({linker})...")
    entities = link_entities(fulltext, method=linker)
    doc["entities"] = entities
    doc["entity_linker"] = linker
    
    # Step 12: Validation
    logger.info("11. Validating extraction...")
    validation = validate_extraction(doc)
    doc["validation"] = validation
    
    # Step 13: Save output
    logger.info(f"12. Saving to {out_json}")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    
    # Print validation report if verbose
    if verbose:
        print("\n" + generate_validation_report(validation))
        
        # Print summary
        print(f"\nExtraction Summary:")
        print(f"  Sections: {len(doc['structure']['sections'])}")
        print(f"  Tables: {len(doc['structure']['tables'])}")
        print(f"  Figures: {len(doc['structure']['figures'])}")
        print(f"  References: {len(doc['references'])}")
        print(f"  Entities: {len(doc['entities'])}")
        print(f"  Statistics: {len(doc['statistics'])}")
        print(f"  Drugs: {len(doc['drugs'])}")
        print(f"  Cross-refs: {len(doc['cross_refs'])}")
        print(f"  Ligature ratio: {ligature_ratio:.4%}")
    
    logger.success(f"✅ Processing complete: {out_json}")
    
    return out_json


def extract_trial_ids(text: str) -> list:
    """Extract clinical trial IDs from text."""
    import re
    
    patterns = {
        "nct": r'\bNCT\d{8}\b',
        "isrctn": r'\bISRCTN\d{8}\b',
        "eudract": r'\b\d{4}-\d{6}-\d{2}\b',
        "ctri": r'\bCTRI/\d{4}/\d{2}/\d{6}\b',
    }
    
    ids = []
    for id_type, pattern in patterns.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            ids.append({
                "type": id_type,
                "id": match.group(),
                "start": match.start(),
                "end": match.end()
            })
    
    return ids


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Process medical PDFs with integrated NLP pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic processing with UMLS
  python scripts/process_one_integrated.py input/AMPLE2.pdf --linker umls
  
  # Use QuickUMLS for speed
  python scripts/process_one_integrated.py input/AMPLE2.pdf --linker quickumls
  
  # Skip PubMed enrichment
  python scripts/process_one_integrated.py input/AMPLE2.pdf --no-enrich
  
  # Extract OCR text from all figures
  python scripts/process_one_integrated.py input/AMPLE2.pdf --fig-mode all
        """
    )
    
    parser.add_argument(
        "pdf",
        type=Path,
        help="Path to PDF file"
    )
    
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (default: out/json_{linker}/{pdf_name}.json)"
    )
    
    parser.add_argument(
        "--linker",
        choices=["auto", "umls", "quickumls", "scispacy"],
        default="auto",
        help="Entity linker to use (default: auto)"
    )
    
    parser.add_argument(
        "--enrich",
        dest="enrich_pubmed",
        action="store_true",
        default=True,
        help="Enrich references with PubMed (default: true)"
    )
    
    parser.add_argument(
        "--no-enrich",
        dest="enrich_pubmed",
        action="store_false",
        help="Skip PubMed enrichment"
    )
    
    parser.add_argument(
        "--fig-mode",
        choices=["caption_first", "all"],
        default="caption_first",
        help="Figure extraction mode (default: caption_first)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output with validation report"
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not args.pdf.exists():
        parser.error(f"PDF file not found: {args.pdf}")
    
    # Determine output path
    if args.out:
        out_json = args.out
    else:
        out_dir = Path("out") / f"json_{args.linker}"
        out_json = out_dir / f"{args.pdf.stem}.json"
    
    # Process PDF
    try:
        process_pdf(
            pdf_path=args.pdf,
            out_json=out_json,
            linker=args.linker,
            enrich_pubmed=args.enrich_pubmed,
            figure_mode=args.fig_mode,
            verbose=args.verbose
        )
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()