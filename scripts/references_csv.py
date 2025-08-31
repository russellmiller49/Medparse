from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Union
import csv
from lxml import etree
NS = {"tei":"http://www.tei-c.org/ns/1.0"}

def _txt(el) -> str: return etree.tostring(el, method="text", encoding="unicode").strip()
def _ama_author(pers) -> str:
    last = _txt(pers.xpath("tei:surname", namespaces=NS)[0]) if pers.xpath("tei:surname", namespaces=NS) else _txt(pers)
    rest = _txt(pers).replace(last,"").split()
    inits = "".join([t[0] for t in rest if t and t[0].isalpha()]).upper()
    return f"{last} {inits}"

def _format_authors(authors: List[str]) -> str:
    return ", ".join(authors) if len(authors)<=6 else ", ".join(authors[:3]) + " et al."

def _ama_row(b):
    title = b.xpath("string(.//tei:analytic/tei:title | .//tei:title)", namespaces=NS).strip()
    authors = [_ama_author(p) for p in b.xpath(".//tei:author/tei:persName", namespaces=NS)]
    jtitle = b.xpath("string(.//tei:monogr/tei:title)", namespaces=NS).strip()
    year = b.xpath("string(.//tei:monogr/tei:imprint/tei:date/@when | .//tei:monogr/tei:imprint/tei:date)", namespaces=NS).strip()
    vol = b.xpath("string(.//tei:biblScope[@unit='volume'])", namespaces=NS).strip()
    iss = b.xpath("string(.//tei:biblScope[@unit='issue'])", namespaces=NS).strip()
    pages = b.xpath("string(.//tei:biblScope[@unit='page'])", namespaces=NS).strip()
    doi = b.xpath("string(.//tei:idno[@type='DOI'])", namespaces=NS).strip()
    vol_issue = f"{vol}({iss})" if vol and iss else (vol or iss)
    pages_part = f":{pages}" if pages else ""
    doi_part = f". doi:{doi}" if doi else ""
    ama = f"{_format_authors(authors)}. {title}. {jtitle}. {year};{vol_issue}{pages_part}{doi_part}".strip().strip(".") + "."
    return {"ama": ama, "title": title, "journal": jtitle, "year": year, "volume": vol, "issue": iss, "pages": pages, "doi": doi, "authors": "; ".join(authors)}

def write_references_csv(refs_input: Union[str, List[Dict]], out_csv: Path) -> int:
    """Write references to CSV. Accepts either TEI XML string or list of structured refs."""
    rows = []
    
    if isinstance(refs_input, str):
        # Legacy TEI XML input
        root = etree.fromstring(refs_input.encode("utf-8"))
        bibls = root.xpath("//tei:listBibl/tei:biblStruct", namespaces=NS)
        rows = [_ama_row(b) for b in bibls]
    else:
        # New structured refs input
        for r in refs_input:
            authors_str = "; ".join(r.get("authors", [])) if isinstance(r.get("authors"), list) else r.get("authors", "")
            authors_list = r.get("authors", []) if isinstance(r.get("authors"), list) else []
            
            # Create AMA citation
            vol_issue = f"{r.get('volume', '')}({r.get('issue', '')})" if r.get('volume') and r.get('issue') else (r.get('volume', '') or r.get('issue', ''))
            pages_part = f":{r.get('pages', '')}" if r.get('pages') else ""
            doi_part = f". doi:{r.get('doi', '')}" if r.get('doi') else ""
            ama = f"{_format_authors(authors_list)}. {r.get('title', '')}. {r.get('journal', '')}. {r.get('year', '')};{vol_issue}{pages_part}{doi_part}".strip().strip(".") + "."
            
            rows.append({
                "ama": ama,
                "title": r.get("title"),
                "journal": r.get("journal"),
                "year": r.get("year"),
                "volume": r.get("volume"),
                "issue": r.get("issue"),
                "pages": r.get("pages"),
                "doi": r.get("doi"),
                "pmid": r.get("pmid"),
                "authors": authors_str
            })
    
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["#","ama","title","journal","year","volume","issue","pages","doi","pmid","authors"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for i, r in enumerate(rows, start=1):
            w.writerow({"#": i, **r})
    return len(rows)