# scripts/linking/umls_api.py
"""UMLS API client for entity linking."""

import os
import httpx
from typing import Dict, Optional, List
from urllib.parse import quote
from .types import VALID_TUIS, MIN_SCORE

UMLS_API_KEY = os.getenv("UMLS_API_KEY")
UMLS_BASE = "https://uts-ws.nlm.nih.gov/rest"


def umls_lookup_exact(term: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Exact/near exact match using UMLS 'search' endpoint.
    
    Args:
        term: Term to search for
        use_cache: Whether to use cache (if available)
        
    Returns:
        Best CUI match with metadata, or None if no valid match
    """
    if not UMLS_API_KEY:
        return None
    
    if not term or len(term.strip()) < 2:
        return None
    
    # Try cache first if available
    if use_cache:
        try:
            from scripts.cache_manager import CacheManager
            cache = CacheManager()
            cached = cache.get_umls_lookup(term)
            if cached:
                return cached
        except:
            pass
    
    # Search UMLS
    params = {
        "string": term,
        "searchType": "exact",
        "apiKey": UMLS_API_KEY
    }
    
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{UMLS_BASE}/search/current", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        print(f"UMLS API error for '{term}': {e}")
        return None
    
    # Process results
    best = None
    results = data.get("result", {}).get("results", [])
    
    for res in results:
        cui = res.get("ui")
        name = res.get("name", "")
        
        if not cui or cui == "NONE":
            continue
        
        # Get detailed concept information
        try:
            concept_info = get_concept_details(cui)
            if not concept_info:
                continue
            
            # Check if semantic types match our filter
            tuis = concept_info.get("tuis", [])
            if VALID_TUIS and not set(tuis).intersection(VALID_TUIS):
                continue
            
            # Found a valid match
            best = {
                "cui": cui,
                "name": name,
                "tuis": tuis,
                "semtypes": concept_info.get("semtypes", []),
                "score": 1.0,
                "definition": concept_info.get("definition")
            }
            break
            
        except Exception as e:
            print(f"Error getting concept details for {cui}: {e}")
            continue
    
    # Cache the result
    if use_cache and best:
        try:
            from scripts.cache_manager import CacheManager
            cache = CacheManager()
            cache.cache_umls_lookup(term, best)
        except:
            pass
    
    return best


def get_concept_details(cui: str) -> Optional[Dict]:
    """
    Get detailed information about a UMLS concept.
    
    Args:
        cui: Concept Unique Identifier
        
    Returns:
        Dict with TUIs, semantic types, and definition
    """
    if not UMLS_API_KEY or not cui:
        return None
    
    params = {"apiKey": UMLS_API_KEY}
    
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{UMLS_BASE}/content/current/CUI/{quote(cui)}", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        print(f"Error fetching concept {cui}: {e}")
        return None
    
    result = data.get("result", {})
    
    # Extract semantic types
    semtypes = []
    tuis = []
    for sty in result.get("semanticTypes", []):
        name = sty.get("name", "")
        uri = sty.get("uri", "")
        if name:
            semtypes.append(name)
        if uri:
            # Extract TUI from URI (e.g., ".../TUI/T047" -> "T047")
            tui = uri.rsplit("/", 1)[-1]
            if tui.startswith("T"):
                tuis.append(tui)
    
    # Get definition if available
    definition = None
    definitions = result.get("definitions")
    if definitions and isinstance(definitions, list) and definitions:
        definition = definitions[0].get("value", "")
    
    return {
        "tuis": tuis,
        "semtypes": semtypes,
        "definition": definition
    }


def umls_search_approximate(term: str, threshold: float = 0.7) -> List[Dict]:
    """
    Approximate match using UMLS 'search' endpoint with normalizedString.
    
    Args:
        term: Term to search for
        threshold: Minimum similarity threshold
        
    Returns:
        List of CUI matches with metadata
    """
    if not UMLS_API_KEY or not term:
        return []
    
    params = {
        "string": term,
        "searchType": "normalizedString",
        "apiKey": UMLS_API_KEY,
        "pageSize": 5
    }
    
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{UMLS_BASE}/search/current", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        print(f"UMLS approximate search error for '{term}': {e}")
        return []
    
    matches = []
    results = data.get("result", {}).get("results", [])
    
    for res in results[:3]:  # Limit to top 3
        cui = res.get("ui")
        name = res.get("name", "")
        
        if not cui or cui == "NONE":
            continue
        
        # Simple similarity check based on term overlap
        term_lower = term.lower()
        name_lower = name.lower()
        
        # Calculate simple Jaccard similarity
        term_words = set(term_lower.split())
        name_words = set(name_lower.split())
        if term_words and name_words:
            similarity = len(term_words & name_words) / len(term_words | name_words)
        else:
            similarity = 0.0
        
        if similarity < threshold:
            continue
        
        # Get concept details
        try:
            concept_info = get_concept_details(cui)
            if not concept_info:
                continue
            
            tuis = concept_info.get("tuis", [])
            if VALID_TUIS and not set(tuis).intersection(VALID_TUIS):
                continue
            
            matches.append({
                "cui": cui,
                "name": name,
                "tuis": tuis,
                "semtypes": concept_info.get("semtypes", []),
                "score": similarity,
                "definition": concept_info.get("definition")
            })
            
        except Exception:
            continue
    
    return matches