from typing import Dict, Any

def validate_extraction(doc: Dict[str, Any]) -> Dict[str, Any]:
    s = doc.get("structure", {})
    m = doc.get("metadata", {})
    tables = s.get("tables", [])
    figures = s.get("figures", [])

    checks = {
        "has_title": bool(m.get("title")),
        "has_authors": isinstance(m.get("authors"), list) and len(m.get("authors", [])) > 0,
        "authors_are_objects": isinstance(m.get("authors"), list) and all(isinstance(a, dict) and "family" in a for a in m.get("authors", [])),
        "has_sections": len(s.get("sections", [])) > 0,
        "tables_have_headers": all(t.get("headers") or t.get("columns") for t in tables) if tables else True,
        "figures_have_captions": all(f.get("caption") for f in figures) if figures else True,
        "references_parsed": len(m.get("references_text", [])) > 0,
        "umls_links_found": len(doc.get("umls_links", [])) > 0
    }
    total = len(checks)
    score = int(round(100 * sum(1 for v in checks.values() if v) / max(1, total)))

    issues = []
    if score < 60: issues.append("Low extraction completeness")
    if not checks["has_sections"]: issues.append("No sections extracted - possible parsing failure")
    if not checks["references_parsed"]: issues.append("No references found - check GROBID processing")

    return {"validations": checks, "completeness_score": score, "issues": issues, "is_valid": len(issues) == 0}