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
    '±', 'plus-minus', 'range', 'min-max', 'geometric mean',
    'ratio of geometric means', 'adjusted', 'unadjusted'
}

# Section names that are likely to contain real statistics
STAT_SECTIONS = {
    'results', 'statistical analysis', 'outcomes', 'findings',
    'efficacy', 'safety', 'primary endpoint', 'secondary endpoint'
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
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in STAT_KEYWORDS)

def is_excluded_pattern(text: str) -> bool:
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def extract_statistics(text: str, section_name: str = None) -> List[Dict[str, Any]]:
    results = []
    in_stat_section = section_name and any(s in section_name.lower() for s in STAT_SECTIONS)
    sentences = re.split(r'[.!?]\s+', text)
    for sent in sentences:
        if in_stat_section:
            has_stat_pattern = bool(re.search(r'(?:\d+\.\d+\s*\([^)]*\d+\.\d+)|(?:p\s*[<>=]\s*\d)|(?:95%\s*CI)|(?:\b(?:OR|HR|RR)\s*\d)', sent, re.I))
            if not has_stat_pattern and not has_statistical_context(sent):
                continue
        else:
            if not has_statistical_context(sent):
                continue
        if not in_stat_section and is_excluded_pattern(sent):
            continue
        p_matches = re.finditer(r'[pP][<>=]\s*([\d.]+(?:e-?\d+)?)', sent)
        for match in p_matches:
            if not is_excluded_pattern(match.group(0)):
                results.append({'type': 'p_value','value': float(match.group(1)),'text': match.group(0),'context': sent[:100]})
        ci_pattern = r'(?:95%?\s*)?CI[:\s]+\[?\(?([\d.-]+)[,\s]+(?:to|-)?\s*([\d.-]+)\]?\)?'
        ci_matches = re.finditer(ci_pattern, sent, re.IGNORECASE)
        for match in ci_matches:
            try:
                lower = float(match.group(1)); upper = float(match.group(2))
                results.append({'type': 'ci','value': [lower, upper],'text': match.group(0),'context': sent[:100]})
            except ValueError:
                continue
        mean_sd_pattern = r'([\d.]+)\s*±\s*([\d.]+)'
        mean_sd_matches = re.finditer(mean_sd_pattern, sent)
        for match in mean_sd_matches:
            if has_statistical_context(sent, window=30):
                try:
                    mean = float(match.group(1)); sd = float(match.group(2))
                    results.append({'type': 'mean_sd','value': {'mean': mean, 'sd': sd},'text': match.group(0),'context': sent[:100]})
                except ValueError:
                    continue
        effect_pattern = r'\b(OR|HR|RR)\s*[=:]\s*([\d.]+)\s*(?:\[?\(?([\d.-]+)[,\s]+(?:to|-)?\s*([\d.-]+)\]?\)?)?'
        effect_matches = re.finditer(effect_pattern, sent, re.IGNORECASE)
        for match in effect_matches:
            try:
                effect_type = match.group(1).upper(); value = float(match.group(2))
                result = {'type': 'effect_size','effect_type': effect_type,'value': value,'text': match.group(0),'context': sent[:100]}
                if match.group(3) and match.group(4):
                    result['ci'] = [float(match.group(3)), float(match.group(4))]
                results.append(result)
            except (ValueError, TypeError):
                continue
        geom_pattern = r'ratio of geometric means\s+([\d.·]+)\s*\[?\(?\s*(?:95%?\s*)?CI\s*([\d.·]+)[–-]([\d.·]+)'
        geom_matches = re.finditer(geom_pattern, sent, re.IGNORECASE)
        for match in geom_matches:
            try:
                value = float(match.group(1).replace('·', '.'))
                ci_lower = float(match.group(2).replace('·', '.'))
                ci_upper = float(match.group(3).replace('·', '.'))
                results.append({'type': 'geometric_mean_ratio','value': value,'ci': [ci_lower, ci_upper],'text': match.group(0),'context': sent[:100]})
            except ValueError:
                continue
        general_ci_pattern = r'([\d.·]+)\s*\(\s*(?:95%?\s*)?CI\s*([\d.·]+)[–-]([\d.·]+)\)'
        general_matches = re.finditer(general_ci_pattern, sent)
        for match in general_matches:
            if has_statistical_context(sent[max(0, match.start()-30):min(len(sent), match.end()+30)]):
                try:
                    value = float(match.group(1).replace('·', '.'))
                    ci_lower = float(match.group(2).replace('·', '.'))
                    ci_upper = float(match.group(3).replace('·', '.'))
                    results.append({'type': 'value_with_ci','value': value,'ci': [ci_lower, ci_upper],'text': match.group(0),'context': sent[:100]})
                except ValueError:
                    continue
    return results

