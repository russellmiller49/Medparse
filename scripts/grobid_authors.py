# scripts/grobid_authors.py
from typing import List, Dict
from lxml import etree

NS = {"tei": "http://www.tei-c.org/ns/1.0"}

def _name(author_el) -> Dict[str, str]:
    given = " ".join([t for t in author_el.xpath(".//tei:forename/text()", namespaces=NS) if t]).strip()
    family = (author_el.xpath("string(.//tei:surname)", namespaces=NS) or "").strip()
    display = (given + " " + family).strip()
    ama = (family + " " + "".join([p[0] for p in given.split()]).upper()).strip() if (family or given) else ""
    return {"given": given, "family": family, "display": display, "ama": ama}

def parse_authors_from_tei(tei_xml: str) -> List[Dict[str, str]]:
    """Extract authors strictly from header biblStruct analytic/author (fallback: monogr/author)."""
    root = etree.fromstring(tei_xml.encode("utf-8"))
    nodes = root.xpath(
        "//tei:teiHeader/tei:fileDesc/tei:sourceDesc//tei:biblStruct/tei:analytic/tei:author",
        namespaces=NS
    )
    if not nodes:
        nodes = root.xpath(
            "//tei:teiHeader/tei:fileDesc/tei:sourceDesc//tei:biblStruct/tei:monogr/tei:author",
            namespaces=NS
        )
    authors = [_name(a) for a in nodes]
    # de-dup and trim to something reasonable
    seen, out = set(), []
    for a in authors:
        key = (a["family"].lower(), a["given"].lower())
        if key in seen: continue
        seen.add(key); out.append(a)
    return out