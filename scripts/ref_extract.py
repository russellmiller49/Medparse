# scripts/ref_extract.py
"""Extract references from GROBID TEI XML."""

from typing import List, Dict
from lxml import etree

NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def extract_refs_from_tei(tei_xml: str) -> List[Dict]:
    """
    Extract structured references from GROBID TEI XML.
    
    Args:
        tei_xml: GROBID TEI XML content
        
    Returns:
        List of reference dicts with title, authors, year, journal, doi, pmid, etc.
    """
    try:
        root = etree.fromstring(tei_xml.encode("utf-8"))
    except Exception as e:
        print(f"Failed to parse TEI XML for references: {e}")
        return []
    
    refs = []
    
    # Find all biblStruct elements in the back matter
    for bibl in root.xpath(".//tei:back//tei:listBibl/tei:biblStruct", namespaces=NS):
        ref = {}
        
        # Extract title (from analytic or monogr)
        title = " ".join(bibl.xpath(".//tei:analytic/tei:title/text()", namespaces=NS))
        if not title:
            title = " ".join(bibl.xpath(".//tei:monogr/tei:title[@level='m']/text()", namespaces=NS))
        ref["title"] = title.strip() if title else None
        
        # Extract authors
        authors = []
        for author in bibl.xpath(".//tei:analytic/tei:author", namespaces=NS):
            given = " ".join(author.xpath(".//tei:forename/text()", namespaces=NS))
            family = " ".join(author.xpath(".//tei:surname/text()", namespaces=NS))
            if family:
                if given:
                    authors.append(f"{family} {given[0]}")  # AMA style: LastName Initial
                else:
                    authors.append(family)
        ref["authors"] = ", ".join(authors) if authors else None
        
        # Extract journal
        journal = " ".join(bibl.xpath(".//tei:monogr/tei:title[@level='j']/text()", namespaces=NS))
        ref["journal"] = journal.strip() if journal else None
        
        # Extract year
        year = bibl.xpath("string(.//tei:monogr/tei:imprint/tei:date/@when)", namespaces=NS)
        if year and len(year) >= 4:
            ref["year"] = year[:4]
        else:
            # Try to extract from text
            year_text = bibl.xpath("string(.//tei:monogr/tei:imprint/tei:date)", namespaces=NS)
            if year_text:
                import re
                year_match = re.search(r'(19|20)\d{2}', year_text)
                if year_match:
                    ref["year"] = year_match.group(0)
                else:
                    ref["year"] = None
            else:
                ref["year"] = None
        
        # Extract volume
        volume = bibl.xpath("string(.//tei:monogr/tei:imprint/tei:biblScope[@unit='volume'])", namespaces=NS)
        ref["volume"] = volume if volume else None
        
        # Extract issue
        issue = bibl.xpath("string(.//tei:monogr/tei:imprint/tei:biblScope[@unit='issue'])", namespaces=NS)
        ref["issue"] = issue if issue else None
        
        # Extract pages
        pages = bibl.xpath("string(.//tei:monogr/tei:imprint/tei:biblScope[@unit='page'])", namespaces=NS)
        if not pages:
            # Try from/to attributes
            page_from = bibl.xpath("string(.//tei:monogr/tei:imprint/tei:biblScope[@unit='page']/@from)", namespaces=NS)
            page_to = bibl.xpath("string(.//tei:monogr/tei:imprint/tei:biblScope[@unit='page']/@to)", namespaces=NS)
            if page_from and page_to:
                pages = f"{page_from}-{page_to}"
            elif page_from:
                pages = page_from
        ref["pages"] = pages if pages else None
        
        # Extract DOI
        doi = bibl.xpath("string(.//tei:idno[@type='DOI'])", namespaces=NS) or \
              bibl.xpath("string(.//tei:idno[@type='doi'])", namespaces=NS)
        ref["doi"] = doi.strip() if doi else None
        
        # Extract PMID
        pmid = bibl.xpath("string(.//tei:idno[@type='PMID'])", namespaces=NS) or \
               bibl.xpath("string(.//tei:idno[@type='pmid'])", namespaces=NS)
        ref["pmid"] = pmid.strip() if pmid else None
        
        # Extract URL
        url = bibl.xpath("string(.//tei:ptr[@type='web']/@target)", namespaces=NS)
        ref["url"] = url if url else None
        
        # Only add if we have at least a title or authors
        if ref.get("title") or ref.get("authors"):
            refs.append(ref)
    
    return refs


def format_reference_ama(ref: Dict) -> str:
    """
    Format a reference in AMA style.
    
    Args:
        ref: Reference dict from extract_refs_from_tei()
        
    Returns:
        AMA-formatted reference string
    """
    parts = []
    
    # Authors
    if ref.get("authors"):
        parts.append(ref["authors"])
    
    # Title
    if ref.get("title"):
        parts.append(ref["title"])
    
    # Journal
    if ref.get("journal"):
        journal_parts = [ref["journal"]]
        
        # Year
        if ref.get("year"):
            journal_parts.append(ref["year"])
        
        # Volume(issue):pages
        vol_issue_pages = []
        if ref.get("volume"):
            vol_issue_pages.append(ref["volume"])
        if ref.get("issue"):
            vol_issue_pages.append(f"({ref['issue']})")
        if ref.get("pages"):
            vol_issue_pages.append(f":{ref['pages']}")
        
        if vol_issue_pages:
            journal_parts.append("".join(vol_issue_pages))
        
        parts.append(". ".join(journal_parts))
    
    # DOI
    if ref.get("doi"):
        parts.append(f"doi:{ref['doi']}")
    
    return ". ".join(parts) + "."