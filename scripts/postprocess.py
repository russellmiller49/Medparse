from __future__ import annotations
import re
from typing import Dict, Any, List
from lxml import etree
from .umls_linker import UMLSClient, normalize_terms, link_umls_phrases
from .table_normalizer import normalize_table
from .text_assembler import (
    assemble_sections,
    build_full_text,
    compute_page_text_ratio,
)

def parse_grobid_metadata(tei_xml: str) -> Dict[str, Any]:
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}

    root = etree.fromstring(tei_xml.encode("utf-8"))

    def _text_list(node, xpath: str) -> List[str]:
        return [t.strip() for t in node.xpath(xpath, namespaces=ns) if isinstance(t, str) and t.strip()]

    def _affiliation_payload(aff) -> Dict[str, Any]:
        orgs = _text_list(aff, ".//tei:orgName/text()")
        address: Dict[str, Any] = {}
        settlements = _text_list(aff, ".//tei:address/tei:settlement/text()")
        if settlements:
            address["city"] = settlements[0]
        regions = _text_list(aff, ".//tei:address/tei:region/text()")
        if regions:
            address["region"] = regions[0]
        country = aff.xpath("string(.//tei:address/tei:country)", namespaces=ns).strip()
        if country:
            address["country"] = country
        parts = orgs[:]
        if address.get("city"):
            parts.append(address["city"])
        if address.get("region") and address["region"] not in parts:
            parts.append(address["region"])
        if address.get("country") and address["country"] not in parts:
            parts.append(address["country"])
        payload: Dict[str, Any] = {}
        if parts:
            payload["text"] = ", ".join(parts)
        if orgs:
            payload["organizations"] = orgs
        if address:
            payload["address"] = address
        return payload

    def _author_payload(author_el) -> Dict[str, Any]:
        forenames = _text_list(author_el, "./tei:persName/tei:forename/text()")
        surname = author_el.xpath("string(./tei:persName/tei:surname)", namespaces=ns).strip()
        given = " ".join(forenames)
        full_name = " ".join(part for part in [given, surname] if part)
        if not full_name and not (surname or given):
            return {}
        role_names = _text_list(author_el, "./tei:persName/tei:roleName/text()")
        email = author_el.xpath("string(./tei:email)", namespaces=ns).strip()
        affiliations = []
        for aff in author_el.xpath("./tei:affiliation", namespaces=ns):
            payload = _affiliation_payload(aff)
            if payload:
                affiliations.append(payload)
        author_payload: Dict[str, Any] = {
            "given": given or None,
            "family": surname or None,
            "full_name": full_name or None,
            "qualifications": ", ".join(role_names) if role_names else None,
            "email": email or None,
            "is_corresponding": author_el.get("role") == "corresp",
            "affiliations": affiliations,
        }
        if author_payload.get("full_name"):
            display = author_payload["full_name"]
        else:
            display = author_payload.get("family") or author_payload.get("given")
        author_payload["display"] = display
        # Prune empty fields
        return {k: v for k, v in author_payload.items() if v not in (None, [], "")}

    title = root.xpath("string(//tei:teiHeader//tei:titleStmt/tei:title)", namespaces=ns) or None
    year = root.xpath(
        "string(//tei:teiHeader//tei:sourceDesc//tei:biblStruct//tei:imprint/tei:date/@when)",
        namespaces=ns,
    ) or root.xpath(
        "string(//tei:teiHeader//tei:profileDesc//tei:creation/tei:date/@when)",
        namespaces=ns,
    ) or None

    author_nodes = root.xpath(
        "//tei:teiHeader//tei:sourceDesc//tei:biblStruct/tei:analytic/tei:author",
        namespaces=ns,
    )
    authors = [payload for node in author_nodes for payload in [_author_payload(node)] if payload]

    # Capture corresponding author summary if available
    corresponding = next((a for a in authors if a.get("is_corresponding")), None)
    corresponding_summary = None
    if corresponding:
        corresponding_summary = {
            "name": corresponding.get("display"),
            "email": corresponding.get("email"),
            "affiliations": corresponding.get("affiliations"),
        }

    refs_text = [
        etree.tostring(n, method="text", encoding="unicode").strip()
        for n in root.xpath("//tei:text//tei:listBibl/tei:biblStruct", namespaces=ns)
    ]

    payload: Dict[str, Any] = {
        "title": title,
        "year": year,
        "authors": authors,
        "references_text": refs_text,
    }
    if corresponding_summary:
        payload["corresponding_author"] = corresponding_summary
    return payload


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
    sections = doc.get("structure", {}).get("sections", [])
    return build_full_text(sections, limit=limit_chars)

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

def merge_outputs(
    docling_json: Dict,
    grobid_meta: Dict,
    grobid_refs: Dict,
    umls_client: UMLSClient | None,
    abbrev_map: Dict[str, str],
    *,
    tei_xml: str | None = None,
) -> Dict:
    doc = docling_json.get("document", {})

    sections = assemble_sections(tei_xml, docling_json)
    tables = doc.get("tables", [])
    figures = doc.get("pictures", [])

    if "assembled" in docling_json:
        body = docling_json["assembled"].get("body", [])
        figure_idx = 0
        for i in range(len(body) - 1):
            elem = body[i]
            next_elem = body[i + 1]
            if (
                elem.get("label") == "picture"
                and next_elem.get("label") == "caption"
                and figure_idx < len(figures)
            ):
                caption_text = next_elem.get("text", "")
                if caption_text and not figures[figure_idx].get("captions"):
                    figures[figure_idx]["caption_text"] = caption_text
                figure_idx += 1

    full_text = build_full_text(sections)
    ratio = compute_page_text_ratio(docling_json, full_text)

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
        "grobid": {"references_tei": grobid_refs.get("references_tei")},
        "full_text": full_text,
    }

    if ratio is not None:
        out.setdefault("metrics", {})["page_text_ratio"] = ratio

    if umls_client:
        out = enrich_with_umls(out, umls_client, abbrev_map)

    return out
