#!/usr/bin/env python3
"""
Backfill missing abstracts from PubMed using E-utilities API.
"""
import os
import time
import json
import re
from pathlib import Path
from typing import Optional, Tuple
import requests
from xml.etree import ElementTree as ET

# NCBI E-utilities configuration
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "")
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def _rate_limit():
    """NCBI guidance: with api_key up to 10 req/sec; without, ~3 req/sec is safer"""
    time.sleep(0.12 if NCBI_API_KEY else 0.35)

def esearch_by_doi(doi: str) -> Optional[str]:
    """Search PubMed by DOI, return PMID if found."""
    if not doi:
        return None
    
    params = {
        "db": "pubmed",
        "term": f"{doi}[AID]",
        "retmode": "json"
    }
    if NCBI_EMAIL:
        params["email"] = NCBI_EMAIL
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    
    try:
        r = requests.get(f"{EUTILS}/esearch.fcgi", params=params, timeout=20)
        _rate_limit()
        r.raise_for_status()
        js = r.json()
        ids = js.get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else None
    except Exception as e:
        print(f"Error searching DOI {doi}: {e}")
        return None

def esearch_by_title(title: str, year: Optional[int]) -> Optional[str]:
    """Search PubMed by title and year, return PMID if found."""
    if not title:
        return None
    
    term = f"{title.strip()}[Title]"
    if year:
        term += f" AND {year}[DP]"
    
    params = {
        "db": "pubmed",
        "term": term,
        "retmode": "json"
    }
    if NCBI_EMAIL:
        params["email"] = NCBI_EMAIL
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    
    try:
        r = requests.get(f"{EUTILS}/esearch.fcgi", params=params, timeout=20)
        _rate_limit()
        r.raise_for_status()
        js = r.json()
        ids = js.get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else None
    except Exception as e:
        print(f"Error searching title '{title[:50]}...': {e}")
        return None

def efetch_abstract(pmid: str) -> Optional[str]:
    """Fetch abstract text from PubMed by PMID."""
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml"
    }
    if NCBI_EMAIL:
        params["email"] = NCBI_EMAIL
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    
    try:
        r = requests.get(f"{EUTILS}/efetch.fcgi", params=params, timeout=30)
        _rate_limit()
        r.raise_for_status()
        
        root = ET.fromstring(r.text)
        
        # Navigate PubMed XML to find abstract
        texts = []
        for abst in root.findall(".//Abstract"):
            pieces = []
            for t in abst.findall("AbstractText"):
                label = t.attrib.get("Label") or t.attrib.get("NlmCategory")
                txt = (t.text or "").strip()
                if not txt:
                    continue
                if label:
                    pieces.append(f"{label}: {txt}")
                else:
                    pieces.append(txt)
            if pieces:
                texts.append("\n".join(pieces))
        
        if texts:
            merged = "\n\n".join(texts).strip()
            # Strip excessive whitespace/JATS remnants
            merged = re.sub(r"\s+", " ", merged)
            return merged
        return None
    except Exception as e:
        print(f"Error fetching PMID {pmid}: {e}")
        return None

def backfill_file(path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Attempt to backfill missing abstract for a single file.
    Returns (success, status_message).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"read_error: {e}"
    
    meta = data.get("metadata", {}) or {}
    
    # Check if already has abstract
    if meta.get("abstract") and meta["abstract"].strip():
        return False, "already_has_abstract"
    
    doi = meta.get("doi", "") or ""
    title = meta.get("title", "") or ""
    year = meta.get("year", None)
    
    # Try searching by DOI first, then title
    pmid = None
    search_method = ""
    
    if doi:
        pmid = esearch_by_doi(doi)
        if pmid:
            search_method = "doi"
    
    if not pmid and title:
        pmid = esearch_by_title(title, year)
        if pmid:
            search_method = "title"
    
    if not pmid:
        return False, "pubmed_not_found"
    
    # Fetch abstract
    abstract = efetch_abstract(pmid)
    if not abstract:
        return False, f"pubmed_no_abstract (PMID: {pmid})"
    
    if dry_run:
        return True, f"would_fill_from_pubmed_{search_method}_pmid_{pmid}"
    
    # Update the file
    meta["abstract"] = abstract
    meta["abstract_source"] = "pubmed"
    meta["pubmed_id"] = pmid
    data["metadata"] = meta
    
    # Also update quality indicators if present
    if "quality" in data:
        data["quality"]["has_abstract"] = True
        data["quality"]["abstract_source"] = "pubmed"
    
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, f"filled_from_{search_method}_pmid_{pmid}"

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Backfill missing abstracts via PubMed")
    ap.add_argument("input_dir", help="Directory of cleaned/hardened JSONs to fix in-place")
    ap.add_argument("--limit", type=int, default=0, help="Process at most N files (0=all)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    ap.add_argument("--only-missing", action="store_true", help="Only process files without abstracts")
    args = ap.parse_args()
    
    if not NCBI_EMAIL:
        print("Warning: NCBI_EMAIL not set. Please set it for better API compliance:")
        print("  export NCBI_EMAIL='your.email@example.com'")
        print()
    
    in_dir = Path(args.input_dir)
    if not in_dir.exists():
        print(f"Error: Directory {in_dir} does not exist")
        return 1
    
    files = list(in_dir.glob("*.json"))
    # Skip chunk files
    files = [f for f in files if not f.name.endswith("_chunks.json")]
    
    if args.only_missing:
        # Pre-filter to only files missing abstracts
        missing_files = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                meta = data.get("metadata", {}) or {}
                if not (meta.get("abstract") and meta["abstract"].strip()):
                    missing_files.append(f)
            except:
                pass
        files = missing_files
        print(f"Found {len(files)} files missing abstracts")
    
    fixed = 0
    skipped = 0
    errors = 0
    
    for i, p in enumerate(files):
        if args.limit and i >= args.limit:
            break
        
        try:
            changed, status = backfill_file(p, dry_run=args.dry_run)
            if changed:
                fixed += 1
                print(f"[{'DRY' if args.dry_run else 'OK'}] {p.name}: {status}")
            else:
                skipped += 1
                if "already_has" not in status:  # Don't print files that already have abstracts
                    print(f"[SKIP] {p.name}: {status}")
        except Exception as e:
            errors += 1
            print(f"[ERR] {p.name}: {e}")
    
    print(f"\n{'DRY RUN ' if args.dry_run else ''}Summary:")
    print(f"  Fixed: {fixed}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Total processed: {min(len(files), args.limit or len(files))}")

if __name__ == "__main__":
    main()