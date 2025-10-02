"""
Precision UMLS filtering to eliminate noisy/incorrect medical concept links.
"""
from typing import List, Dict, Any, Set

# Allowed UMLS semantic types (TUIs)
ALLOWED_TUIS = {
    # Disorders
    'T020', 'T190', 'T049', 'T019', 'T047', 'T050', 'T033', 'T037', 'T048', 'T191', 'T046', 'T184',
    # Procedures
    'T060', 'T065', 'T058', 'T059', 'T063', 'T062', 'T061',
    # Anatomy
    'T017', 'T029', 'T023', 'T030', 'T031', 'T022', 'T025', 'T026', 'T018', 'T021', 'T024',
    # Chemicals & Drugs
    'T116', 'T195', 'T123', 'T122', 'T118', 'T103', 'T120', 'T104', 'T200', 'T111', 'T196', 'T126', 
    'T131', 'T125', 'T129', 'T130', 'T197', 'T119', 'T124', 'T114', 'T109', 'T115', 'T121', 'T192', 
    'T110', 'T127',
    # Genes & Molecular
    'T087', 'T088', 'T028', 'T085', 'T086', 'T116', 'T126', 'T123',
    # Physiology
    'T043', 'T045', 'T044', 'T042', 'T041', 'T032', 'T040', 'T039',
    # Devices
    'T074', 'T075', 'T203',
    # Clinical Findings
    'T033', 'T034', 'T184'
}

# Blacklisted terms (common false positives)
BLACKLIST_TERMS = {
    'history of three', 'history of two', 'history of one', 'history of four', 'history of five',
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'yes', 'no', 'none', 'all', 'some', 'many', 'few', 'several',
    'left', 'right', 'up', 'down', 'front', 'back', 
    'top', 'bottom', 'middle', 'center', 'side',
    'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    'morning', 'afternoon', 'evening', 'night', 'day', 'week', 'month', 'year',
    'table', 'figure', 'page', 'section', 'chapter', 'appendix', 'supplementary',
    'study', 'research', 'analysis', 'review', 'report', 'data', 'method',
    'first', 'second', 'third', 'fourth', 'fifth',
    'increase', 'decrease', 'change', 'difference',
    'patient', 'subject', 'participant', 'group', 'cohort',
    'result', 'finding', 'outcome', 'conclusion',
    'positive', 'negative', 'neutral'
}

# Blacklist patterns (regex)
import re
BLACKLIST_PATTERNS = [
    r'^history of \w+$',
    r'^number of \w+$',
    r'^part of \w+$',
    r'^one of \w+$',
    r'^\d+$',  # Pure numbers
    r'^[A-Z]$',  # Single letters
    r'^vs\.?$',  # vs or vs.
    r'^n\s*=\s*\d+$',  # n = 123
]

def filter_umls_links(links: List[Dict[str, Any]], 
                      min_score: float = 0.75,  # Increased threshold
                      min_term_length: int = 4,  # Increased minimum
                      require_alphabetic: bool = True) -> List[Dict[str, Any]]:
    """
    Filter UMLS links for quality and relevance with precision focus.
    
    Args:
        links: List of UMLS link dictionaries
        min_score: Minimum confidence score (default 0.75 for precision)
        min_term_length: Minimum term length in characters
        require_alphabetic: Require at least one alphabetic character
    
    Returns:
        Filtered list of high-quality UMLS links
    """
    filtered = []
    seen_terms = set()
    seen_cuis = set()
    
    for link in links:
        # Extract fields
        text = link.get('text', '').strip()
        text_lower = text.lower()
        cui = link.get('cui', '')
        score = link.get('score', 0.0)
        tuis = link.get('semtypes', [])
        
        # Skip if blacklisted (exact match)
        if text_lower in BLACKLIST_TERMS:
            continue
        
        # Skip if matches blacklist pattern
        if any(re.match(pattern, text_lower) for pattern in BLACKLIST_PATTERNS):
            continue
        
        # Check score threshold (stricter for precision)
        if score < min_score:
            continue
        
        # Check term length
        if len(text) < min_term_length:
            continue
        
        # Require alphabetic characters
        if require_alphabetic and not any(c.isalpha() for c in text):
            continue
        
        # Skip terms that are mostly numbers
        alpha_ratio = sum(1 for c in text if c.isalpha()) / len(text) if text else 0
        if alpha_ratio < 0.5:  # At least 50% alphabetic
            continue
        
        # Check semantic types (if available)
        if tuis:
            # Must have at least one allowed TUI
            if not any(tui in ALLOWED_TUIS for tui in tuis):
                continue
        
        # Skip if term is just numbers or punctuation
        if text.replace(' ', '').replace('-', '').replace('.', '').isdigit():
            continue
        
        # Skip generic medical terms without context
        generic_terms = {'disease', 'syndrome', 'disorder', 'condition', 'symptom', 'sign'}
        if text_lower in generic_terms and score < 0.9:
            continue
        
        # Deduplicate by term and CUI
        term_cui_key = f"{text}:{cui}"
        if term_cui_key in seen_terms:
            continue
        seen_terms.add(term_cui_key)
        
        # Keep only best score per CUI
        if cui in seen_cuis:
            # Find existing entry with this CUI
            for i, existing in enumerate(filtered):
                if existing.get('cui') == cui:
                    if score > existing.get('score', 0):
                        # Replace with better scoring match
                        filtered[i] = link
                    break
        else:
            filtered.append(link)
            seen_cuis.add(cui)
    
    return filtered

