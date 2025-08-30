from __future__ import annotations
from typing import List, Dict, Any, Optional
from lxml import etree
from .ncbi_client import NCBIClient
from .cache_manager import CacheManager

def _parse_esearch(xml_text: str) -> List[str]:
    root = etree.fromstring(xml_text.encode("utf-8"))
    return [e.text for e in root.xpath("//IdList/Id") if e is not None and e.text]

def _parse_efetch(xml_text: str) -> List[Dict[str,Any]]:
    root = etree.fromstring(xml_text.encode("utf-8"))
    arts = root.xpath("//PubmedArticle")
    out = []
    for node in arts:
        def xp(path):
            r = node.xpath(path)
            return r[0].text if r and hasattr(r[0], "text") else (r[0] if r else None)
        pmid = xp(".//PMID")
        t_nodes = node.xpath(".//ArticleTitle")
        title = etree.tostring(t_nodes[0], method="text", encoding="unicode").strip() if t_nodes else None
        ab_pars = node.xpath(".//Abstract/AbstractText")
        abstract = " ".join(etree.tostring(p, method="text", encoding="unicode").strip() for p in ab_pars) if ab_pars else None
        journal = xp(".//Journal/Title")
        year = xp(".//JournalIssue/PubDate/Year") or xp(".//ArticleDate/Year")
        doi_node = node.xpath(".//ArticleIdList/ArticleId[@IdType='doi']")
        doi = doi_node[0].text if doi_node else None
        mesh_terms = [e.text for e in node.xpath(".//MeshHeading/DescriptorName") if e is not None and e.text]
        out.append({"pmid": pmid, "title": title, "abstract": abstract, "journal": journal, "year": year, "doi": doi, "mesh_terms": mesh_terms})
    return out

def _esearch_try(ncbi: NCBIClient, cache: Optional[CacheManager], key: str, term: str) -> List[str]:
    if cache:
        cached = cache.get(key)
        if cached is not None:
            return cached
    xml = ncbi.esearch_pubmed(term, retmax=3)
    ids = _parse_esearch(xml)
    if cache:
        cache.set(key, ids)
    return ids

def enrich_items_with_ncbi(items: List[Dict[str,Any]], ncbi: NCBIClient, cache: Optional[CacheManager] = None) -> List[Dict[str,Any]]:
    enriched = []
    for it in items:
        title = (it.get("title") or "").strip()
        year = (it.get("year") or "").strip()
        journal = (it.get("journal") or "").strip()
        doi = (it.get("doi") or "").strip()
        pmids: List[str] = []
        
        if doi:
            pmids = _esearch_try(ncbi, cache, f"esearch_doi::{doi}", f'"{doi}"[AID]')
        if not pmids and title:
            if year:
                pmids = _esearch_try(ncbi, cache, f"esearch_titl_year::{title}|{year}", f'"{title}"[Title] AND {year}[DP]')
            if not pmids and journal:
                pmids = _esearch_try(ncbi, cache, f"esearch_titl_jour::{title}|{journal}", f'"{title}"[Title] AND "{journal}"[Journal]')
            if not pmids:
                first12 = " ".join(title.split()[:12])
                pmids = _esearch_try(ncbi, cache, f"esearch_title_part::{first12}", f'{first12}[Title]')
        
        hits = []
        if pmids:
            efxml = ncbi.efetch_pubmed(",".join(pmids[:1]))
            hits = _parse_efetch(efxml)
        enriched.append({**it, "hits": hits})
    return enriched