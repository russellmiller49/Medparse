import re
from typing import Optional, Dict, Any, List

try:
    from dateutil.parser import parse as dtparse  # type: ignore
except Exception:  # pragma: no cover
    dtparse = None

YEAR_RX = re.compile(r"(?:19|20)\d{2}")
HEAD_MATCH = {"abstract", "summary", "overview", "synopsis"}


def normalize_year(meta: Dict[str, Any]) -> Dict[str, Any]:
    raw = meta.get("year")

    def to_year(s: Any) -> Optional[int]:
        if dtparse is None:
            # fallback: extract first 4-digit year
            m = YEAR_RX.search(str(s))
            return int(m.group(0)) if m else None
        try:
            y = dtparse(str(s)).year
            return y
        except Exception:
            return None

    if isinstance(raw, int):
        return {"changed": False}

    if isinstance(raw, str) and raw.strip():
        y = to_year(raw)
        if y:
            pub = meta.setdefault("published", {"print": None, "online": None})
            if not pub.get("online"):
                pub["online"] = raw
            meta["year"] = y
            return {"changed": True, "source": "normalize:iso"}
    return {"changed": False}


def find_abstract(struct: Dict[str, Any]) -> Optional[str]:
    secs = (struct or {}).get("sections") or []
    for s in secs[:6]:
        title = (s.get("title") or "").strip().lower().replace(":", "")
        if title in HEAD_MATCH:
            paras = s.get("paragraphs") or []
            txt = " ".join(p.get("text", "").strip() for p in paras if isinstance(p, dict) and p.get("text"))
            return re.sub(r"\s+", " ", txt).strip() or None
    return None


def find_author_title_line(struct: Dict[str, Any]) -> Optional[str]:
    secs = (struct or {}).get("sections") or []
    for s in secs[:10]:
        title = (s.get("title") or "").strip()
        if not title:
            continue
        # Heuristic: title contains commas/ands and several capitalized tokens
        if ("," in title or ";" in title or " and " in title.lower()) and sum(1 for t in title.split() if t[:1].isupper()) >= 2:
            return title
    return None


def tokenize_names(line: str) -> List[str]:
    parts = re.split(r",|;|\band\b|&", line)
    return [p.strip() for p in parts if p and p.strip()]
