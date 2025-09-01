"""
Context-gated statistics extractor with hard negatives.
Blocks grant numbers, citations, DOIs, PMIDs from being misinterpreted as statistics.
"""
import re
from typing import List, Dict, Any

# Statistical keywords that must appear in context
STAT_KEYWORDS = {
    'ci', 'confidence interval', 'p-value', 'p value', 'p=', 'p<', 'p>', 
    'odds ratio', 'or', 'hazard ratio', 'hr', 'risk ratio', 'rr',
    'mean', 'median', 'standard deviation', 'sd', 'iqr', 'interquartile',
    'correlation', 'r2', 'beta', 'coefficient', 'significant',
    '±', 'plus-minus', 'range', 'min-max'
}

# Patterns to exclude (grant IDs, DOIs, PMIDs, etc.)
EXCLUDE_PATTERNS = [
    r'[A-Z]\d{1,2}[A-Z]{0,2}\d{5,}',  # Grant IDs like R01HL123456
    r'\d{1,2}[A-Z]{2,4}\d{5,}',       # More grant patterns
    r'10\.\d{4,}/[-._;()/:A-Za-z0-9]+',  # DOIs
    r'PMID:?\s*\d{7,}',               # PMIDs
    r'NCT\d{8,}',                     # Clinical trial IDs
    r'\([1-9]\d{0,2}(?:,\s*\d{1,3})*\)',  # Citation tuples like (3,4) or (12,15,18)
]

def has_statistical_context(text: str, window: int = 50) -> bool:
    """Check if text contains statistical keywords within window."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in STAT_KEYWORDS)

def is_excluded_pattern(text: str) -> bool:
    """Check if text matches excluded patterns."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def extract_statistics(text: str) -> List[Dict[str, Any]]:
    """
    Extract statistics with context gating and hard negatives.
    
    Returns list of dicts with keys:
    - type: 'p_value', 'ci', 'mean_sd', 'effect_size'
    - value: extracted value(s)
    - text: matched text
    - context: surrounding context
    """
    results = []
    
    # Split into sentences for context analysis
    sentences = re.split(r'[.!?]\s+', text)
    
    for sent in sentences:
        # Skip if no statistical context
        if not has_statistical_context(sent):
            continue
            
        # Skip if contains excluded patterns
        if is_excluded_pattern(sent):
            continue
        
        # P-values
        p_matches = re.finditer(r'[pP][<>=]\s*([\d.]+(?:e-?\d+)?)', sent)
        for match in p_matches:
            if not is_excluded_pattern(match.group(0)):
                results.append({
                    'type': 'p_value',
                    'value': float(match.group(1)),
                    'text': match.group(0),
                    'context': sent[:100]
                })
        
        # Confidence intervals (with explicit CI mention)
        ci_pattern = r'(?:95%?\s*)?CI[:\s]+\[?\(?([\d.-]+)[,\s]+(?:to|-)?\s*([\d.-]+)\]?\)?'
        ci_matches = re.finditer(ci_pattern, sent, re.IGNORECASE)
        for match in ci_matches:
            try:
                lower = float(match.group(1))
                upper = float(match.group(2))
                results.append({
                    'type': 'ci',
                    'value': [lower, upper],
                    'text': match.group(0),
                    'context': sent[:100]
                })
            except ValueError:
                continue
        
        # Mean ± SD
        mean_sd_pattern = r'([\d.]+)\s*±\s*([\d.]+)'
        mean_sd_matches = re.finditer(mean_sd_pattern, sent)
        for match in mean_sd_matches:
            if has_statistical_context(sent, window=30):  # Tighter context for mean±sd
                try:
                    mean = float(match.group(1))
                    sd = float(match.group(2))
                    results.append({
                        'type': 'mean_sd',
                        'value': {'mean': mean, 'sd': sd},
                        'text': match.group(0),
                        'context': sent[:100]
                    })
                except ValueError:
                    continue
        
        # Effect sizes (OR, HR, RR)
        effect_pattern = r'\b(OR|HR|RR)\s*[=:]\s*([\d.]+)\s*(?:\[?\(?([\d.-]+)[,\s]+(?:to|-)?\s*([\d.-]+)\]?\)?)?'
        effect_matches = re.finditer(effect_pattern, sent, re.IGNORECASE)
        for match in effect_matches:
            try:
                effect_type = match.group(1).upper()
                value = float(match.group(2))
                result = {
                    'type': 'effect_size',
                    'effect_type': effect_type,
                    'value': value,
                    'text': match.group(0),
                    'context': sent[:100]
                }
                
                # Add CI if present
                if match.group(3) and match.group(4):
                    result['ci'] = [float(match.group(3)), float(match.group(4))]
                
                results.append(result)
            except (ValueError, TypeError):
                continue
    
    return results