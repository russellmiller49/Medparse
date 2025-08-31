import re
from typing import List, Dict, Tuple

# Statistical cue words that must appear in the SAME sentence as any numeric pattern
STAT_CUES = {
    "ci", "confidence interval", "odds ratio", "or", "risk ratio", "rr",
    "hazard ratio", "hr", "p=", "p <", "p>", "p<", "p >", "mean", "median", "sd",
    "standard deviation", "iqr", "interquartile", "±", "beta", "β"
}

RE_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z(])')
RE_HAS_LETTERS_AND_DIGITS = re.compile(r'(?=.*[A-Za-z])(?=.*\d)')
RE_CITATION_TUPLE = re.compile(r'^\(\s*\d{1,3}(\s*,\s*\d{1,3})+\s*\)$')
RE_GRANTISH = re.compile(r'[A-Za-z]\d[A-Za-z0-9-]+')  # e.g., U54HL119810-03

# Selected stat patterns (keep conservative)
RE_PVALUE = re.compile(r'\b[Pp]\s*([<=>])\s*0?\.\d+\b')
RE_CI = re.compile(r'(?:(?:95|90|99)\s*%?\s*)?CI\s*[:=]?\s*[\(\[]?\s*(-?\d+(?:\.\d+)?)\s*[–—-]\s*(-?\d+(?:\.\d+)?)\s*[\)\]]?', re.I)
RE_MEAN_SD = re.compile(r'\bmean\b[^.]*?\b(?:sd|standard deviation)\b[^.]*?(?:=|:)?\s*(-?\d+(?:\.\d+)?)[^.\d]+(\d+(?:\.\d+)?)', re.I)
RE_PLUS_MINUS = re.compile(r'(-?\d+(?:\.\d+)?)\s*[±]\s*(\d+(?:\.\d+)?)')
RE_EFFECT = re.compile(r'\b(?:OR|RR|HR)\b\s*(=|:)?\s*(-?\d+(?:\.\d+)?)')

def _has_stat_cue(sentence: str) -> bool:
    s = sentence.lower()
    return any(cue in s for cue in STAT_CUES)

def _is_grant_or_identifier(text: str) -> bool:
    # Only flag as grant if it matches the grant pattern specifically
    # Don't use the generic letters+digits check as it's too broad
    return bool(RE_GRANTISH.search(text))

def _is_pure_citation_tuple(token: str) -> bool:
    return bool(RE_CITATION_TUPLE.match(token.strip()))

def _iter_sentences(text: str):
    for chunk in RE_SENT_SPLIT.split(text):
        yield chunk.strip()

def extract_statistics(text: str) -> List[Dict]:
    """
    Conservative, context-gated statistics extractor.
    Returns a list of dicts with keys: type, value(s), text, sentence, span.
    """
    results: List[Dict] = []
    offset = 0
    for sent in _iter_sentences(text):
        if not sent:
            offset += 1  # keep moving
            continue

        # Hard negatives: grant-like or pure citations => skip unless we see cues
        has_cue = _has_stat_cue(sent)
        if not has_cue:
            # If the entire sentence looks like a citation run or contains grant-like tokens, skip quickly.
            if _is_grant_or_identifier(sent):
                offset += len(sent) + 1
                continue
            # Drop (3,4) etc. with no cues
            if _is_pure_citation_tuple(sent.strip()):
                offset += len(sent) + 1
                continue

        # p-values
        for m in RE_PVALUE.finditer(sent):
            if not has_cue:  # require cue for p-values too
                continue
            results.append({
                "type": "p_value", "value": m.group(0), "text": m.group(0),
                "sentence": sent
            })

        # confidence intervals
        for m in RE_CI.finditer(sent):
            if not has_cue:
                continue
            lo, hi = m.group(1), m.group(2)
            # sanity: reject if the matched window looks like an identifier
            if _is_grant_or_identifier(m.group(0)):
                continue
            results.append({
                "type": "ci", "value": [float(lo), float(hi)],
                "text": m.group(0), "sentence": sent
            })

        # mean ± sd
        for m in RE_PLUS_MINUS.finditer(sent):
            if not has_cue:
                continue
            results.append({
                "type": "mean_plusminus_sd", "value": [float(m.group(1)), float(m.group(2))],
                "text": m.group(0), "sentence": sent
            })

        # explicit mean/sd wording
        for m in RE_MEAN_SD.finditer(sent):
            if not has_cue:
                continue
            results.append({
                "type": "mean_sd", "value": [float(m.group(1)), float(m.group(2))],
                "text": m.group(0), "sentence": sent
            })

        # effect sizes OR/RR/HR
        for m in RE_EFFECT.finditer(sent):
            if not has_cue:
                continue
            results.append({
                "type": "effect_size", "metric": m.group(0).split()[0],
                "value": float(m.group(2)), "text": m.group(0), "sentence": sent
            })

        offset += len(sent) + 1
    return results