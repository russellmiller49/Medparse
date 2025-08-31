# scripts/filters.py
CLINICAL_TUIS = {"T047","T191","T061","T059","T060","T121","T200","T123","T184"}
GENERIC = {"text","value","study","group","table","figure","acknowledgements","references"}

def keep(term: str, tui: str|None, score: float, min_score: float = 0.6) -> bool:
    if term.lower() in GENERIC: return False
    if tui and tui not in CLINICAL_TUIS: return False
    return score >= min_score