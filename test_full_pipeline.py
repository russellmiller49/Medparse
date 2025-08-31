#!/usr/bin/env python3
"""Test the full pipeline including GROBID."""

from pathlib import Path
import json
import sys

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.docling_adapter import convert_pdf
from scripts.grobid_tei import parse_article_metadata
from scripts.grobid_client import Grobid
from scripts.text_normalize import normalize_for_nlp, detect_ligature_ratio
from scripts.stats_extractor import extract_statistics
from scripts.ref_extract import extract_refs_from_tei
from scripts.ref_enrich import enrich_references
from scripts.crossrefs import resolve_cross_refs
from scripts.validator import validate_extraction, generate_validation_report
from scripts.env_loader import load_env


def test_full_pipeline(pdf_path: Path):
    """Test full pipeline including GROBID."""
    
    print(f"Testing FULL pipeline with: {pdf_path.name}")
    print("=" * 60)
    
    # Load environment
    env = load_env()
    grobid_url = env.get("GROBID_URL", "http://localhost:8070")
    
    # Test GROBID connection
    print("\n1. Testing GROBID connection...")
    grobid = Grobid(url=grobid_url)
    try:
        # Test with a simple ping
        import httpx
        response = httpx.get(f"{grobid_url}/api/isalive")
        if response.text.strip() == "true":
            print(f"   ✓ GROBID is alive at {grobid_url}")
        else:
            print(f"   ✗ GROBID not responding properly")
    except Exception as e:
        print(f"   ✗ Cannot connect to GROBID: {e}")
        return False
    
    # Test 2: Extract with GROBID
    print("\n2. Extracting metadata with GROBID...")
    try:
        tei_result = grobid.process_fulltext(str(pdf_path))
        refs_result = grobid.process_biblio(str(pdf_path))
        
        # Extract the actual XML strings from the result dicts
        tei_xml = tei_result.get("tei_xml", "") if isinstance(tei_result, dict) else str(tei_result)
        refs_tei = refs_result.get("references_tei", "") if isinstance(refs_result, dict) else str(refs_result)
        
        print(f"   ✓ TEI XML length: {len(tei_xml)} chars")
        print(f"   ✓ References TEI length: {len(refs_tei)} chars")
        
        # Parse metadata
        metadata = parse_article_metadata(tei_xml)
        print(f"   ✓ Title: {metadata.get('title', '')[:50]}...")
        print(f"   ✓ Authors: {len(metadata.get('authors', []))} found")
        if metadata.get('authors'):
            print(f"     First author: {metadata['authors'][0].get('display', 'Unknown')}")
        print(f"   ✓ Year: {metadata.get('year', 'Not found')}")
        print(f"   ✓ Journal: {metadata.get('journal', 'Not found')[:50]}...")
    except Exception as e:
        print(f"   ✗ GROBID processing error: {e}")
        metadata = {}
        refs_tei = ""
    
    # Test 3: Extract references
    print("\n3. Extracting references...")
    try:
        references = extract_refs_from_tei(refs_tei) if refs_tei else []
        print(f"   ✓ Found {len(references)} references")
        
        if references:
            # Show first reference
            ref = references[0]
            print(f"   First reference:")
            print(f"     Title: {ref.get('title', '')[:50]}...")
            print(f"     Authors: {ref.get('authors', '')[:50]}...")
            print(f"     Year: {ref.get('year', 'N/A')}")
            print(f"     DOI: {ref.get('doi', 'N/A')}")
    except Exception as e:
        print(f"   ✗ Reference extraction error: {e}")
        references = []
    
    # Test 4: Docling extraction
    print("\n4. Extracting document structure with Docling...")
    try:
        docling_data = convert_pdf(pdf_path)
        print(f"   ✓ Sections: {len(docling_data.get('sections', []))}")
        print(f"   ✓ Figures: {len(docling_data.get('figures', []))}")
        print(f"   ✓ Tables: {len(docling_data.get('tables', []))}")
    except Exception as e:
        print(f"   ✗ Docling error: {e}")
        docling_data = {"sections": [], "figures": [], "tables": []}
    
    # Test 5: Build complete document
    print("\n5. Building complete document...")
    doc = {
        "metadata": metadata,
        "structure": {
            "sections": docling_data.get("sections", []),
            "tables": docling_data.get("tables", []),
            "figures": docling_data.get("figures", [])
        },
        "references": references
    }
    
    # Get full text
    fulltext_parts = []
    for section in doc["structure"]["sections"]:
        if section.get("title"):
            fulltext_parts.append(section["title"])
        for para in section.get("paragraphs", []):
            if isinstance(para, str):
                fulltext_parts.append(para)
            elif isinstance(para, dict):
                fulltext_parts.append(para.get("text", ""))
    
    fulltext = "\n\n".join(fulltext_parts)
    fulltext_normalized = normalize_for_nlp(fulltext)
    
    # Extract statistics
    stats = extract_statistics(fulltext_normalized)
    doc["statistics"] = stats
    
    # Extract cross-references
    cross_refs = resolve_cross_refs(fulltext_normalized)
    doc["cross_refs"] = cross_refs
    
    print(f"   Full text length: {len(fulltext)} chars")
    print(f"   Statistics found: {len(stats)}")
    print(f"   Cross-refs found: {len(cross_refs)}")
    
    # Test 6: Reference enrichment (optional)
    print("\n6. Testing reference enrichment...")
    if references and env.get("NCBI_API_KEY"):
        print("   Attempting PubMed enrichment (first 3 refs)...")
        try:
            enriched = enrich_references(references[:3], use_cache=True)
            enriched_count = sum(1 for r in enriched if r.get("pmid"))
            print(f"   ✓ Enriched {enriched_count}/{min(3, len(references))} references")
        except Exception as e:
            print(f"   ✗ Enrichment failed: {e}")
    else:
        print("   Skipping (no NCBI_API_KEY or no references)")
    
    # Test 7: Validation
    print("\n7. Running validation...")
    validation = validate_extraction(doc)
    
    print(f"   Completeness score: {validation['completeness_score']}%")
    print(f"   Quality level: {validation['quality_level']}")
    print(f"   Is valid: {validation['is_valid']}")
    
    if validation.get("issues"):
        print("   Issues:")
        for issue in validation["issues"]:
            print(f"   - {issue}")
    
    if validation.get("warnings"):
        print("   Warnings:")
        for warning in validation["warnings"]:
            print(f"   - {warning}")
    
    # Save output
    output_path = Path(f"test_full_output_{pdf_path.stem}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": metadata,
            "structure_summary": {
                "sections": len(doc["structure"]["sections"]),
                "tables": len(doc["structure"]["tables"]),
                "figures": len(doc["structure"]["figures"])
            },
            "references_count": len(references),
            "statistics_count": len(stats),
            "cross_refs_count": len(cross_refs),
            "validation": validation
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n   Saved full test output to: {output_path}")
    
    print("\n" + "=" * 60)
    print("Full pipeline test complete!")
    
    # Show overall success
    success_items = [
        ("GROBID", bool(metadata.get("authors"))),
        ("References", len(references) > 0),
        ("Sections", len(doc["structure"]["sections"]) > 0),
        ("Statistics", len(stats) > 0),
        ("Validation", validation["is_valid"])
    ]
    
    print("\nSummary:")
    for item, success in success_items:
        status = "✓" if success else "✗"
        print(f"  {status} {item}")
    
    overall_success = sum(s for _, s in success_items) >= 3
    return overall_success


if __name__ == "__main__":
    # Test with AMPLE2.pdf if it exists
    test_pdf = Path("input/AMPLE2.pdf")
    
    if not test_pdf.exists():
        print(f"Test PDF not found: {test_pdf}")
        sys.exit(1)
    
    success = test_full_pipeline(test_pdf)
    sys.exit(0 if success else 1)