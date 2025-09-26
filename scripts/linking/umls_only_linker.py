"""UMLS-only medical concept linker as fallback when QuickUMLS/scispaCy fail."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .umls_api import umls_lookup_exact, umls_search_approximate


def link_medical_concepts_umls_only(
    text: str,
    *,
    top_k: int = 20,
    min_confidence: float = 0.8,
) -> List[Dict[str, Any]]:
    """Link text spans to medical concepts using only UMLS API.
    
    This is a fallback when QuickUMLS and scispaCy are not available.
    It performs simple tokenization and tries to match each word/phrase
    against the UMLS API.
    """
    if not text or not text.strip():
        return []

    results = []
    seen_cuis = set()
    
    # Common stop words to filter out
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
    }
    
    # Extract potential medical terms using simple heuristics
    # 1. Full text as a phrase
    # 2. Individual words (4+ characters, not stop words)
    # 3. Common medical term patterns
    
    # Split text into potential terms
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Try full phrase first, then individual words
    phrases_to_try = [text.strip()] + [word for word in words if len(word) >= 4 and word not in stop_words]
    
    # Remove duplicates while preserving order
    unique_phrases = []
    seen_phrases = set()
    for phrase in phrases_to_try:
        if phrase not in seen_phrases:
            unique_phrases.append(phrase)
            seen_phrases.add(phrase)
    
    for phrase in unique_phrases:
        if len(results) >= top_k:
            break
            
        # Find position in original text
        start_pos = text.lower().find(phrase)
        if start_pos == -1:
            start_pos = 0
        end_pos = start_pos + len(phrase)
        
        # Try exact match first
        exact_result = umls_lookup_exact(phrase)
        if exact_result and exact_result.get('cui') not in seen_cuis:
            seen_cuis.add(exact_result.get('cui'))
            results.append({
                'text': phrase,
                'start': start_pos,
                'end': end_pos,
                'cui': exact_result.get('cui'),
                'tui': exact_result.get('tuis', []),
                'semtypes': exact_result.get('tuis', []),
                'preferred_term': exact_result.get('name'),
                'preferred_name': exact_result.get('name'),
                'synonyms': [exact_result.get('name')] if exact_result.get('name') else [],
                'source': 'UMLS',
                'confidence': 1.0,
                'score': 1.0
            })
            continue
            
        # Try approximate search
        approx_results = umls_search_approximate(phrase)
        for approx in approx_results:
            if len(results) >= top_k:
                break
                
            confidence = float(approx.get('score', 0.0) or 0.0)
            if confidence >= min_confidence and approx.get('cui') not in seen_cuis:
                seen_cuis.add(approx.get('cui'))
                results.append({
                    'text': phrase,
                    'start': start_pos,
                    'end': end_pos,
                    'cui': approx.get('cui'),
                    'tui': approx.get('tuis', []),
                    'semtypes': approx.get('tuis', []),
                    'preferred_term': approx.get('name'),
                    'preferred_name': approx.get('name'),
                    'synonyms': [approx.get('name')] if approx.get('name') else [],
                    'source': 'UMLS',
                    'confidence': confidence,
                    'score': confidence
                })
                break  # Take only the best match for this phrase
    
    return results


__all__ = ["link_medical_concepts_umls_only"]
