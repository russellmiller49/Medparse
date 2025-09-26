"""Enhanced multi-source medical concept linker."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from scripts.cache_manager import CacheManager
from scripts.local_linkers import link_with_quickumls, link_with_scispacy
from .types import MIN_SCORE, VALID_TUIS
from .umls_api import umls_lookup_exact, umls_search_approximate

_ALLOWED_TUIS = frozenset(VALID_TUIS) if VALID_TUIS else frozenset()
_UMLS_MIN_CONFIDENCE = 0.8
_FALLBACK_MIN_CONFIDENCE = 0.65


@dataclass(slots=True)
class Candidate:
    cui: str
    preferred_term: str
    tui: List[str]
    synonyms: List[str] = field(default_factory=list)
    source: str = ""
    confidence: float = 0.0


@dataclass(slots=True)
class MentionBucket:
    text: str
    start: int
    end: int
    synonyms: set[str] = field(default_factory=set)
    candidates: Dict[str, Candidate] = field(default_factory=dict)

    def add_candidate(self, source: str, candidate: Candidate) -> None:
        self.candidates[source] = candidate
        self.synonyms.update(candidate.synonyms)
        if candidate.preferred_term:
            self.synonyms.add(candidate.preferred_term)


def _allowed_tui(tuis: Iterable[str]) -> bool:
    if not _ALLOWED_TUIS:
        return True
    return bool(set(t for t in tuis if t).intersection(_ALLOWED_TUIS))


def _clean_synonyms(values: Iterable[str], *, fallback: str) -> List[str]:
    items: List[str] = []
    seen: set[str] = set()
    for val in values:
        if not val:
            continue
        normalized = val.strip()
        if not normalized:
            continue
        # Guard extremely long synonyms
        if len(normalized) > 120:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        items.append(normalized)
    if fallback and fallback.strip():
        fallback_norm = fallback.strip()
        if fallback_norm.lower() not in seen:
            items.insert(0, fallback_norm)
    return items


def _build_quickumls_candidate(match: Dict[str, Any]) -> Optional[Candidate]:
    cui = str(match.get("cui", "")).strip()
    if not cui:
        return None

    tuis: List[str] = []
    semtypes = match.get("semtypes") or []
    if isinstance(semtypes, list):
        tuis = [str(t).strip() for t in semtypes if str(t).strip()]
    tui_single = match.get("tui")
    if tui_single and tui_single not in tuis:
        tuis.append(str(tui_single))

    if tuis and not _allowed_tui(tuis):
        return None

    preferred = match.get("preferred")
    if isinstance(preferred, bool):
        preferred_term = match.get("term") if preferred else match.get("text")
    else:
        preferred_term = match.get("preferred") or match.get("text")

    synonyms = match.get("synonyms") or []
    if isinstance(synonyms, list):
        synonym_list = [str(s).strip() for s in synonyms if str(s).strip()]
    else:
        synonym_list = [str(synonyms)] if synonyms else []

    score = float(match.get("score", 0.0) or 0.0)
    if score < MIN_SCORE:
        return None

    return Candidate(
        cui=cui,
        preferred_term=str(preferred_term or "").strip() or match.get("term", ""),
        tui=tuis,
        synonyms=synonym_list,
        source="QuickUMLS",
        confidence=score,
    )


def _build_scispacy_candidate(match: Dict[str, Any]) -> Optional[Candidate]:
    cui = str(match.get("cui", "")).strip()
    if not cui:
        return None

    tuis: List[str] = []
    if isinstance(match.get("tui"), list):
        tuis = [str(t).strip() for t in match["tui"] if str(t).strip()]
    elif isinstance(match.get("semtypes"), list):
        tuis = [str(t).strip() for t in match["semtypes"] if str(t).strip()]

    if tuis and not _allowed_tui(tuis):
        return None

    synonyms = match.get("synonyms") or []
    if not isinstance(synonyms, list):
        synonyms = [str(synonyms)] if synonyms else []

    return Candidate(
        cui=cui,
        preferred_term=str(match.get("preferred") or match.get("text") or "").strip(),
        tui=tuis,
        synonyms=[str(s).strip() for s in synonyms if str(s).strip()],
        source="scispaCy",
        confidence=float(match.get("score", 0.0) or 0.0),
    )


def _resolve_with_umls(
    phrase: str,
    *,
    cache: Optional[CacheManager],
    resolution_cache: Dict[str, Optional[Candidate]],
) -> Optional[Candidate]:
    key = phrase.lower().strip()
    if not key:
        return None

    if key in resolution_cache:
        return resolution_cache[key]

    cache_key = f"concept::{key}"
    cached: Optional[Candidate] = None

    if cache:
        cached_obj = cache.get(cache_key)
        if isinstance(cached_obj, dict):
            cached_candidate = Candidate(
                cui=cached_obj.get("cui", ""),
                preferred_term=cached_obj.get("preferred_term", ""),
                tui=list(cached_obj.get("tui", [])),
                synonyms=list(cached_obj.get("synonyms", [])),
                source=cached_obj.get("source", "UMLS"),
                confidence=float(cached_obj.get("confidence", 1.0)),
            )
            resolution_cache[key] = cached_candidate
            return cached_candidate

    match = umls_lookup_exact(phrase)
    candidate: Optional[Candidate] = None

    def _candidate_from_umls(data: Dict[str, Any], confidence: float) -> Optional[Candidate]:
        tuis = data.get("tuis") or []
        if tuis and not _allowed_tui(tuis):
            return None
        return Candidate(
            cui=str(data.get("cui")),
            preferred_term=str(data.get("name") or phrase).strip(),
            tui=list(tuis),
            synonyms=[str(data.get("name") or phrase)],
            source="UMLS",
            confidence=confidence,
        )

    if match:
        candidate = _candidate_from_umls(match, 1.0)

    if not candidate:
        approx_list = umls_search_approximate(phrase)
        for approx in approx_list:
            confidence = float(approx.get("score", 0.0) or 0.0)
            if confidence < _UMLS_MIN_CONFIDENCE:
                continue
            candidate = _candidate_from_umls(approx, confidence)
            if candidate:
                break

    if candidate and cache:
        cache.set(
            cache_key,
            {
                "cui": candidate.cui,
                "preferred_term": candidate.preferred_term,
                "tui": candidate.tui,
                "synonyms": candidate.synonyms,
                "source": candidate.source,
                "confidence": candidate.confidence,
            },
        )

    resolution_cache[key] = candidate
    return candidate


def _ensure_bucket(
    buckets: Dict[Tuple[int, int, str], MentionBucket],
    *,
    text: str,
    start: Optional[int],
    end: Optional[int],
) -> Optional[MentionBucket]:
    if start is None or end is None:
        return None
    norm = text.strip()
    if not norm:
        return None
    key = (int(start), int(end), norm.lower())
    bucket = buckets.get(key)
    if not bucket:
        bucket = MentionBucket(text=norm, start=int(start), end=int(end))
        bucket.synonyms.add(norm)
        buckets[key] = bucket
    return bucket


def _choose_best_candidate(bucket: MentionBucket) -> Optional[Candidate]:
    ordered_sources = ("UMLS", "QuickUMLS", "scispaCy")
    for source in ordered_sources:
        candidate = bucket.candidates.get(source)
        if not candidate:
            continue
        if source == "UMLS" and candidate.confidence < _UMLS_MIN_CONFIDENCE:
            continue
        if source != "UMLS" and candidate.confidence < _FALLBACK_MIN_CONFIDENCE:
            continue
        if candidate.tui and not _allowed_tui(candidate.tui):
            continue
        return candidate
    return None


def link_medical_concepts(
    text: str,
    *,
    top_k: int = 20,
    quickumls_path: Optional[str] = None,
    cache: Optional[CacheManager] = None,
) -> List[Dict[str, Any]]:
    """Link text spans to medical concepts using multi-source fallback."""

    if not text or not text.strip():
        return []

    buckets: Dict[Tuple[int, int, str], MentionBucket] = {}

    # QuickUMLS detection
    quick_matches = link_with_quickumls(text, quickumls_path=quickumls_path)
    for match in quick_matches:
        bucket = _ensure_bucket(
            buckets,
            text=match.get("text") or match.get("term") or "",
            start=match.get("start"),
            end=match.get("end"),
        )
        if not bucket:
            continue
        candidate = _build_quickumls_candidate(match)
        if candidate:
            bucket.add_candidate("QuickUMLS", candidate)

    # scispaCy spans (with built-in linking)
    scispacy_matches = link_with_scispacy(text)
    for match in scispacy_matches:
        bucket = _ensure_bucket(
            buckets,
            text=match.get("text", ""),
            start=match.get("start"),
            end=match.get("end"),
        )
        if not bucket:
            continue
        candidate = _build_scispacy_candidate(match)
        if candidate:
            bucket.add_candidate("scispaCy", candidate)

    if not buckets:
        return []

    # Resolve with UMLS for each unique phrase
    resolution_cache: Dict[str, Optional[Candidate]] = {}
    for bucket in buckets.values():
        candidate = _resolve_with_umls(bucket.text, cache=cache, resolution_cache=resolution_cache)
        if candidate:
            bucket.add_candidate("UMLS", candidate)

    resolved: List[Dict[str, Any]] = []

    for bucket in sorted(buckets.values(), key=lambda b: (b.start, b.end)):
        candidate = _choose_best_candidate(bucket)
        if not candidate:
            continue
        synonyms = _clean_synonyms(bucket.synonyms, fallback=bucket.text)
        resolved.append(
            {
                "text": bucket.text,
                "start": bucket.start,
                "end": bucket.end,
                "cui": candidate.cui,
                "tui": candidate.tui,
                "semtypes": candidate.tui,
                "preferred_term": candidate.preferred_term or bucket.text,
                "preferred_name": candidate.preferred_term or bucket.text,
                "synonyms": synonyms,
                "source": candidate.source,
                "confidence": round(min(max(candidate.confidence, 0.0), 1.0), 4),
                "score": round(min(max(candidate.confidence, 0.0), 1.0), 4),
            }
        )

        if len(resolved) >= top_k:
            break

    return resolved


__all__ = ["link_medical_concepts"]
