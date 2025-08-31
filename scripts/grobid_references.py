# scripts/grobid_references.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from lxml import etree

NS = {"tei": "http://www.tei-c.org/ns/1.0"}

def _text(el) -> str:
    return etree.tostring(el, method="text", encoding="unicode").strip()

def _first(el, xp) -> Optional[str]:
    r = el.xpath(xp, namespaces=NS)
    if not r: return None
    v = r[0]
    return (v if isinstance(v, str) else (v.text if hasattr(v, "text") else _text(v))) or None

def _authors_ama(analytic_or_monogr) -> List[str]:
    names = []
    for a in analytic_or_monogr.xpath(".//tei:author", namespaces=NS):
        fam = _first(a, ".//tei:surname") or ""
        fns = [x.strip() for x in a.xpath(".//tei:forename/text()", namespaces=NS) if x and x.strip()]
        inits = "".join([n[0] for n in fns if n])
        disp = (fam + " " + inits).strip() if fam or inits else None
        if disp: names.append(disp)
    return names

def parse_references_tei(tei_xml: str) -> Dict[str, Any]:
    """Return both raw lines and structured refs extracted from TEI."""
    root = etree.fromstring(tei_xml.encode("utf-8"))
    bibl_structs = root.xpath("//tei:listBibl/tei:biblStruct", namespaces=NS)

    refs_struct: List[Dict[str, Any]] = []
    refs_raw: List[str] = []

    for b in bibl_structs:
        # Prefer analytic (article-level) metadata, then monogr
        analytic = b.find("tei:analytic", namespaces=NS)
        monogr   = b.find("tei:monogr", namespaces=NS)

        # Title
        title = None
        if analytic is not None:
            title = _first(analytic, ".//tei:title")
        if not title:
            title = _first(monogr, ".//tei:title")

        # Journal (monograph title)
        journal = _first(monogr, ".//tei:title[@level='j']") or _first(monogr, ".//tei:title")

        # Year / Imprint
        year = _first(monogr, ".//tei:imprint/tei:date/@when")
        if year and len(year) >= 4: year = year[:4]
        if not year:
            year = _first(monogr, ".//tei:imprint/tei:date")

        volume = _first(monogr, ".//tei:imprint/tei:biblScope[@unit='volume']")
        issue  = _first(monogr, ".//tei:imprint/tei:biblScope[@unit='issue']")
        pages  = _first(monogr, ".//tei:imprint/tei:biblScope[@unit='page']")

        # IDs
        doi  = _first(b, ".//tei:idno[@type='DOI']")
        pmid = _first(b, ".//tei:idno[@type='PMID']")

        # Authors (AMA-style strings)
        auth_src = analytic if analytic is not None else monogr
        authors = _authors_ama(auth_src) if auth_src is not None else []

        # First author last name for PubMed fallback
        first_author_last = None
        if authors:
            first_author_last = authors[0].split(" ")[0]

        refs_struct.append({
            "title": title or None,
            "journal": journal or None,
            "year": year or None,
            "volume": volume or None,
            "issue": issue or None,
            "pages": pages or None,
            "doi": doi or None,
            "pmid": pmid or None,
            "authors": authors,
            "first_author_last": first_author_last
        })

        refs_raw.append(_text(b))

    return {"references_struct": refs_struct, "references_raw": refs_raw}