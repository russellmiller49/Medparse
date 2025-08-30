from __future__ import annotations
from typing import List, Dict, Any
from lxml import etree
NS = {"tei":"http://www.tei-c.org/ns/1.0"}

def extract_ref_items(tei_xml: str) -> List[Dict[str, Any]]:
    root = etree.fromstring(tei_xml.encode("utf-8"))
    items = []
    for b in root.xpath("//tei:listBibl/tei:biblStruct", namespaces=NS):
        title = b.xpath("string(.//tei:analytic/tei:title | .//tei:title)", namespaces=NS).strip()
        year = b.xpath("string(.//tei:monogr/tei:imprint/tei:date/@when | .//tei:monogr/tei:imprint/tei:date)", namespaces=NS).strip()
        journal = b.xpath("string(.//tei:monogr/tei:title)", namespaces=NS).strip()
        doi = b.xpath("string(.//tei:idno[@type='DOI'])", namespaces=NS).strip()
        first_author = b.xpath("string(.//tei:author[1]//tei:surname)", namespaces=NS).strip()
        items.append({
            "title": title or None,
            "year": year or None,
            "journal": journal or None,
            "doi": doi or None,
            "first_author": first_author or None
        })
    return items