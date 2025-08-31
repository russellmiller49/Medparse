# scripts/linking/quickumls_fallback.py
"""QuickUMLS local matcher for fast entity linking."""

import os
from typing import Optional, Dict, List
from .types import VALID_TUIS, MIN_SCORE

# QuickUMLS instance (lazy loaded)
_matcher_cache = None


def get_quickumls_matcher():
    """Load and cache QuickUMLS matcher."""
    global _matcher_cache
    
    if _matcher_cache is not None:
        return _matcher_cache
    
    quickumls_path = os.getenv("QUICKUMLS_PATH")
    if not quickumls_path or not os.path.exists(quickumls_path):
        return None
    
    try:
        from quickumls import QuickUMLS
        _matcher_cache = QuickUMLS(
            quickumls_path,
            threshold=MIN_SCORE,
            window=5,  # Context window for matching
            similarity_name="cosine",
            min_match_length=3,
            accepted_semtypes=list(VALID_TUIS) if VALID_TUIS else None
        )
        return _matcher_cache
    except Exception as e:
        print(f"Failed to load QuickUMLS from {quickumls_path}: {e}")
        return None


def quickumls_match(term: str) -> Optional[Dict]:
    """
    Match term using QuickUMLS local index.
    
    Args:
        term: Term to match
        
    Returns:
        Best CUI match with metadata, or None
    """
    if not term or len(term.strip()) < 2:
        return None
    
    matcher = get_quickumls_matcher()
    if not matcher:
        return None
    
    try:
        matches = matcher.match(term, best_match=True, ignore_syntax=False)
    except Exception as e:
        print(f"QuickUMLS match error for '{term}': {e}")
        return None
    
    if not matches or not matches[0]:
        return None
    
    # Get best match
    best_group = matches[0]
    if not best_group:
        return None
    
    best = best_group[0]
    
    # Extract semantic types
    tuis = set(best.get("semtypes", []))
    
    # Apply TUI filter
    if VALID_TUIS and not tuis.intersection(VALID_TUIS):
        return None
    
    return {
        "cui": best["cui"],
        "name": best.get("term", term),
        "tuis": list(tuis),
        "score": best.get("similarity", 0.0),
        "preferred_term": best.get("preferred", 1) == 1
    }


def quickumls_match_all(term: str, max_matches: int = 3) -> List[Dict]:
    """
    Get all matches for a term using QuickUMLS.
    
    Args:
        term: Term to match
        max_matches: Maximum number of matches to return
        
    Returns:
        List of CUI matches with metadata
    """
    if not term or len(term.strip()) < 2:
        return []
    
    matcher = get_quickumls_matcher()
    if not matcher:
        return []
    
    try:
        matches = matcher.match(term, best_match=False, ignore_syntax=False)
    except Exception as e:
        print(f"QuickUMLS match error for '{term}': {e}")
        return []
    
    results = []
    seen_cuis = set()
    
    for match_group in matches[:max_matches]:
        if not match_group:
            continue
        
        for match in match_group:
            cui = match.get("cui")
            if not cui or cui in seen_cuis:
                continue
            seen_cuis.add(cui)
            
            # Extract semantic types
            tuis = set(match.get("semtypes", []))
            
            # Apply TUI filter
            if VALID_TUIS and not tuis.intersection(VALID_TUIS):
                continue
            
            results.append({
                "cui": cui,
                "name": match.get("term", term),
                "tuis": list(tuis),
                "score": match.get("similarity", 0.0),
                "preferred_term": match.get("preferred", 1) == 1
            })
    
    return results


def is_quickumls_available() -> bool:
    """Check if QuickUMLS is available and configured."""
    quickumls_path = os.getenv("QUICKUMLS_PATH")
    if not quickumls_path:
        return False
    
    # Check if path exists and contains expected files
    if not os.path.exists(quickumls_path):
        return False
    
    # Check for key QuickUMLS files
    expected_files = ["cui_semtypes.db", "umls_simstring.db"]
    for filename in expected_files:
        if not os.path.exists(os.path.join(quickumls_path, filename)):
            return False
    
    # Try to import QuickUMLS
    try:
        import quickumls
        return True
    except ImportError:
        return False