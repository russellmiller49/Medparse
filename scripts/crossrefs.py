# scripts/crossrefs.py
"""Extract cross-references (figures, tables, citations) with spans."""

import re
from typing import List, Dict, Optional


def resolve_cross_refs(text: str) -> List[Dict]:
    """
    Find cross-references in text without modifying it.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of cross-references with:
            - type: "figure", "table", "citation", "supplementary"
            - text: The matched text
            - start: Start character position
            - end: End character position
            - target: What it refers to (e.g., "Figure 1", "Table 2")
            - index: Extracted number if applicable
    """
    refs = []
    
    # Figure references
    fig_pattern = re.compile(
        r'\b(Figure|Fig\.?|FIG\.?)\s+(\d+[A-Za-z]?(?:\s*[-–,]\s*\d+[A-Za-z]?)*)',
        re.IGNORECASE
    )
    for match in fig_pattern.finditer(text):
        refs.append({
            "type": "figure",
            "text": match.group(0),
            "start": match.start(),
            "end": match.end(),
            "target": match.group(0),
            "index": _extract_numbers(match.group(2))
        })
    
    # Table references
    table_pattern = re.compile(
        r'\b(Table|Tbl\.?)\s+(\d+[A-Za-z]?(?:\s*[-–,]\s*\d+[A-Za-z]?)*)',
        re.IGNORECASE
    )
    for match in table_pattern.finditer(text):
        refs.append({
            "type": "table",
            "text": match.group(0),
            "start": match.start(),
            "end": match.end(),
            "target": match.group(0),
            "index": _extract_numbers(match.group(2))
        })
    
    # Supplementary references
    supp_pattern = re.compile(
        r'\b(Supplementary|Supp\.?)\s+(Figure|Fig\.?|Table|Tbl\.?|Data|Material)\s+([S]?\d+[A-Za-z]?)',
        re.IGNORECASE
    )
    for match in supp_pattern.finditer(text):
        refs.append({
            "type": "supplementary",
            "text": match.group(0),
            "start": match.start(),
            "end": match.end(),
            "target": match.group(0),
            "index": _extract_numbers(match.group(3))
        })
    
    # Citation references (various formats)
    # Format: [1], [1,2,3], [1-3], (Smith et al., 2020)
    
    # Numeric citations in brackets
    bracket_cite_pattern = re.compile(r'\[(\d+(?:\s*[-–,]\s*\d+)*)\]')
    for match in bracket_cite_pattern.finditer(text):
        refs.append({
            "type": "citation",
            "text": match.group(0),
            "start": match.start(),
            "end": match.end(),
            "target": match.group(1),
            "index": _extract_numbers(match.group(1))
        })
    
    # Author-year citations
    author_year_pattern = re.compile(
        r'\(([A-Z][a-z]+(?:\s+(?:et\s+al\.?|and|&)\s+[A-Z][a-z]+)?),?\s+(19|20)\d{2}[a-z]?\)'
    )
    for match in author_year_pattern.finditer(text):
        refs.append({
            "type": "citation",
            "text": match.group(0),
            "start": match.start(),
            "end": match.end(),
            "target": match.group(0),
            "author": match.group(1),
            "year": match.group(2) + match.group(0)[match.start(2) - match.start():match.end()]
        })
    
    # Deduplicate overlapping matches
    refs = _remove_overlapping(refs)
    
    # Sort by position
    refs.sort(key=lambda x: x["start"])
    
    return refs


def _extract_numbers(text: str) -> List[int]:
    """
    Extract numbers from reference text.
    
    Args:
        text: Text like "1,2,3" or "1-3" or "1A"
        
    Returns:
        List of integers
    """
    numbers = []
    
    # Handle ranges (e.g., "1-3" -> [1, 2, 3])
    range_match = re.search(r'(\d+)\s*[-–]\s*(\d+)', text)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        numbers.extend(range(start, end + 1))
    else:
        # Extract individual numbers
        for num_match in re.finditer(r'\d+', text):
            numbers.append(int(num_match.group()))
    
    return numbers


def _remove_overlapping(refs: List[Dict]) -> List[Dict]:
    """
    Remove overlapping cross-references, keeping the most specific.
    
    Args:
        refs: List of cross-references
        
    Returns:
        Deduplicated list
    """
    if not refs:
        return []
    
    # Sort by start position
    refs.sort(key=lambda x: x["start"])
    
    filtered = []
    for ref in refs:
        # Check if this overlaps with any already accepted ref
        overlaps = False
        for existing in filtered:
            if (ref["start"] < existing["end"] and ref["end"] > existing["start"]):
                # They overlap - keep the longer/more specific one
                if len(ref["text"]) > len(existing["text"]):
                    # Replace the existing with this one
                    filtered.remove(existing)
                else:
                    overlaps = True
                    break
        
        if not overlaps:
            filtered.append(ref)
    
    return filtered


def link_cross_refs_to_targets(
    cross_refs: List[Dict],
    figures: List[Dict],
    tables: List[Dict],
    references: List[Dict]
) -> List[Dict]:
    """
    Link cross-references to their actual targets.
    
    Args:
        cross_refs: List of cross-references from resolve_cross_refs()
        figures: List of figures in document
        tables: List of tables in document
        references: List of references in document
        
    Returns:
        Cross-references with added "target_index" field
    """
    linked = []
    
    for ref in cross_refs:
        ref_copy = dict(ref)
        
        if ref["type"] == "figure" and ref.get("index"):
            # Link to figure by index
            for idx in ref["index"]:
                if 0 < idx <= len(figures):
                    ref_copy["target_index"] = idx - 1  # 0-based
                    ref_copy["target_data"] = figures[idx - 1]
                    break
        
        elif ref["type"] == "table" and ref.get("index"):
            # Link to table by index
            for idx in ref["index"]:
                if 0 < idx <= len(tables):
                    ref_copy["target_index"] = idx - 1
                    ref_copy["target_data"] = tables[idx - 1]
                    break
        
        elif ref["type"] == "citation" and ref.get("index"):
            # Link to reference by index
            for idx in ref["index"]:
                if 0 < idx <= len(references):
                    ref_copy["target_index"] = idx - 1
                    ref_copy["target_data"] = references[idx - 1]
                    break
        
        linked.append(ref_copy)
    
    return linked


def extract_cross_refs_from_sections(sections: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Extract cross-references from document sections.
    
    Args:
        sections: List of section dicts with paragraphs
        
    Returns:
        Dict mapping section index to list of cross-refs
    """
    section_refs = {}
    
    for i, section in enumerate(sections):
        all_refs = []
        
        # Process each paragraph
        for para in section.get("paragraphs", []):
            if isinstance(para, dict):
                text = para.get("text", "")
            else:
                text = str(para)
            
            if text:
                refs = resolve_cross_refs(text)
                all_refs.extend(refs)
        
        if all_refs:
            section_refs[str(i)] = all_refs
    
    return section_refs