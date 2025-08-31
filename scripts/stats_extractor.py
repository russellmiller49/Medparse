# scripts/stats_extractor.py
import re
from typing import List, Dict, Optional, Tuple

# Statistical patterns with improved precision
STAT_PATTERNS = {
    "p_value": re.compile(
        r'\b[Pp]\s*([=<>≤≥])\s*(0?\.\d+)\b',
        re.IGNORECASE
    ),
    "ci_95": re.compile(
        r'(?:95%?\s*CI[:=]?\s*)?\[?\(?\s*(-?\d+\.?\d*)\s*[-–,;]\s*(-?\d+\.?\d*)\s*\]?\)?',
        re.IGNORECASE
    ),
    "hr": re.compile(
        r'\bHR\s*[:=]\s*(\d+\.?\d*)\b',
        re.IGNORECASE
    ),
    "or": re.compile(
        r'\bOR\s*[:=]\s*(\d+\.?\d*)\b',
        re.IGNORECASE
    ),
    "rr": re.compile(
        r'\bRR\s*[:=]\s*(\d+\.?\d*)\b',
        re.IGNORECASE
    ),
    "mean_sd": re.compile(
        r'\b(\d+\.?\d*)\s*±\s*(\d+\.?\d*)\b'
    ),
    "sample_size": re.compile(
        r'\b[Nn]\s*=\s*(\d+)\b'
    ),
    "percentage": re.compile(
        r'\b(\d+\.?\d*)%'
    ),
    "correlation": re.compile(
        r'\b[rR]\s*=\s*([+-]?0?\.\d+)\b'
    ),
}

# Context window for capturing surrounding text
CONTEXT_WINDOW = 140


def extract_statistics(text: str) -> List[Dict]:
    """
    Extract statistical values from text with their spans and context.
    Never modifies the original text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        List of dicts with:
            - type: Type of statistic (p_value, ci_95, etc.)
            - value: The matched text
            - start: Start character position
            - end: End character position
            - context: Surrounding text for context
    """
    hits = []
    
    for stat_type, pattern in STAT_PATTERNS.items():
        for match in pattern.finditer(text):
            # Extract context window
            context_start = max(0, match.start() - CONTEXT_WINDOW)
            context_end = min(len(text), match.end() + CONTEXT_WINDOW)
            context = text[context_start:context_end]
            
            hit = {
                "type": stat_type,
                "value": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "context": context
            }
            
            # Add additional metadata for certain types
            if stat_type == "p_value" and match.lastindex >= 2:
                hit["operator"] = match.group(1)
                try:
                    hit["parsed_value"] = float(match.group(2))
                    hit["significant"] = hit["parsed_value"] < 0.05
                except:
                    pass
            elif stat_type == "ci_95" and match.lastindex >= 2:
                try:
                    hit["lower"] = float(match.group(1))
                    hit["upper"] = float(match.group(2))
                except:
                    pass
            
            hits.append(hit)
    
    # Sort by position in text
    hits.sort(key=lambda x: x["start"])
    
    return hits