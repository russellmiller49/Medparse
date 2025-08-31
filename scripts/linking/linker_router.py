# scripts/linking/linker_router.py
"""Main router for entity linking - coordinates different linking strategies."""

from typing import List, Dict, Optional
from .scispacy_spans import get_spans
from .umls_api import umls_lookup_exact
from .quickumls_fallback import quickumls_match, is_quickumls_available


def link_entities(text: str, method: str = "auto") -> List[Dict]:
    """
    Find and link entities in text to medical concepts.
    
    This function:
    1) Finds entity spans using scispaCy
    2) Links them to UMLS concepts using specified method
    3) Returns entities with their character spans (never modifies text)
    
    Args:
        text: Text to analyze
        method: Linking method - "auto", "umls", "quickumls", or "scispacy_only"
                "auto" tries UMLS first, then QuickUMLS as fallback
        
    Returns:
        List of entities with:
            - text: The entity text
            - start: Start character position
            - end: End character position
            - cui: UMLS Concept Unique Identifier (if linked)
            - canonical: Preferred name for the concept
            - tuis: List of semantic type identifiers
            - source: Which linker was used
    """
    if not text or not text.strip():
        return []
    
    # Step 1: Get entity spans from scispaCy
    spans = get_spans(text)
    if not spans:
        return []
    
    # Step 2: Link each span to UMLS concepts
    entities = []
    
    for span in spans:
        entity_text = span["text"]
        
        # Skip if too short or too long
        if len(entity_text) < 2 or len(entity_text) > 100:
            continue
        
        # Try linking based on method
        result = None
        source = None
        
        if method == "scispacy_only":
            # Just return the spans without linking
            entities.append({
                **span,
                "cui": None,
                "canonical": entity_text,
                "tuis": [],
                "source": "scispacy"
            })
            continue
        
        elif method == "umls" or method == "auto":
            # Try UMLS API first
            result = umls_lookup_exact(entity_text)
            if result:
                source = "umls_api"
        
        if not result and (method == "quickumls" or method == "auto"):
            # Try QuickUMLS as fallback
            if is_quickumls_available():
                result = quickumls_match(entity_text)
                if result:
                    source = "quickumls"
        
        # If we got a result, add it to entities
        if result:
            entities.append({
                **span,
                "cui": result["cui"],
                "canonical": result["name"],
                "tuis": result.get("tuis", []),
                "score": result.get("score", 1.0),
                "source": source
            })
        elif method != "auto":
            # If specific method requested and failed, still include the span
            entities.append({
                **span,
                "cui": None,
                "canonical": entity_text,
                "tuis": [],
                "source": "unlinked"
            })
    
    return entities


def link_entities_comparative(text: str) -> Dict[str, List[Dict]]:
    """
    Run all three linking methods for comparison.
    
    Args:
        text: Text to analyze
        
    Returns:
        Dict with results from each method:
            - "umls": Entities linked with UMLS API
            - "quickumls": Entities linked with QuickUMLS
            - "scispacy": Just the spans from scispaCy
    """
    return {
        "umls": link_entities(text, method="umls"),
        "quickumls": link_entities(text, method="quickumls"),
        "scispacy": link_entities(text, method="scispacy_only")
    }


def deduplicate_entities(entities: List[Dict]) -> List[Dict]:
    """
    Remove duplicate entities based on CUI and overlapping spans.
    
    Args:
        entities: List of entities from link_entities()
        
    Returns:
        Deduplicated list of entities
    """
    if not entities:
        return []
    
    # Sort by start position
    entities = sorted(entities, key=lambda x: x["start"])
    
    deduplicated = []
    seen_spans = set()
    seen_cuis = {}
    
    for entity in entities:
        # Check for overlapping spans
        span_key = (entity["start"], entity["end"])
        if span_key in seen_spans:
            continue
        
        # Check for nearby same CUI (within 50 chars)
        cui = entity.get("cui")
        if cui:
            if cui in seen_cuis:
                last_pos = seen_cuis[cui]
                if abs(entity["start"] - last_pos) < 50:
                    continue
            seen_cuis[cui] = entity["start"]
        
        seen_spans.add(span_key)
        deduplicated.append(entity)
    
    return deduplicated


def filter_entities_by_type(entities: List[Dict], allowed_tuis: Optional[set] = None) -> List[Dict]:
    """
    Filter entities by semantic type.
    
    Args:
        entities: List of entities from link_entities()
        allowed_tuis: Set of allowed TUIs (uses VALID_TUIS if None)
        
    Returns:
        Filtered list of entities
    """
    if not allowed_tuis:
        from .types import VALID_TUIS
        allowed_tuis = VALID_TUIS
    
    if not allowed_tuis:
        return entities
    
    filtered = []
    for entity in entities:
        tuis = set(entity.get("tuis", []))
        if tuis.intersection(allowed_tuis):
            filtered.append(entity)
    
    return filtered