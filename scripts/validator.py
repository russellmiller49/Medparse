# scripts/validator.py
"""Validate extraction quality for NLP-readiness."""

from typing import Dict, Any, List


def validate_extraction(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate document extraction quality.
    
    Args:
        doc: Extracted document dict
        
    Returns:
        Validation results with checks, score, and issues
    """
    meta = doc.get("metadata", {})
    struct = doc.get("structure", {})
    figures = struct.get("figures", [])
    tables = struct.get("tables", [])
    sections = struct.get("sections", [])
    
    # Count structured references and enriched references
    refs_struct = len(meta.get("references_struct", []))
    refs_enriched = len(doc.get("references_enriched", []))
    
    # Comprehensive validation checks
    checks = {
        # Metadata checks
        "has_title": bool(meta.get("title")),
        "has_authors": bool(meta.get("authors")),
        "authors_are_valid": _validate_authors(meta.get("authors", [])),
        
        # Structure checks
        "has_sections": bool(sections),
        "sections_have_content": _validate_sections(sections),
        
        # Table checks
        "has_tables": bool(tables),
        "tables_have_captions": all(t.get("caption") for t in tables) if tables else True,
        "tables_have_data": all(t.get("cells") or t.get("data") for t in tables) if tables else True,
        
        # Figure checks
        "has_figures": bool(figures),
        "figures_have_captions": all(f.get("caption") for f in figures) if figures else True,
        "figures_have_images": all(f.get("image_path") for f in figures) if figures else True,
        
        # Entity and statistics checks
        "has_entities": bool(doc.get("entities") or doc.get("umls_links") or doc.get("umls_links_local")),
        "has_statistics": bool(doc.get("statistics")),
        
        # Reference checks
        "has_references": bool(doc.get("references") or refs_struct > 0),
        "refs_structured": refs_struct > 0,
        "refs_enriched_some": refs_enriched > 0,
        "references_enriched": refs_enriched >= refs_struct * 0.5 if refs_struct > 0 else True,
        "has_references_csv": bool(doc.get("references_csv_path")),
        
        # Cross-reference checks
        "has_cross_refs": bool(doc.get("cross_refs")),
        
        # NLP-specific checks
        "umls_links": bool(doc.get("umls_links") or doc.get("umls_links_local")),
        "figures_textual_count": sum(1 for f in figures if f.get("ocr_text")) if figures else 0
    }
    
    # Calculate completeness score
    # Weight certain checks as more important
    weights = {
        "has_title": 2,
        "has_authors": 2,
        "has_sections": 2,
        "sections_have_content": 2,
        "has_entities": 1.5,
        "has_references": 1.5,
        "has_figures": 1,
        "has_tables": 1,
        "has_statistics": 1,
        "has_cross_refs": 0.5
    }
    
    weighted_score = 0
    total_weight = 0
    
    for check, value in checks.items():
        weight = weights.get(check, 1)
        if value:
            weighted_score += weight
        total_weight += weight
    
    score = int(round(100 * weighted_score / max(1, total_weight)))
    
    # Identify issues
    issues = []
    warnings = []
    
    # Critical issues
    if not checks["has_title"]:
        issues.append("Missing document title")
    if not checks["has_authors"]:
        issues.append("Missing authors")
    if not checks["has_sections"]:
        issues.append("No sections extracted - possible parsing failure")
    if not checks["sections_have_content"]:
        issues.append("Sections have no content")
    
    # Warnings (non-critical)
    if not checks["has_entities"]:
        warnings.append("No medical entities found")
    if not checks["has_statistics"]:
        warnings.append("No statistics extracted")
    if not checks["has_references"]:
        warnings.append("No references found - check GROBID processing")
    if checks["has_figures"] and not checks["figures_have_captions"]:
        warnings.append("Some figures missing captions")
    if checks["has_tables"] and not checks["tables_have_captions"]:
        warnings.append("Some tables missing captions")
    
    # Determine if valid for NLP
    is_valid = len(issues) == 0 and score >= 60
    
    return {
        "checks": checks,
        "completeness_score": score,
        "is_valid": is_valid,
        "issues": issues,
        "warnings": warnings,
        "quality_level": _get_quality_level(score)
    }


def _validate_authors(authors: List) -> bool:
    """Check if authors are properly structured."""
    if not authors:
        return False
    
    for author in authors:
        if not isinstance(author, dict):
            return False
        if not author.get("family") and not author.get("display"):
            return False
        
        # Check for affiliation bleed-through
        disp = (author.get("display") or "").lower()
        if any(tok in disp for tok in ["department","university","hospital","correspondence","orcid","email"]):
            return False
    
    return True


def _validate_sections(sections: List) -> bool:
    """Check if sections have actual content."""
    if not sections:
        return False
    
    total_paragraphs = 0
    for section in sections:
        paragraphs = section.get("paragraphs", [])
        for para in paragraphs:
            if isinstance(para, str):
                text = para
            elif isinstance(para, dict):
                text = para.get("text", "")
            else:
                continue
            
            if text and len(text.strip()) > 10:
                total_paragraphs += 1
    
    return total_paragraphs > 0


def _get_quality_level(score: int) -> str:
    """Get quality level description from score."""
    if score >= 90:
        return "excellent"
    elif score >= 75:
        return "good"
    elif score >= 60:
        return "acceptable"
    elif score >= 40:
        return "poor"
    else:
        return "failed"


def generate_validation_report(validation: Dict[str, Any]) -> str:
    """
    Generate a human-readable validation report.
    
    Args:
        validation: Validation dict from validate_extraction()
        
    Returns:
        Formatted report string
    """
    lines = [
        "=" * 60,
        "EXTRACTION VALIDATION REPORT",
        "=" * 60,
        "",
        f"Completeness Score: {validation['completeness_score']}%",
        f"Quality Level: {validation['quality_level'].upper()}",
        f"Valid for NLP: {'YES' if validation['is_valid'] else 'NO'}",
        ""
    ]
    
    if validation.get("issues"):
        lines.extend([
            "CRITICAL ISSUES:",
            "-" * 40
        ])
        for issue in validation["issues"]:
            lines.append(f"  ❌ {issue}")
        lines.append("")
    
    if validation.get("warnings"):
        lines.extend([
            "WARNINGS:",
            "-" * 40
        ])
        for warning in validation["warnings"]:
            lines.append(f"  ⚠️  {warning}")
        lines.append("")
    
    lines.extend([
        "DETAILED CHECKS:",
        "-" * 40
    ])
    
    checks = validation.get("checks", {})
    for check, value in checks.items():
        status = "✓" if value else "✗"
        # Make check names readable
        readable_name = check.replace("_", " ").title()
        lines.append(f"  {status} {readable_name}")
    
    lines.extend(["", "=" * 60])
    
    return "\n".join(lines)