from __future__ import annotations
import re
from typing import Dict, Any, List
from lxml import etree
from .umls_linker import UMLSClient, normalize_terms, link_umls_phrases
from .table_normalizer import normalize_table

def parse_grobid_metadata(tei_xml: str) -> Dict[str, Any]:
    import re
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    
    root = etree.fromstring(tei_xml.encode("utf-8"))
    
    def fix_runon(s: str) -> str:
        s = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', s)
        s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', s)
        return " ".join(s.split())
    
    def author_display(pers) -> Dict[str, str]:
        surname = pers.xpath("string(tei:surname)", namespaces=ns).strip()
        given_list = [t.strip() for t in pers.xpath("tei:forename/text()", namespaces=ns) if t and t.strip()]
        given_list = [fix_runon(g) for g in given_list]
        given = " ".join(given_list).strip()
        ama_inits = "".join([g[0] for g in given_list if g])
        return {"family": surname, "given": given, "display": f"{given} {surname}".strip(), "ama": f"{surname} {ama_inits}".strip()}
    
    title = root.xpath("string(//tei:teiHeader//tei:titleStmt/tei:title)", namespaces=ns) or None
    year = root.xpath("string(//tei:teiHeader//tei:sourceDesc//tei:biblStruct//tei:imprint/tei:date/@when)", namespaces=ns) \
        or root.xpath("string(//tei:teiHeader//tei:profileDesc//tei:creation/tei:date/@when)", namespaces=ns) or None
    
    pers_nodes = root.xpath("//tei:teiHeader//tei:sourceDesc//tei:biblStruct/tei:analytic/tei:author/tei:persName", namespaces=ns)
    authors = [author_display(p) for p in pers_nodes]
    
    refs_text = [etree.tostring(n, method="text", encoding="unicode").strip()
                 for n in root.xpath("//tei:text//tei:listBibl/tei:biblStruct", namespaces=ns)]
    
    return {"title": title, "year": year, "authors": authors, "references_text": refs_text}


def _collect_candidate_terms(doc: Dict[str,Any], abbrev_map: Dict[str,str]) -> List[str]:
    STOP = {
        "text","figure","fig","table","supplementary","introduction","methods","results","discussion",
        "conclusion","acknowledgments","department","university","study","analysis","data","sample",
        "group","rate","percent","male","female","day","week","month","year","baseline","outcome",
        "appendix","online","copyright"
    }
    candidates = []
    for sec in doc.get("structure", {}).get("sections", []):
        t = (sec.get("title") or "").strip()
        if t: candidates.append(t)
    for t in doc.get("structure", {}).get("tables", []):
        for k in ("title","caption"):
            v = (t.get(k) or "").strip()
            if v: candidates.append(v)
        normalize_table(t)
    for f in doc.get("structure", {}).get("figures", []):
        v = (f.get("caption") or "").strip()
        if v: candidates.append(v)
    body = []
    for sec in doc.get("structure", {}).get("sections", []):
        for p in sec.get("paragraphs", []):
            s = p.get("text") or ""
            if s: body.append(s)
    body_text = " ".join(body)
    # Very restrictive pattern: focus on medical terms and multi-word phrases
    for m in re.finditer(r"\b([A-Z][a-zA-Z-]{4,}(?:\s+[A-Z][a-zA-Z-]{3,}){1,3})\b", body_text):
        term = m.group(1)
        # Only include multi-word terms that are likely to be medical concepts
        if len(term.split()) >= 2 and len(term) >= 8:
            candidates.append(term)
    candidates.extend(abbrev_map.keys())
    
    cleaned = []
    for c in candidates:
        c0 = re.sub(r"[\[\]\(\){}:;,.]", " ", c).strip()
        c0 = re.sub(r"\s+", " ", c0)
        if not c0 or len(c0) < 3: 
            continue
        if c0.lower() in STOP or c0.lower().isnumeric():
            continue
        cleaned.append(c0)
    seen=set(); out=[]
    for c in cleaned:
        k=c.lower()
        if k in seen: continue
        seen.add(k); out.append(c)
    return out[:200]


