# scripts/ref_enricher.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
import httpx, time, os
from tenacity import retry, stop_after_attempt, wait_exponential

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
NCBI_API_KEY = os.getenv("NCBI_API_KEY")
NCBI_EMAIL   = os.getenv("NCBI_EMAIL", "unknown@example.com")

def _params(extra: Dict[str, Any]) -> Dict[str, Any]:
    p = {"retmode": "json"}
    if NCBI_API_KEY: p["api_key"] = NCBI_API_KEY
    if NCBI_EMAIL:   p["email"] = NCBI_EMAIL
    p.update(extra); return p

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6), reraise=True)
def _get_json(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    with httpx.Client(timeout=25.0) as cli:
        r = cli.get(NCBI_BASE + path, params=params)
        r.raise_for_status()
        return r.json()

def _idconv_doi(doi: str) -> Optional[str]:
    if not doi: return None
    with httpx.Client(timeout=20.0) as cli:
        r = cli.get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
                    params={"format":"json","ids":doi,"tool":"medparse","email":NCBI_EMAIL})
        r.raise_for_status()
        data = r.json()
    recs = data.get("records", [])
    return recs[0].get("pmid") if recs else None

def _esearch_title(title: str, first_author: Optional[str], year: Optional[str]) -> Optional[str]:
    if not title: return None
    term = f'{title}[Title]'
    if first_author: term += f' AND {first_author}[Author]'
    if year: term += f' AND {year}[PDAT]'
    data = _get_json("esearch.fcgi", _params({"db":"pubmed","term":term}))
    ids = (data.get("esearchresult", {}) or {}).get("idlist", [])
    return ids[0] if ids else None

def _esummary(pmid: str) -> Dict[str, Any]:
    data = _get_json("esummary.fcgi", _params({"db":"pubmed","id":pmid}))
    return data.get("result", {}).get(pmid, {})

def _efetch_abstract(pmid: str) -> Optional[str]:
    with httpx.Client(timeout=25.0) as cli:
        r = cli.get(NCBI_BASE + "efetch.fcgi", params=_params({"db":"pubmed","id":pmid,"retmode":"xml"}))
        r.raise_for_status()
        xml = r.text
    # Extremely light scrape for a single abstract blob
    import re
    m = re.search(r"<AbstractText[^>]*>(.*?)</AbstractText>", xml, flags=re.S)
    if not m: return None
    return " ".join(m.group(1).split())

def enrich_refs_from_struct(refs_struct: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in refs_struct:
        pmid = r.get("pmid")
        doi  = r.get("doi")
        if not pmid and doi:
            pmid = _idconv_doi(doi)

        if not pmid:
            pmid = _esearch_title(r.get("title",""), r.get("first_author_last"), r.get("year"))

        enriched = {"pmid": pmid, "doi": doi}
        if pmid:
            es = _esummary(pmid)
            enriched.update({
                "title":   es.get("title") or r.get("title"),
                "journal": es.get("fulljournalname") or es.get("source") or r.get("journal"),
                "year":    (es.get("pubdate") or "")[:4] or r.get("year"),
                "authors": [a.get("name") for a in es.get("authors", []) if a.get("name")],
                "mesh":    es.get("meshheadinglist", []),
                "pubtypes": es.get("pubtype", []),
            })
            abs_txt = _efetch_abstract(pmid)
            if abs_txt: enriched["abstract"] = abs_txt
        out.append({**r, "enrichment": enriched})
        time.sleep(0.1)  # be gentle; you also have tenacity retries
    return out