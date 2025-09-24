from __future__ import annotations
from typing import List, Dict, Any, Optional

_MATCHER_CACHE: Dict[str, Any] = {}


def _get_quickumls_matcher(path: str, threshold: float = 0.9):
    """Load and cache a QuickUMLS matcher for the given installation path."""
    if path in _MATCHER_CACHE:
        return _MATCHER_CACHE[path]

    from quickumls import QuickUMLS  # Imported lazily to avoid import-time failure on py>=3.12

    matcher = QuickUMLS(
        path,
        threshold=threshold,
        similarity_name="cosine",
        window=5,
        min_match_length=3,
    )
    _MATCHER_CACHE[path] = matcher
    return matcher


def link_with_quickumls(
    text: str,
    quickumls_path: Optional[str] = None,
    min_score: float = 0.75,
) -> List[Dict[str, Any]]:
    """Link entities using a local QuickUMLS installation."""

    if not text or not text.strip():
        return []

    if not quickumls_path:
        return []

    try:
        matcher = _get_quickumls_matcher(quickumls_path)
    except Exception:
        return []

    try:
        results = matcher.match(text, ignore_syntax=False)
    except Exception:
        return []

    linked: List[Dict[str, Any]] = []
    for group in results:
        if not group:
            continue

        best = group[0]
        score = float(best.get("similarity", 0.0) or 0.0)
        if score < min_score:
            continue

        semtypes = list(best.get("semtypes", []))
        tui = semtypes[0] if semtypes else None
        term = best.get("term") or best.get("ngram") or ""

        linked.append(
            {
                "text": term,
                "term": term,
                "cui": best.get("cui", ""),
                "tui": tui,
                "semtypes": semtypes,
                "score": score,
                "start": best.get("start"),
                "end": best.get("end"),
                "preferred": bool(best.get("preferred")),
                "source": "QuickUMLS",
            }
        )

    return linked

def link_with_scispacy(text: str, model: str = "en_core_sci_md") -> List[Dict[str,Any]]:
    try:
        import spacy
        from scispacy.umls_linking import UmlsEntityLinker
    except Exception:
        return []
    nlp = spacy.load(model)
    nlp.add_pipe("abbreviation_detector")
    linker = UmlsEntityLinker(resolve_abbreviations=True, max_entities_per_mention=1)
    nlp.add_pipe(linker)
    doc = nlp(text[:500000])
    out = []
    for ent in doc.ents:
        if not ent._.umls_ents: continue
        cui, score = ent._.umls_ents[0]
        pref = ""
        if hasattr(linker, "umls") and hasattr(linker.umls, "cui_to_entity") and cui in linker.umls.cui_to_entity:
            pref = linker.umls.cui_to_entity[cui].canonical_name
        out.append({"phrase": ent.text, "cui": cui, "preferred": pref, "source": "scispaCy"})
    return out
