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
    'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    'morning', 'afternoon', 'evening', 'night',
    'table', 'figure', 'page', 'section', 'chapter',
    'study', 'research', 'analysis', 'review', 'report'
}

def filter_umls_links(links: List[Dict[str, Any]], 
                      min_score: float = 0.7,
                      min_term_length: int = 3,
                      require_alphabetic: bool = True) -> List[Dict[str, Any]]:
    """
    Filter UMLS links for quality and relevance.
    
    Args:
        links: List of UMLS link dictionaries
        min_score: Minimum confidence score
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
        text = link.get('text', '').strip().lower()
        cui = link.get('cui', '')
        score = link.get('score', 0.0)
        tuis = link.get('semtypes', [])
        
        # Skip if blacklisted
        if text in BLACKLIST_TERMS:
            continue
        
        # Check score threshold
        if score < min_score:
            continue
        
        # Check term length
        if len(text) < min_term_length:
            continue
        
        # Require alphabetic characters
        if require_alphabetic and not any(c.isalpha() for c in text):
            continue
        
        # Check semantic types (if available)
        if tuis:
            # Must have at least one allowed TUI
            if not any(tui in ALLOWED_TUIS for tui in tuis):
                continue
        
        # Skip if term is just numbers or punctuation
        if text.replace(' ', '').replace('-', '').replace('.', '').isdigit():
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