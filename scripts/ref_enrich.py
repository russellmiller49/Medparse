# scripts/ref_enrich.py
"""Enrich references with PubMed metadata."""

import os
import httpx
import time
from typing import Dict, List, Optional
import json

NCBI_API_KEY = os.getenv("NCBI_API_KEY")
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "unknown@example.com")
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Rate limiting
LAST_REQUEST_TIME = 0
MIN_REQUEST_INTERVAL = 0.35  # ~3 requests per second with API key


def _rate_limit():
    """Enforce NCBI rate limits."""
    global LAST_REQUEST_TIME
    current_time = time.time()
    elapsed = current_time - LAST_REQUEST_TIME
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    LAST_REQUEST_TIME = time.time()


def fetch_pubmed_by_id(pmid: str) -> Optional[Dict]:
    """
    Fetch PubMed metadata by PMID.
    
    Args:
        pmid: PubMed ID
        
    Returns:
        PubMed metadata dict or None
    """
    if not pmid:
        return None
    
    _rate_limit()
    
    params = {
        "db": "pubmed",
        "retmode": "json",
        "id": pmid,
        "email": NCBI_EMAIL
    }
    
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(f"{NCBI_BASE}/esummary.fcgi", params=params)
            r.raise_for_status()
            data = r.json()
            
            # Extract the actual record
            result = data.get("result", {})
            if pmid in result:
                return result[pmid]
            
            # Try with string key
            if str(pmid) in result:
                return result[str(pmid)]
                
    except Exception as e:
        print(f"Error fetching PubMed data for PMID {pmid}: {e}")
    
    return None


def search_pubmed_by_doi(doi: str) -> Optional[str]:
    """
    Search PubMed by DOI to get PMID.
    
    Args:
        doi: Digital Object Identifier
        
    Returns:
        PMID if found, None otherwise
    """
    if not doi:
        return None
    
    _rate_limit()
    
    # Clean DOI (remove common prefixes)
    if doi.startswith("http://dx.doi.org/"):
        doi = doi[18:]
    elif doi.startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi.startswith("doi:"):
        doi = doi[4:]
    
    params = {
        "db": "pubmed",
        "term": f"{doi}[AID]",
        "retmode": "json",
        "email": NCBI_EMAIL
    }
    
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{NCBI_BASE}/esearch.fcgi", params=params)
            r.raise_for_status()
            data = r.json()
            
            result = data.get("esearchresult", {})
            ids = result.get("idlist", [])
            if ids:
                return ids[0]
                
    except Exception as e:
        print(f"Error searching PubMed for DOI {doi}: {e}")
    
    return None


def search_pubmed_by_title(title: str, year: Optional[str] = None) -> Optional[str]:
    """
    Search PubMed by title (and optionally year) to get PMID.
    
    Args:
        title: Article title
        year: Publication year
        
    Returns:
        PMID if found, None otherwise
    """
    if not title:
        return None
    
    _rate_limit()
    
    # Build search query
    query = f'"{title}"[Title]'
    if year:
        query += f" AND {year}[PDAT]"
    
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": 1,
        "email": NCBI_EMAIL
    }
    
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{NCBI_BASE}/esearch.fcgi", params=params)
            r.raise_for_status()
            data = r.json()
            
            result = data.get("esearchresult", {})
            ids = result.get("idlist", [])
            if ids:
                return ids[0]
                
    except Exception as e:
        print(f"Error searching PubMed for title '{title[:50]}...': {e}")
    
    return None


def enrich_references(refs: List[Dict], use_cache: bool = True) -> List[Dict]:
    """
    Enrich references with PubMed metadata.
    
    This function:
    1. Tries to find PMID if not present (via DOI or title search)
    2. Fetches PubMed metadata for each PMID
    3. Adds enriched data to each reference
    
    Args:
        refs: List of references from extract_refs_from_tei()
        use_cache: Whether to use cache for PubMed lookups
        
    Returns:
        List of enriched references (always returns same length as input)
    """
    enriched = []
    
    # Try to use cache if available
    cache = None
    if use_cache:
        try:
            from scripts.cache_manager import CacheManager
            cache = CacheManager()
        except:
            pass
    
    for i, ref in enumerate(refs):
        # Copy original reference
        enriched_ref = dict(ref)
        
        # Try to get PMID if not present
        pmid = ref.get("pmid")
        
        if not pmid and ref.get("doi"):
            # Try DOI search
            pmid = search_pubmed_by_doi(ref["doi"])
            if pmid:
                enriched_ref["pmid"] = pmid
                enriched_ref["pmid_source"] = "doi_search"
        
        if not pmid and ref.get("title"):
            # Try title search as last resort
            pmid = search_pubmed_by_title(ref["title"], ref.get("year"))
            if pmid:
                enriched_ref["pmid"] = pmid
                enriched_ref["pmid_source"] = "title_search"
        
        # Fetch PubMed data if we have PMID
        pubmed_data = None
        if pmid:
            # Check cache first
            if cache:
                cache_key = f"pmid_{pmid}"
                pubmed_data = cache.get(cache_key)
            
            # Fetch if not cached
            if not pubmed_data:
                pubmed_data = fetch_pubmed_by_id(pmid)
                
                # Cache the result
                if cache and pubmed_data:
                    cache.set(f"pmid_{pmid}", pubmed_data)
        
        # Add PubMed data to reference
        if pubmed_data:
            enriched_ref["pubmed"] = pubmed_data
            
            # Extract useful fields
            enriched_ref["pubmed_title"] = pubmed_data.get("title")
            enriched_ref["pubmed_journal"] = pubmed_data.get("fulljournalname")
            enriched_ref["pubmed_year"] = pubmed_data.get("pubdate", "").split()[0] if pubmed_data.get("pubdate") else None
            
            # Extract author list
            authors = pubmed_data.get("authors", [])
            if authors:
                enriched_ref["pubmed_authors"] = [
                    author.get("name", "") for author in authors
                ]
        else:
            enriched_ref["pubmed"] = None
        
        enriched.append(enriched_ref)
        
        # Progress indicator for large reference lists
        if (i + 1) % 10 == 0:
            print(f"Enriched {i + 1}/{len(refs)} references...")
    
    return enriched


def write_references_csv(refs: List[Dict], csv_path: str):
    """
    Write references to CSV in AMA format.
    
    Args:
        refs: List of references (enriched or not)
        csv_path: Path to output CSV file
    """
    import csv
    
    headers = [
        "authors", "title", "journal", "year", "volume", 
        "issue", "pages", "doi", "pmid", "pmid_source"
    ]
    
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        
        for ref in refs:
            # Use PubMed data if available, otherwise original
            row = {
                "authors": ref.get("pubmed_authors", ref.get("authors")),
                "title": ref.get("pubmed_title", ref.get("title")),
                "journal": ref.get("pubmed_journal", ref.get("journal")),
                "year": ref.get("pubmed_year", ref.get("year")),
                "volume": ref.get("volume"),
                "issue": ref.get("issue"),
                "pages": ref.get("pages"),
                "doi": ref.get("doi"),
                "pmid": ref.get("pmid"),
                "pmid_source": ref.get("pmid_source", "")
            }
            
            # Format authors list if it's a list
            if isinstance(row["authors"], list):
                row["authors"] = ", ".join(row["authors"])
            
            writer.writerow(row)