def get_link_quality_score(link: Dict[str, Any]) -> float:
    """
    Calculate quality score for a UMLS link.
    Higher scores indicate better quality matches.
    """
    score = link.get('score', 0.0)
    text = link.get('text', '')
    tuis = link.get('semtypes', [])
    
    # Boost score for high-priority semantic types
    priority_tuis = {'T047', 'T121', 'T060', 'T061'}  # Disease, Drug, Procedure
    if any(tui in priority_tuis for tui in tuis):
        score *= 1.2
    
    # Penalize very short terms
    if len(text) < 5:
        score *= 0.8
    
    # Penalize if no alphabetic characters
    if not any(c.isalpha() for c in text):
        score *= 0.5
    
    return score


def cluster_umls_links(links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate mention-level links into canonical concept clusters."""

    if not links:
        return []

    clusters: Dict[str, Dict[str, Any]] = {}

    for link in links:
        cui = link.get("cui")
        if not cui:
            continue

        bucket = clusters.setdefault(
            cui,
            {
                "cui": cui,
                "preferred_term": link.get("preferred_term") or link.get("preferred_name") or link.get("text"),
                "tui": set(link.get("semtypes") or link.get("tui") or []),
                "synonyms": set(),
                "sources": set(),
                "mentions": [],
                "max_confidence": 0.0,
                "total_confidence": 0.0,
                "negated_mentions": 0,
            },
        )

        bucket["sources"].add(link.get("source") or "unknown")

        if link.get("preferred_term") and (not bucket["preferred_term"] or link["preferred_term"]):
            bucket["preferred_term"] = link["preferred_term"]

        bucket["tui"].update(link.get("semtypes", []) or link.get("tui", []))

        for value in link.get("synonyms", []) or []:
            if value:
                bucket["synonyms"].add(value)
        if link.get("text"):
            bucket["synonyms"].add(link["text"])

        confidence = float(link.get("confidence") or link.get("score") or 0.0)
        bucket["max_confidence"] = max(bucket["max_confidence"], confidence)
        bucket["total_confidence"] += confidence

        mention = {
            "text": link.get("text"),
            "start": link.get("start"),
            "end": link.get("end"),
            "confidence": confidence,
            "source": link.get("source"),
            "negated": bool(link.get("negated")),
            "section_index": link.get("section_index"),
            "section_title": link.get("section_title"),
            "section_category": link.get("section_category"),
        }
        bucket["mentions"].append(mention)

        if mention["negated"]:
            bucket["negated_mentions"] += 1

    aggregated: List[Dict[str, Any]] = []
    for data in clusters.values():
        mention_count = len(data["mentions"])
        mean_confidence = data["total_confidence"] / mention_count if mention_count else 0.0
        entry = {
            "cui": data["cui"],
            "preferred_term": data["preferred_term"],
            "tui": sorted(t for t in data["tui"] if t),
            "synonyms": sorted(s for s in data["synonyms"] if s),
            "sources": sorted(s for s in data["sources"] if s),
            "mentions": data["mentions"],
            "max_confidence": round(data["max_confidence"], 4),
            "mean_confidence": round(mean_confidence, 4),
            "mention_count": mention_count,
            "negated_mentions": data["negated_mentions"],
            "has_negated_mentions": data["negated_mentions"] > 0,
            "all_mentions_negated": mention_count > 0 and data["negated_mentions"] == mention_count,
        }
        aggregated.append(entry)

    aggregated.sort(key=lambda item: (item["max_confidence"], item["mention_count"]), reverse=True)
    return aggregated
