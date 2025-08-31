# scripts/grobid_tei.py
import re
from typing import Dict, List, Optional, Any
from lxml import etree

NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def fix_runon_names(name: str) -> str:
    """Fix run-on names like 'SameerKAvasarala' -> 'Sameer K Avasarala'."""
    if not name or " " in name:
        return name
    
    # Insert spaces before uppercase letters that follow lowercase
    name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
    # Insert spaces between consecutive uppercase letters when followed by lowercase
    name = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', name)
    # Clean up multiple spaces
    return " ".join(name.split())


def parse_article_authors(tei_xml: str) -> List[Dict]:
    """
    Extract authors strictly from teiHeader > fileDesc > sourceDesc > biblStruct > analytic > author.
    Never from back-matter references.
    
    Returns [{"family": ..., "given": ..., "display": ..., "ama": ..., "affiliations": [...]}]
    """
    try:
        root = etree.fromstring(tei_xml.encode("utf-8"))
    except Exception as e:
        print(f"Failed to parse TEI XML: {e}")
        return []
    
    authors = []
    
    # Primary path: analytic authors (for journal articles)
    xpath_auth = ".//tei:teiHeader//tei:fileDesc//tei:sourceDesc//tei:biblStruct/tei:analytic/tei:author"
    
    for author_elem in root.xpath(xpath_auth, namespaces=NS):
        pers_nodes = author_elem.xpath(".//tei:persName", namespaces=NS)
        if not pers_nodes:
            continue
        
        pers = pers_nodes[0]
        
        # Extract name components
        given_names = []
        for forename in pers.xpath("./tei:forename", namespaces=NS):
            text = (forename.text or "").strip()
            if text:
                # Fix run-on names
                text = fix_runon_names(text)
                given_names.append(text)
        
        family = ""
        for surname in pers.xpath("./tei:surname", namespaces=NS):
            text = (surname.text or "").strip()
            if text:
                family = fix_runon_names(text)
                break
        
        if not family:  # Skip if no family name
            continue
        
        given = " ".join(given_names)
        display = f"{given} {family}".strip()
        
        # AMA format: "LastName AB" (initials only)
        ama_initials = "".join([g[0] for g in given_names if g])
        ama = f"{family} {ama_initials}".strip()
        
        # Extract affiliations
        affiliations = []
        for aff in author_elem.xpath(".//tei:affiliation", namespaces=NS):
            # Get text content, handling nested elements
            aff_text = etree.tostring(aff, method="text", encoding="unicode").strip()
            if aff_text:
                # Clean up whitespace
                aff_text = " ".join(aff_text.split())
                affiliations.append(aff_text)
        
        authors.append({
            "family": family,
            "given": given,
            "display": display,
            "ama": ama,
            "affiliations": affiliations
        })
    
    # Fallback: monograph authors if no analytic authors found
    if not authors:
        xpath_mono = ".//tei:teiHeader//tei:fileDesc//tei:sourceDesc//tei:biblStruct/tei:monogr/tei:author"
        for author_elem in root.xpath(xpath_mono, namespaces=NS):
            pers_nodes = author_elem.xpath(".//tei:persName", namespaces=NS)
            if not pers_nodes:
                continue
            
            pers = pers_nodes[0]
            given_names = []
            for forename in pers.xpath("./tei:forename", namespaces=NS):
                text = (forename.text or "").strip()
                if text:
                    text = fix_runon_names(text)
                    given_names.append(text)
            
            family = ""
            for surname in pers.xpath("./tei:surname", namespaces=NS):
                text = (surname.text or "").strip()
                if text:
                    family = fix_runon_names(text)
                    break
            
            if not family:
                continue
            
            given = " ".join(given_names)
            display = f"{given} {family}".strip()
            ama_initials = "".join([g[0] for g in given_names if g])
            ama = f"{family} {ama_initials}".strip()
            
            authors.append({
                "family": family,
                "given": given,
                "display": display,
                "ama": ama,
                "affiliations": []
            })
    
    return authors


def parse_article_metadata(tei_xml: str) -> Dict[str, Any]:
    """
    Extract comprehensive metadata from GROBID TEI.
    
    Returns:
        {
            "title": str,
            "authors": List[Dict],
            "year": str,
            "journal": str,
            "volume": str,
            "issue": str,
            "pages": str,
            "doi": str,
            "abstract": str
        }
    """
    try:
        root = etree.fromstring(tei_xml.encode("utf-8"))
    except Exception as e:
        print(f"Failed to parse TEI XML: {e}")
        return {}
    
    # Title
    title = root.xpath("string(//tei:teiHeader//tei:titleStmt/tei:title)", namespaces=NS) or ""
    title = " ".join(title.split())  # Clean whitespace
    
    # Authors
    authors = parse_article_authors(tei_xml)
    
    # Publication details from monogr
    journal = root.xpath("string(//tei:monogr/tei:title[@level='j'])", namespaces=NS) or ""
    volume = root.xpath("string(//tei:monogr/tei:imprint/tei:biblScope[@unit='volume'])", namespaces=NS) or ""
    issue = root.xpath("string(//tei:monogr/tei:imprint/tei:biblScope[@unit='issue'])", namespaces=NS) or ""
    
    # Pages - try different formats
    pages = root.xpath("string(//tei:monogr/tei:imprint/tei:biblScope[@unit='page'])", namespaces=NS) or ""
    if not pages:
        page_from = root.xpath("string(//tei:monogr/tei:imprint/tei:biblScope[@unit='page']/@from)", namespaces=NS)
        page_to = root.xpath("string(//tei:monogr/tei:imprint/tei:biblScope[@unit='page']/@to)", namespaces=NS)
        if page_from and page_to:
            pages = f"{page_from}-{page_to}"
    
    # Year
    year = root.xpath("string(//tei:monogr/tei:imprint/tei:date/@when)", namespaces=NS) or ""
    if year and len(year) >= 4:
        year = year[:4]
    
    # DOI
    doi = root.xpath("string(//tei:idno[@type='DOI'])", namespaces=NS) or ""
    
    # Abstract
    abstract = root.xpath("string(//tei:abstract)", namespaces=NS) or ""
    abstract = " ".join(abstract.split())
    
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "doi": doi,
        "abstract": abstract
    }