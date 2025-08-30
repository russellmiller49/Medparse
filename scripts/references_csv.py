from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
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

def write_references_csv(tei_xml: str, out_csv: Path) -> int:
    root = etree.fromstring(tei_xml.encode("utf-8"))
    bibls = root.xpath("//tei:listBibl/tei:biblStruct", namespaces=NS)
    rows = [_ama_row(b) for b in bibls]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["#","ama","title","journal","year","volume","issue","pages","doi","authors"])
        w.writeheader()
        for i, r in enumerate(rows, start=1):
            w.writerow({"#": i, **r})
    return len(rows)