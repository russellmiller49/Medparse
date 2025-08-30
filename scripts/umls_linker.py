from __future__ import annotations
import time, re, httpx
from typing import Dict, List, Optional
from rapidfuzz import fuzz
from .cache_manager import CacheManager

UMLS_AUTH = "https://utslogin.nlm.nih.gov/cas/v1/api-key"
UMLS_SEARCH = "https://uts-ws.nlm.nih.gov/rest/search/current"
SERVICE = "http://umlsks.nlm.nih.gov"

class UMLSClient:
    def __init__(self, api_key: str, sabs: str = "SNOMEDCT_US,MSH,RXNORM", timeout=20, cache: CacheManager | None = None):
        self.api_key = api_key
        self.sabs = sabs
        self.timeout = timeout
        self._session = httpx.Client(timeout=timeout)
        self._tgt = None; self._tgt_time = 0
        self.cache = cache

    def _get_tgt(self) -> str:
        if self._tgt and time.time() - self._tgt_time < 7*60:
            return self._tgt
        resp = self._session.post(UMLS_AUTH, data={"apikey": self.api_key})
        resp.raise_for_status()
        loc = resp.headers.get("location") or resp.headers.get("Location")
        if not loc:
            m = re.search(r'action="([^"]+/tickets)"', resp.text)
            if not m: raise RuntimeError("Failed to obtain UMLS TGT")
            loc = m.group(1)
        self._tgt = loc; self._tgt_time = time.time()
        return self._tgt

    def _get_st(self) -> str:
        tgt = self._get_tgt()
        resp = self._session.post(tgt, data={"service": SERVICE})
        resp.raise_for_status()
        return resp.text.strip()

    def search(self, term: str, pageSize: int = 10) -> List[Dict]:
        st = self._get_st()
        params = {"string": term, "ticket": st, "sabs": self.sabs, "pageSize": str(pageSize)}
        r = self._session.get(UMLS_SEARCH, params=params)
        r.raise_for_status()
        return r.json().get("result", {}).get("results", [])

    def best_concept(self, term: str) -> Optional[Dict]:
        if self.cache:
            c = self.cache.get_umls_lookup(term)
            if c is not None: return c
        results = self.search(term, pageSize=10)
        ranked = sorted(results, key=lambda x: (
            0 if x.get("rootSource") in {"SNOMEDCT_US","RXNORM"} else 1,
            -fuzz.ratio(term.lower(), x.get("name","").lower())
        ))
        best = ranked[0] if ranked else None
        if self.cache and best is not None:
            self.cache.cache_umls_lookup(term, best)
        return best


def normalize_terms(text: str, abbrev_map: Dict[str, str]) -> str:
    def repl(m):
        k = m.group(0)
        return f"{abbrev_map[k.upper()]} ({k})"
    if not abbrev_map:
        return text
    pattern = r"\b(" + "|".join(map(re.escape, sorted(abbrev_map.keys(), key=len, reverse=True))) + r")\b"
    return re.sub(pattern, repl, text, flags=re.IGNORECASE)

def link_umls_phrases(phrases: list[str], client: UMLSClient) -> list[Dict]:
    linked = []
    for p in phrases:
        c = client.best_concept(p)
        if c:
            linked.append({"phrase": p, "cui": c.get("ui"), "preferred": c.get("name"), "source": c.get("rootSource")})
    return linked