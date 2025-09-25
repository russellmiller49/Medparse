# scripts/linker_router.py
from typing import List, Dict, Optional
from scripts.filters import keep

def link_umls_primary(text: str, umls_client) -> List[Dict]:
    """Link entities using UMLS with semantic filtering."""
    if not umls_client:
        return []
    
    # Extract candidate phrases from text
    import re
    from scripts.umls_linker import link_umls_phrases
    
    # Simple phrase extraction (can be improved)
    phrases = []
    # Extract noun phrases and medical terms
    sentences = text.split('.')
    for sent in sentences[:100]:  # Limit for performance
        # Simple pattern for medical terms - allow lowercase start
        candidates = re.findall(r'\b[a-zA-Z][a-z]+(?:\s+[a-z]+)*\b', sent)
        phrases.extend(candidates)
    
    # Use existing link_umls_phrases function
    hits = link_umls_phrases(phrases[:50], umls_client)  # Limit phrases for performance
    
    # Apply semantic filtering - allow results without TUI (UMLS API doesn't provide TUI by default)
    filtered_hits = []
    for h in hits:
        text_val = h.get("preferred", h.get("text", ""))
        tui_val = h.get("tui")
        score_val = h.get("score", 1.0)
        
        # If no TUI available (common with UMLS API), allow the result
        if tui_val is None:
            filtered_hits.append(h)
        else:
            # Apply normal filtering if TUI is available
            if keep(text_val, tui_val, score_val):
                filtered_hits.append(h)
    
    return filtered_hits

def link_quickumls(text: str, quick_path: str) -> List[Dict]:
    """Link entities using QuickUMLS with semantic filtering."""
    from scripts.local_linkers import link_with_quickumls
    hits = link_with_quickumls(text, quickumls_path=quick_path)
    out = []
    for h in hits:
        if keep(h.get("term", h.get("text", "")), h.get("tui"), h.get("score", 0.7), 0.7):
            out.append({
                "text": h.get("term", h.get("text", "")),
                "cui": h.get("cui"),
                "tui": h.get("tui"),
                "score": h.get("score", 0.7),
                "start": h.get("start"),
                "end": h.get("end"),
                "semtypes": h.get("semtypes", []),
                "preferred": h.get("preferred"),
                "source": "QuickUMLS"
            })
    return out

def link_scispacy(text: str, model: str = "en_core_sci_md") -> List[Dict]:
    """Link entities using scispaCy with semantic filtering."""
    from scripts.local_linkers import link_with_scispacy
    hits = link_with_scispacy(text, model=model)
    out = []
    for h in hits:
        if keep(h.get("text", ""), h.get("tui"), h.get("score", 0.7), 0.7):
            out.append({
                "text": h.get("text", ""),
                "cui": h.get("cui"),
                "tui": h.get("tui"),
                "score": h.get("score", 0.7),
                "start": h.get("start"),
                "end": h.get("end"),
                "source": "scispaCy"
            })
    return out
