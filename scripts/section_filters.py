# scripts/section_filters.py
import re

_AFFIL_TOKENS = {"department","university","hospital","institute","school","center","centre",
                 "email","correspondence","orcid"}
_DEGREE_TOKENS = {"md","phd","do","frcp","frcs","mbbs","mph","msc","ms","pharmd"}

def looks_like_author_line(text: str) -> bool:
    if not text: return False
    s = text.strip()
    if len(s) > 200: return True  # giant title usually an author list
    low = s.lower()
    # many delimiters + affiliation tokens or degrees
    if (s.count(",") + s.count(";")) >= 3 and any(t in low for t in _AFFIL_TOKENS):
        return True
    if any(t in low for t in _DEGREE_TOKENS) and (s.count(",") >= 2):
        return True
    # repeated patterns like "Surname X, Surname Y, ..."
    if re.findall(r"\b[A-Z][a-z]+ [A-Z](?:\.[A-Z]\.)?\b", s) and s.count(",") >= 2:
        return True
    return False

def drop_author_sections(struct: dict) -> None:
    secs = []
    for sec in struct.get("sections", []):
        title = (sec.get("title") or "").strip()
        if title and looks_like_author_line(title):
            continue
        secs.append(sec)
    struct["sections"] = secs