def enrich_with_umls(doc: Dict[str,Any], umls: UMLSClient, abbrev_map: Dict[str,str]) -> Dict[str,Any]:
    for sec in doc.get("structure", {}).get("sections", []):
        for p in sec.get("paragraphs", []):
            p["text"] = normalize_terms(p.get("text",""), abbrev_map)
    for fig in doc.get("structure", {}).get("figures", []):
        if "caption" in fig:
            fig["caption"] = normalize_terms(fig["caption"], abbrev_map)
    
    phrases = _collect_candidate_terms(doc, abbrev_map)
    linked = link_umls_phrases(phrases, umls)
    NOISE = {"Text value","Text","Value"}
    linked = [x for x in linked if (x.get("preferred") or "").strip() not in NOISE]
    
    doc.setdefault("umls_links", []).extend(linked)
    return doc


def concat_text(doc: Dict[str,Any], limit_chars: int = 300000) -> str:
    parts = []
    struct = doc.get("structure", {})
    for sec in struct.get("sections", []):
        if sec.get("title"): parts.append(sec["title"])
        for p in sec.get("paragraphs", []):
            t = p.get("text","")
            if t: parts.append(t)
    return "\n".join(parts)[:limit_chars]

def extract_trial_ids(text: str) -> List[str]:
    nct = r'\bNCT\d{8}\b'
    isrctn = r'\bISRCTN\d{8}\b'
    eudract = r'\b\d{4}-\d{6}-\d{2}\b'
    ids = []
    ids.extend(re.findall(nct, text))
    ids.extend(re.findall(isrctn, text))
    ids.extend(re.findall(eudract, text))
    return sorted(set(ids))

def resolve_cross_references(doc: Dict[str, Any]) -> None:
    struct = doc.get("structure", {})
    ref_pattern = r'\b(Figure|Fig.|Table|Supplementary Figure|Supp. Fig.)\s+(\d+[A-Za-z]?)\b'
    for section in struct.get("sections", []):
        for para in section.get("paragraphs", []):
            txt = para.get("text","")
            xs = []
            for m in re.finditer(ref_pattern, txt, flags=re.IGNORECASE):
                kind = m.group(1).lower()
                num = m.group(2)
                base = re.match(r'(\d+)', num)
                if not base: continue
                idx = int(base.group(1)) - 1
                if idx < 0: continue
                xs.append({"type": "figure" if "fig" in kind else "table", "index": idx, "text": m.group(0), "span": [m.start(), m.end()]})
            if xs: para["cross_refs"] = xs

def merge_outputs(docling_json: Dict, grobid_meta: Dict, grobid_refs: Dict, umls_client: UMLSClient, abbrev_map: Dict[str,str]) -> Dict:
    # Handle new docling 2.48.0 structure
    doc = docling_json.get("document", {})
    
    # Extract sections from assembled body (docling 2.48.0 uses 'label' not 'type')
    sections = []
    if "assembled" in docling_json:
        body = docling_json["assembled"].get("body", [])
        current_section = {"title": "", "paragraphs": []}
        for elem in body:
            label = elem.get("label", "")
            if label == "section_header":
                if current_section["paragraphs"]:
                    sections.append(current_section)
                current_section = {"title": elem.get("text", ""), "paragraphs": []}
            elif label in ["text", "list_item"]:
                current_section["paragraphs"].append({"text": elem.get("text", "")})
        if current_section["paragraphs"]:
            sections.append(current_section)
    
    # Extract tables from document.tables
    tables = doc.get("tables", [])
    
    # Extract figures from document.pictures
    figures = doc.get("pictures", [])
    
    # Try to associate captions with figures from assembled body
    if "assembled" in docling_json:
        body = docling_json["assembled"].get("body", [])
        figure_idx = 0
        for i in range(len(body) - 1):
            elem = body[i]
            next_elem = body[i + 1]
            
            # If we find a picture followed by a caption, associate them
            if (elem.get("label") == "picture" and 
                next_elem.get("label") == "caption" and 
                figure_idx < len(figures)):
                
                caption_text = next_elem.get("text", "")
                if caption_text and not figures[figure_idx].get("captions"):
                    figures[figure_idx]["caption_text"] = caption_text
                figure_idx += 1
    
    out = {
        "metadata": grobid_meta,
        "structure": {
            "sections": sections,
            "tables": tables,
            "figures": figures,
            "citations": doc.get("citations", []),
            "n_sections": len(sections),
            "n_tables": len(tables),
            "n_figures": len(figures),
            "n_citations": len(doc.get("citations", [])),
        },
        "provenance": docling_json.get("provenance", {}),
        "grobid": {"references_tei": grobid_refs.get("references_tei")}
    }
    out = enrich_with_umls(out, umls_client, abbrev_map)
    return out