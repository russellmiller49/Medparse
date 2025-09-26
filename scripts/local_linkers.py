from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple

_MATCHER_CACHE: Dict[str, Any] = {}
_SCISPACY_CACHE: Dict[Tuple[str, str], Tuple[Any, Any]] = {}


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

        synonyms = {term}
        alt = best.get("ngram")
        if isinstance(alt, str) and alt.strip():
            synonyms.add(alt.strip())

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
                "synonyms": sorted(synonyms),
                "source": "QuickUMLS",
            }
        )

    return linked

def _load_scispacy(model: str = "en_core_sci_md") -> Optional[Tuple[Any, Any]]:
    cache_key = (model, "scispacy")
    if cache_key in _SCISPACY_CACHE:
        return _SCISPACY_CACHE[cache_key]

    try:
        import spacy
        from scispacy.umls_linking import UmlsEntityLinker
    except Exception:
        return None

    try:
        nlp = spacy.load(model)
    except Exception:
        try:
            nlp = spacy.load("en_core_sci_sm")
        except Exception:
            return None

    if "abbreviation_detector" not in nlp.pipe_names:
        try:
            nlp.add_pipe("abbreviation_detector")
        except Exception:
            pass

    linker = UmlsEntityLinker(resolve_abbreviations=True, max_entities_per_mention=3)
    nlp.add_pipe(linker, last=True)
    _SCISPACY_CACHE[cache_key] = (nlp, linker)
    return _SCISPACY_CACHE[cache_key]


def link_with_scispacy(text: str, model: str = "en_core_sci_md") -> List[Dict[str, Any]]:
    resources = _load_scispacy(model)
    if not resources:
        return []

    nlp, linker = resources
    doc = nlp(text[:500000])
    out: List[Dict[str, Any]] = []
    umls_store = getattr(linker, "umls", None)
    cui_to_entity = getattr(umls_store, "cui_to_entity", {}) if umls_store else {}

    for ent in doc.ents:
        umls_ents = getattr(ent._, "umls_ents", None)
        if not umls_ents:
            continue
        cui, score = umls_ents[0]
        meta = cui_to_entity.get(cui)
        preferred = getattr(meta, "canonical_name", ent.text)
        tuis = list(getattr(meta, "types", []) or [])
        synonyms = list(getattr(meta, "aliases", []) or [])
        out.append(
            {
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "cui": cui,
                "tui": tuis,
                "semtypes": tuis,
                "preferred": preferred,
                "synonyms": synonyms,
                "score": float(score),
                "source": "scispaCy",
            }
        )
    return out
