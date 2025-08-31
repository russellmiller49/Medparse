import re
from typing import Iterable, List, Dict, Optional, Tuple, Set

STOP_PHRASE_RE = re.compile(r'^(history|hx)\s+of\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b', re.I)
NON_ALPHA_RE = re.compile(r'^[^A-Za-z]*$')

# Keep only useful UMLS semantic groups
ALLOWED_SEM_GROUPS: Set[str] = {"DISO", "PROC", "ANAT", "CHEM"}  # adjust as needed

def _normalize_tokens(text: str) -> List[str]:
    return [t for t in re.split(r'[^A-Za-z0-9]+', text.lower()) if t and t not in {"of","the","a","an","and","or","to","for","in"}]

def _valid_span_for_linking(text: str) -> bool:
    if not text or NON_ALPHA_RE.match(text):
        return False
    if STOP_PHRASE_RE.match(text.strip()):
        return False
    toks = _normalize_tokens(text)
    # Require at least 2 content tokens or a long medical-ish token
    return len(toks) >= 2 or any(len(t) >= 6 for t in toks)

def _overlap(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    union = len(sa | sb) or 1
    return inter / union

def link_umls_spans(
    spans: Iterable[Tuple[str, Tuple[int,int]]],
    *,
    kb_lookup,          # function(name) -> List[ { "cui":..., "name":..., "score":..., "semtypes":[...] } ]
    min_score: float = 0.85,
    min_overlap: float = 0.6
) -> List[Dict]:
    """
    Safer UMLS linker: applies span validity, candidate score cutoff,
    semantic group filter, and token-overlap.
    """
    out: List[Dict] = []
    for text, (start, end) in spans:
        if not _valid_span_for_linking(text):
            continue
        cand_list = kb_lookup(text) or []
        best: Optional[Dict] = None
        span_toks = _normalize_tokens(text)
        for cand in cand_list:
            if cand.get("score", 0.0) < min_score:
                continue
            if "semtypes" in cand and not set(cand["semtypes"]).intersection(ALLOWED_SEM_GROUPS):
                continue
            o = _overlap(span_toks, _normalize_tokens(cand.get("name","")))
            if o < min_overlap:
                continue
            if best is None or cand["score"] > best["score"]:
                best = cand
        if best:
            out.append({
                "text": text, "span": [start, end],
                "cui": best["cui"], "preferred_name": best.get("name"),
                "score": best.get("score"), "semtypes": best.get("semtypes", [])
            })
    return out