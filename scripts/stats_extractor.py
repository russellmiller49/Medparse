import re
from typing import List, Dict, Any

STAT_PATTERNS = {
    "p_value": r'\b[Pp]\s*[=<>≤≥]\s*(?:0?\.\d+|0)\b',
    "confidence_interval": r'(?:95%?\s*CI[:=]?\s*)?\[?\(?\s*(-?\d+\.?\d*)\s*[-–,]\s*(-?\d+\.?\d*)\s*\]?\)?',
    "hazard_ratio": r'\bHR\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)\b',
    "odds_ratio": r'\bOR\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)\b',
    "relative_risk": r'\bRR\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)\b',
    "sample_size": r'\b[Nn]\s*=\s*([0-9,]+)\b',
}

def extract_statistics(text: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for stat_type, pattern in STAT_PATTERNS.items():
        for m in re.finditer(pattern, text):
            results.append({
                "type": stat_type,
                "value": m.group(0),
                "span": [m.start(), m.end()],
                "context": text[max(0, m.start()-80): m.end()+80]
            })
    return results