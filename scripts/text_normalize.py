# scripts/text_normalize.py
"""Text normalization utilities - fix ligatures, hyphens, artifacts without mutating source."""

import re
import unicodedata
from typing import Iterable, List, Optional

# Common ligature mappings
LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi", 
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
}

# Character replacements for various dashes and spaces
CHAR_MAP = {
    "\u2010": "-",  # Hyphen
    "\u2011": "-",  # Non-breaking hyphen
    "\u2012": "-",  # Figure dash
    "\u2013": "-",  # En dash
    "\u2014": "-",  # Em dash
    "\u2212": "-",  # Minus sign
    "\u00a0": " ",  # Non-breaking space
    "\u202f": " ",  # Narrow no-break space
    "\u2009": " ",  # Thin space
    "\u2007": " ",  # Figure space
}


def normalize_text(s: str) -> str:
    """
    Normalize text for NLP processing.
    
    This function:
    - Fixes Unicode ligatures
    - Normalizes dashes and spaces
    - Removes PDF extraction artifacts
    - De-hyphenates line breaks
    - Collapses whitespace
    
    Args:
        s: Input text
        
    Returns:
        Normalized text (original is never modified)
    """
    if not s:
        return s
    
    # Unicode normalization (NFKC)
    s = unicodedata.normalize("NFKC", s)
    
    # Replace ligatures
    for lig, replacement in LIGATURES.items():
        s = s.replace(lig, replacement)
    
    # Replace special characters
    for char, replacement in CHAR_MAP.items():
        s = s.replace(char, replacement)
    
    # Remove spurious "e/uniFB.." artifacts from bad PDF extraction
    s = re.sub(r"(?i)e/uniFB0+([a-z])", r"ef\1", s)
    
    # Remove other Unicode artifacts
    s = re.sub(r"\\u[0-9a-fA-F]{4}", "", s)
    
    # De-hyphenate on line breaks: "statis-\n tics" → "statistics"
    s = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", s)
    
    # Fix common OCR errors
    s = re.sub(r"\bl\s+l\b", "ll", s)  # "l l" -> "ll"
    s = re.sub(r"\bi\s+i\b", "ii", s)  # "i i" -> "ii"
    
    # Collapse multiple spaces to single space
    s = re.sub(r"[ \t]+", " ", s)
    
    # Normalize line breaks
    s = re.sub(r"\s*\n\s*", "\n", s)
    
    # Remove leading/trailing whitespace
    s = s.strip()
    
    return s


def normalize_paragraphs(paragraphs: Iterable[str]) -> List[str]:
    """
    Normalize a list of paragraphs.
    
    Args:
        paragraphs: Iterable of paragraph strings
        
    Returns:
        List of normalized paragraphs
    """
    return [normalize_text(p) for p in paragraphs if p]


def detect_ligature_ratio(text: str) -> float:
    """
    Detect the ratio of ligatures in text (for validation).
    
    Args:
        text: Input text
        
    Returns:
        Ratio of ligature characters to total characters
    """
    if not text:
        return 0.0
    
    ligature_count = sum(text.count(lig) for lig in LIGATURES.keys())
    total_chars = len(text)
    
    if total_chars == 0:
        return 0.0
    
    return ligature_count / total_chars


def remove_inline_expansions(text: str) -> str:
    """
    Remove incorrectly inserted inline expansions like 'Odds ratio (or)'.
    
    Args:
        text: Text possibly containing inline expansions
        
    Returns:
        Cleaned text
    """
    # Pattern to match incorrectly inserted statistical term expansions
    patterns = [
        r'\bOdds ratio \(or\)',
        r'\bHazard ratio \(hr\)',
        r'\bRelative risk \(rr\)',
        r'\bConfidence interval \(ci\)',
        r'\bStandard deviation \(sd\)',
    ]
    
    cleaned = text
    for pattern in patterns:
        # Replace with just the term without the incorrect expansion
        term = pattern.split(r' \(')[0].replace(r'\b', '')
        cleaned = re.sub(pattern, term, cleaned, flags=re.IGNORECASE)
    
    return cleaned


def normalize_for_nlp(text: str, remove_expansions: bool = True) -> str:
    """
    Full normalization pipeline for NLP processing.
    
    Args:
        text: Input text
        remove_expansions: Whether to remove inline expansions
        
    Returns:
        Fully normalized text
    """
    # First apply standard normalization
    normalized = normalize_text(text)
    
    # Then remove inline expansions if requested
    if remove_expansions:
        normalized = remove_inline_expansions(normalized)
    
    return normalized


def create_normalized_copy(doc: dict) -> dict:
    """
    Create a normalized copy of document sections for NLP processing.
    
    Args:
        doc: Document dict with structure.sections
        
    Returns:
        Document dict with normalized text (original unchanged)
    """
    import copy
    
    # Deep copy to avoid modifying original
    normalized_doc = copy.deepcopy(doc)
    
    # Normalize all section paragraphs
    structure = normalized_doc.get("structure", {})
    for section in structure.get("sections", []):
        if "paragraphs" in section:
            section["paragraphs"] = normalize_paragraphs(
                p.get("text", "") if isinstance(p, dict) else p
                for p in section["paragraphs"]
            )
    
    # Normalize figure captions
    for figure in structure.get("figures", []):
        if "caption" in figure:
            figure["caption"] = normalize_text(figure["caption"])
    
    # Normalize table captions
    for table in structure.get("tables", []):
        if "caption" in table:
            table["caption"] = normalize_text(table["caption"])
    
    return normalized_doc