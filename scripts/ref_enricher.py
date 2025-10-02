# scripts/ref_enricher.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
import httpx, requests, time, os
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

PMC_IDCONV_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"


def _normalize_doi(doi: str) -> Optional[str]:
    """Extract valid DOI from potentially malformed GROBID output."""
    if not doi:
        return None
    
    import re
    
    # Common DOI pattern: 10.xxxx/xxxxx
    doi_pattern = r'10\.\d{4,9}/[^\s]+'
    match = re.search(doi_pattern, doi)
    
    if match:
        normalized = match.group(0)
        # Remove trailing punctuation and common suffixes that might have been concatenated
        normalized = re.sub(r'[.,;:)\]]+$', '', normalized)
        # Remove common publication suffixes like "Epub2013May30"
        normalized = re.sub(r'Epub\d{4}[A-Za-z]{3}\d{1,2}$', '', normalized)
        return normalized
    
    return None

def _idconv_doi(doi: str) -> Optional[str]:
    if not doi:
        return None

    # Normalize DOI first to extract valid DOI from malformed GROBID output
    normalized_doi = _normalize_doi(doi)
    if not normalized_doi:
        return None

    params = {
        "format": "json",
        "ids": normalized_doi,
        "tool": "medparse",
        "email": NCBI_EMAIL,
    }

    # NCBI idconv service currently rejects httpx user agents with 403, so use
    # requests for the DOI lookup to follow the recommended endpoint.
    response = requests.get(
        PMC_IDCONV_URL,
        params=params,
        timeout=20.0,
        headers={
            "User-Agent": "medparse/1.0 (+%s)" % NCBI_EMAIL,
            "Accept": "application/json",
        },
    )
    response.raise_for_status()
    data = response.json()

    records = data.get("records", []) if isinstance(data, dict) else []
    if not records:
        return None

    primary = records[0] or {}
    pmid = primary.get("pmid") or primary.get("pmid_id")
    return pmid

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
