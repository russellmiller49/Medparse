#!/usr/bin/env python3
"""Test the new modular pipeline with available components."""

from pathlib import Path
import json
import sys

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.docling_adapter import convert_pdf
from scripts.grobid_tei import parse_article_metadata
from scripts.text_normalize import normalize_for_nlp, detect_ligature_ratio, remove_inline_expansions
from scripts.stats_extractor import extract_statistics
from scripts.ref_extract import extract_refs_from_tei
from scripts.crossrefs import resolve_cross_refs
from scripts.validator import validate_extraction, generate_validation_report


def test_pipeline(pdf_path: Path):
    """Test core pipeline components."""
    
    print(f"Testing pipeline with: {pdf_path.name}")
    print("=" * 60)
    
    # Test 1: Docling adapter
    print("\n1. Testing Docling adapter...")
    try:
        docling_data = convert_pdf(pdf_path)
        print(f"   ✓ Sections: {len(docling_data.get('sections', []))}")
        print(f"   ✓ Figures: {len(docling_data.get('figures', []))}")
        print(f"   ✓ Tables: {len(docling_data.get('tables', []))}")
        print(f"   ✓ Text blocks: {len(docling_data.get('texts', []))}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        docling_data = {"sections": [], "figures": [], "tables": [], "texts": []}
    
    # Test 2: Text normalization
    print("\n2. Testing text normalization...")
    sample_text = """
    This is a test with ﬁgures and eﬀects.
    It has Odds ratio (or) incorrectly inserted.
    Some statis-
    tics split across lines.
    """
    
    normalized = normalize_for_nlp(sample_text)
    print(f"   Original: {repr(sample_text[:50])}")
    print(f"   Normalized: {repr(normalized[:50])}")
    
    # Check if ligatures were fixed
    if "ﬁ" not in normalized and "ﬀ" not in normalized:
        print("   ✓ Ligatures fixed")
    else:
        print("   ✗ Ligatures not fixed")
    
    # Check if inline expansions removed
    if "Odds ratio (or)" not in normalized:
        print("   ✓ Inline expansions removed")
    else:
        print("   ✗ Inline expansions still present")
    
    # Test 3: Build and normalize document
    print("\n3. Building document structure...")
    doc = {
        "metadata": {"title": "Test Document"},
        "structure": {
            "sections": docling_data.get("sections", []),
            "tables": docling_data.get("tables", []),
            "figures": docling_data.get("figures", [])
        }
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
    
    print(f"   Full text length: {len(fulltext)} chars")
    print(f"   Normalized length: {len(fulltext_normalized)} chars")
    
    # Check ligature ratio
    ligature_ratio = detect_ligature_ratio(fulltext)
    print(f"   Ligature ratio: {ligature_ratio:.4%}")
    
    # Test 4: Statistics extraction
    print("\n4. Testing statistics extraction...")
    stats = extract_statistics(fulltext_normalized)
    print(f"   Found {len(stats)} statistics")
    
    # Show first few
    for stat in stats[:3]:
        print(f"   - {stat['type']}: {stat['value']} at pos {stat['start']}-{stat['end']}")
    
    # Test 5: Cross-references
    print("\n5. Testing cross-reference extraction...")
    cross_refs = resolve_cross_refs(fulltext_normalized)
    print(f"   Found {len(cross_refs)} cross-references")
    
    # Count by type
    ref_types = {}
    for ref in cross_refs:
        ref_type = ref["type"]
        ref_types[ref_type] = ref_types.get(ref_type, 0) + 1
    
    for ref_type, count in ref_types.items():
        print(f"   - {ref_type}: {count}")
    
    # Test 6: Validation
    print("\n6. Testing validation...")
    doc["statistics"] = stats
    doc["cross_refs"] = cross_refs
    
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
    
    # Test 7: Sample output
    print("\n7. Creating sample output...")
    output = {
        "metadata": doc["metadata"],
        "structure_summary": {
            "sections": len(doc["structure"]["sections"]),
            "tables": len(doc["structure"]["tables"]),
            "figures": len(doc["structure"]["figures"])
        },
        "extraction_summary": {
            "statistics": len(stats),
            "cross_refs": len(cross_refs),
            "text_length": len(fulltext_normalized),
            "ligature_ratio": ligature_ratio
        },
        "validation": validation
    }
    
    output_path = Path(f"test_output_{pdf_path.stem}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"   Saved test output to: {output_path}")
    
    print("\n" + "=" * 60)
    print("Pipeline test complete!")
    
    return validation["is_valid"]


if __name__ == "__main__":
    # Test with AMPLE2.pdf if it exists
    test_pdf = Path("input/AMPLE2.pdf")
    
    if not test_pdf.exists():
        print(f"Test PDF not found: {test_pdf}")
        print("Please provide a PDF file as argument")
        sys.exit(1)
    
    success = test_pipeline(test_pdf)
    sys.exit(0 if success else 1)