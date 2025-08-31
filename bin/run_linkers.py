#!/usr/bin/env python3
# bin/run_linkers.py
"""
Comparative entity linker evaluation script.

USAGE:
    python bin/run_linkers.py --pdf input/AMPLE2.pdf --linker umls
    python bin/run_linkers.py --pdf input/AMPLE2.pdf --linker quickumls  
    python bin/run_linkers.py --pdf input/AMPLE2.pdf --linker scispacy
    python bin/run_linkers.py --pdf input/AMPLE2.pdf --compare  # Run all three
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.docling_adapter import convert_pdf
from scripts.grobid_tei import parse_article_metadata
from scripts.grobid_client import Grobid
from scripts.text_normalize import normalize_for_nlp, create_normalized_copy
from scripts.stats_extractor import extract_statistics
from scripts.figures import prepare_figures
from scripts.ref_extract import extract_refs_from_tei
from scripts.ref_enrich import enrich_references
from scripts.crossrefs import resolve_cross_refs, extract_cross_refs_from_sections
from scripts.validator import validate_extraction, generate_validation_report
from scripts.linking.linker_router import link_entities, link_entities_comparative
from scripts.env_loader import load_env


def process_with_linker(
    pdf_path: Path,
    linker: str,
    grobid_url: str,
    out_dir: Path
) -> Path:
    """
    Process a PDF with a specific entity linker.
    
    Args:
        pdf_path: Path to PDF file
        linker: Linker to use ("umls", "quickumls", "scispacy")
        grobid_url: GROBID service URL
        out_dir: Output directory
        
    Returns:
        Path to output JSON file
    """
    print(f"\n{'='*60}")
    print(f"Processing {pdf_path.name} with {linker.upper()} linker")
    print(f"{'='*60}\n")
    
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Extract structure with Docling
    print("1. Extracting document structure with Docling...")
    docling_data = convert_pdf(pdf_path)
    
    # Step 2: Get metadata from GROBID
    print("2. Extracting metadata with GROBID...")
    grobid = Grobid(url=grobid_url)
    tei_xml = grobid.process_fulltext(str(pdf_path))
    refs_tei = grobid.process_biblio(str(pdf_path))
    
    # Parse metadata
    metadata = parse_article_metadata(tei_xml)
    
    # Step 3: Extract references
    print("3. Extracting and enriching references...")
    references = extract_refs_from_tei(refs_tei)
    references_enriched = enrich_references(references)
    
    # Step 4: Prepare figures
    print("4. Processing figures...")
    fig_dir = out_dir / "figures" / linker
    figures = prepare_figures(
        docling_data.get("figures", []),
        fig_dir,
        base_name=pdf_path.stem,
        extract_text=True
    )
    
    # Step 5: Build document structure
    doc = {
        "metadata": metadata,
        "structure": {
            "sections": docling_data.get("sections", []),
            "tables": docling_data.get("tables", []),
            "figures": figures,
        },
        "references": references,
        "references_enriched": references_enriched,
    }
    
    # Step 6: Create normalized copy for NLP
    print("5. Normalizing text for NLP...")
    normalized_doc = create_normalized_copy(doc)
    
    # Concatenate normalized text
    fulltext_parts = []
    for section in normalized_doc["structure"]["sections"]:
        if section.get("title"):
            fulltext_parts.append(section["title"])
        for para in section.get("paragraphs", []):
            if isinstance(para, str):
                fulltext_parts.append(para)
            elif isinstance(para, dict):
                fulltext_parts.append(para.get("text", ""))
    
    fulltext = "\n\n".join(fulltext_parts)
    
    # Step 7: Extract statistics (span-based)
    print("6. Extracting statistics...")
    statistics = extract_statistics(fulltext)
    doc["statistics"] = statistics
    
    # Step 8: Extract cross-references
    print("7. Extracting cross-references...")
    cross_refs = resolve_cross_refs(fulltext)
    section_refs = extract_cross_refs_from_sections(normalized_doc["structure"]["sections"])
    doc["cross_refs"] = cross_refs
    doc["section_cross_refs"] = section_refs
    
    # Step 9: Entity linking
    print(f"8. Linking entities with {linker.upper()}...")
    if linker == "scispacy":
        method = "scispacy_only"
    elif linker == "quickumls":
        method = "quickumls"
    else:
        method = "umls"
    
    entities = link_entities(fulltext, method=method)
    doc["entities"] = entities
    doc["entity_linker"] = linker
    
    # Step 10: Validation
    print("9. Validating extraction...")
    validation = validate_extraction(doc)
    doc["validation"] = validation
    
    # Step 11: Save output
    out_path = out_dir / f"{pdf_path.stem}.{linker}.json"
    print(f"10. Saving to {out_path}")
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    
    # Print validation report
    print("\n" + generate_validation_report(validation))
    
    # Print summary stats
    print(f"\nExtraction Summary:")
    print(f"  Sections: {len(doc['structure']['sections'])}")
    print(f"  Tables: {len(doc['structure']['tables'])}")
    print(f"  Figures: {len(doc['structure']['figures'])}")
    print(f"  References: {len(doc['references'])}")
    print(f"  Entities: {len(doc['entities'])}")
    print(f"  Statistics: {len(doc['statistics'])}")
    print(f"  Cross-refs: {len(doc['cross_refs'])}")
    
    return out_path


def compare_linkers(pdf_path: Path, grobid_url: str, out_dir: Path) -> Dict[str, Path]:
    """
    Run all three linkers and save results.
    
    Args:
        pdf_path: Path to PDF file
        grobid_url: GROBID service URL
        out_dir: Output directory
        
    Returns:
        Dict mapping linker name to output path
    """
    results = {}
    
    for linker in ["umls", "quickumls", "scispacy"]:
        try:
            out_path = process_with_linker(pdf_path, linker, grobid_url, out_dir)
            results[linker] = out_path
        except Exception as e:
            print(f"Error with {linker}: {e}")
            results[linker] = None
    
    return results


def compare_results(results: Dict[str, Path]) -> None:
    """
    Compare entity extraction results across linkers.
    
    Args:
        results: Dict mapping linker name to output JSON path
    """
    print(f"\n{'='*60}")
    print("COMPARATIVE ANALYSIS")
    print(f"{'='*60}\n")
    
    data = {}
    for linker, path in results.items():
        if path and path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data[linker] = json.load(f)
    
    if not data:
        print("No results to compare")
        return
    
    # Compare entity counts
    print("Entity Extraction Comparison:")
    print("-" * 40)
    
    for linker, doc in data.items():
        entities = doc.get("entities", [])
        linked = [e for e in entities if e.get("cui")]
        print(f"\n{linker.upper()}:")
        print(f"  Total entities: {len(entities)}")
        print(f"  Linked to UMLS: {len(linked)}")
        
        # Count by semantic type
        tui_counts = {}
        for e in linked:
            for tui in e.get("tuis", []):
                tui_counts[tui] = tui_counts.get(tui, 0) + 1
        
        if tui_counts:
            print(f"  Top semantic types:")
            for tui, count in sorted(tui_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"    {tui}: {count}")
    
    # Compare validation scores
    print("\n\nValidation Scores:")
    print("-" * 40)
    
    for linker, doc in data.items():
        validation = doc.get("validation", {})
        score = validation.get("completeness_score", 0)
        quality = validation.get("quality_level", "unknown")
        print(f"{linker.upper()}: {score}% ({quality})")
    
    # Find overlapping entities
    if len(data) > 1:
        print("\n\nEntity Overlap Analysis:")
        print("-" * 40)
        
        linkers = list(data.keys())
        for i in range(len(linkers)):
            for j in range(i + 1, len(linkers)):
                l1, l2 = linkers[i], linkers[j]
                
                e1_texts = set(e["text"].lower() for e in data[l1].get("entities", []))
                e2_texts = set(e["text"].lower() for e in data[l2].get("entities", []))
                
                overlap = e1_texts & e2_texts
                only_l1 = e1_texts - e2_texts
                only_l2 = e2_texts - e1_texts
                
                print(f"\n{l1.upper()} vs {l2.upper()}:")
                print(f"  Common entities: {len(overlap)}")
                print(f"  Only in {l1}: {len(only_l1)}")
                print(f"  Only in {l2}: {len(only_l2)}")
                
                if overlap and len(overlap) <= 5:
                    print(f"  Common examples: {list(overlap)[:5]}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare entity linkers on medical PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single linker
  python bin/run_linkers.py --pdf input/AMPLE2.pdf --linker umls
  
  # Compare all linkers
  python bin/run_linkers.py --pdf input/AMPLE2.pdf --compare
  
  # Custom output directory
  python bin/run_linkers.py --pdf input/AMPLE2.pdf --compare --output outputs/comparison
        """
    )
    
    parser.add_argument(
        "--pdf",
        type=Path,
        required=True,
        help="Path to PDF file"
    )
    
    parser.add_argument(
        "--linker",
        choices=["umls", "quickumls", "scispacy"],
        help="Specific linker to use"
    )
    
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run all linkers and compare results"
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/linker_comparison"),
        help="Output directory (default: outputs/linker_comparison)"
    )
    
    parser.add_argument(
        "--grobid-url",
        default=None,
        help="GROBID service URL (overrides .env)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.compare and not args.linker:
        parser.error("Either --linker or --compare must be specified")
    
    if not args.pdf.exists():
        parser.error(f"PDF file not found: {args.pdf}")
    
    # Load environment
    env = load_env()
    grobid_url = args.grobid_url or env.get("GROBID_URL", "http://localhost:8070")
    
    # Run processing
    if args.compare:
        results = compare_linkers(args.pdf, grobid_url, args.output)
        compare_results(results)
    else:
        process_with_linker(args.pdf, args.linker, grobid_url, args.output)
    
    print(f"\n✅ Processing complete. Results saved to {args.output}/")


if __name__ == "__main__":
    main()