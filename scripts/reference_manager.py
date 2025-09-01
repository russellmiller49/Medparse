"""
Ensure references are always present in the output.
Falls back to raw GROBID references if enrichment failed.
"""
from typing import Dict, Any, List

def ensure_references_enriched(doc: Dict[str, Any]) -> None:
    """
    Ensure metadata.references_enriched is non-empty.
    Falls back to GROBID raw references if enrichment failed.
    
    Modifies doc in-place.
    
    Args:
        doc: Document dictionary to update
    """
    metadata = doc.setdefault("metadata", {})
    
    # Check if we have enriched references
    refs_enriched = metadata.get("references_enriched", [])
    
    if not refs_enriched:
        # Try to fall back to raw GROBID references
        grobid_refs = doc.get("grobid", {}).get("references_tei", [])
        
        # Handle case where references_tei is a raw XML string
        if isinstance(grobid_refs, str) and grobid_refs.strip():
            # Try to extract from XML
            import re
            xml_content = grobid_refs
            # Look for title tags in the XML
            titles = re.findall(r'<title[^>]*>([^<]+)</title>', xml_content)
            
            if titles:
                # Create basic references from extracted data
                parsed_refs = []
                for i, title in enumerate(titles[:100]):  # Limit to first 100
                    ref = {"title": title.strip()}
                    # Try to find year near this title
                    title_pos = xml_content.find(title)
                    if title_pos > 0:
                        context = xml_content[max(0, title_pos-500):title_pos+500]
                        year_match = re.search(r'<date[^>]*>(\d{4})</date>', context)
                        if year_match:
                            ref["year"] = int(year_match.group(1))
                    parsed_refs.append(ref)
                grobid_refs = parsed_refs
        
        if grobid_refs and isinstance(grobid_refs, list):
            # Convert GROBID refs to a simpler format
            fallback_refs = []
            
            for ref in grobid_refs:
                if isinstance(ref, dict):
                    # Extract key fields
                    fallback_ref = {}
                    
                    # Title
                    title = ref.get("title", "")
                    if title:
                        fallback_ref["title"] = title
                    
                    # Authors
                    authors = ref.get("authors", [])
                    if authors:
                        fallback_ref["authors"] = authors
                    
                    # Year
                    year = ref.get("year")
                    if year:
                        fallback_ref["year"] = year
                    
                    # Journal/venue
                    journal = ref.get("journal") or ref.get("venue") or ref.get("publisher")
                    if journal:
                        fallback_ref["journal"] = journal
                    
                    # DOI
                    doi = ref.get("doi")
                    if doi:
                        fallback_ref["doi"] = doi
                    
                    # PMID
                    pmid = ref.get("pmid")
                    if pmid:
                        fallback_ref["pmid"] = pmid
                    
                    # Raw text fallback
                    raw_text = ref.get("raw_reference") or ref.get("text", "")
                    if raw_text and not fallback_ref:
                        # If we couldn't extract structured data, at least keep raw text
                        fallback_ref["raw_text"] = raw_text
                    
                    if fallback_ref:
                        fallback_refs.append(fallback_ref)
            
            if fallback_refs:
                metadata["references_enriched"] = fallback_refs
                metadata["references_source"] = "grobid_fallback"
        
        # Secondary fallback: Check structure.citations
        if not metadata.get("references_enriched"):
            citations = doc.get("structure", {}).get("citations", [])
            
            if citations:
                fallback_refs = []
                
                for cite in citations:
                    if isinstance(cite, dict):
                        ref = {}
                        
                        # Try to extract text
                        text = cite.get("text") or cite.get("reference") or str(cite)
                        if text:
                            ref["raw_text"] = text
                            
                            # Try to parse year
                            import re
                            year_match = re.search(r'\b(19|20)\d{2}\b', text)
                            if year_match:
                                ref["year"] = int(year_match.group())
                            
                            fallback_refs.append(ref)
                    elif isinstance(cite, str) and cite.strip():
                        fallback_refs.append({"raw_text": cite})
                
                if fallback_refs:
                    metadata["references_enriched"] = fallback_refs
                    metadata["references_source"] = "citations_fallback"
    
    # Ensure the field exists even if empty
    if "references_enriched" not in metadata:
        metadata["references_enriched"] = []
        metadata["references_source"] = "none"

def count_valid_references(refs: List[Dict[str, Any]]) -> int:
    """
    Count references that have meaningful content.
    
    Args:
        refs: List of reference dictionaries
        
    Returns:
        Number of valid references
    """
    valid_count = 0
    
    for ref in refs:
        if isinstance(ref, dict):
            # Check if it has any substantial field
            has_content = (
                ref.get("title") or
                ref.get("authors") or
                ref.get("doi") or
                ref.get("pmid") or
                (ref.get("raw_text", "").strip() and len(ref.get("raw_text", "")) > 10)
            )
            if has_content:
                valid_count += 1
    
    return valid_count

def merge_reference_sources(doc: Dict[str, Any]) -> None:
    """
    Merge references from multiple sources to maximize coverage.
    
    Args:
        doc: Document to update
    """
    metadata = doc.setdefault("metadata", {})
    
    # Collect from all sources
    all_refs = {}
    
    # 1. Enriched references (highest priority)
    for ref in metadata.get("references_enriched", []):
        if isinstance(ref, dict):
            # Use DOI or title as key
            key = ref.get("doi")
            if not key:
                key = ref.get("title", "").lower()[:50]
            if key:
                all_refs[key] = ref
    
    # 2. GROBID references
    for ref in doc.get("grobid", {}).get("references_tei", []):
        if isinstance(ref, dict):
            key = ref.get("doi")
            if not key:
                key = ref.get("title", "").lower()[:50]
            if key and key not in all_refs:
                all_refs[key] = ref
    
    # 3. Structure citations (lowest priority)
    for cite in doc.get("structure", {}).get("citations", []):
        if isinstance(cite, dict):
            text = cite.get("text", "")
            if text and len(text) > 10:
                key = text[:50].lower()
                if key not in all_refs:
                    all_refs[key] = {"raw_text": text}
    
    # Update with merged references
    if all_refs:
        metadata["references_enriched"] = list(all_refs.values())
        metadata["references_source"] = "merged"