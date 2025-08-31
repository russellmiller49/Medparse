#!/usr/bin/env python3
from __future__ import annotations
import json, re, math, argparse, uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple

# -----------------------
# Helpers
# -----------------------

HEADING_STOP = {
  "acknowledgements","acknowledgments","author contributions","correspondence","references",
  "supplementary","funding","copyright"
}

def sent_split(text: str) -> List[str]:
    # conservative sentence split
    text = re.sub(r"\s+", " ", text).strip()
    if not text: return []
    parts = re.split(r"(?<=[\.\?\!])\s+(?=[A-Z\(])", text)
    return [s.strip() for s in parts if s.strip()]

def word_count(s: str) -> int:
    return 0 if not s else len(s.split())

def approx_tokens(s: str) -> int:
    # rough: 1 token ~= 1.3 words for scientific prose
    return int(round(word_count(s) * 1.3))

def chunk_id(prefix: str) -> str:
    return f"{prefix}::{uuid.uuid4().hex[:8]}"

def section_is_boilerplate(title: str) -> bool:
    t = (title or "").lower().strip()
    if t in HEADING_STOP: return True
    # generic affiliation/correspondence detectors
    low = t.lower()
    if any(k in low for k in ["department","university","hospital","institute","correspondence","email","orcid"]):
        return True
    return False

def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

# -----------------------
# Stats extraction on text (optional reinforcement)
# -----------------------

STAT_RX = {
  "p_value": re.compile(r'\b[Pp]\s*([=<>≤≥])\s*(0?\.\d+)\b'),
  "ci_95":   re.compile(r'(?:95%?\s*CI[:=]?\s*)?\[?\(?\s*(-?\d+\.?\d*)\s*[-–,]\s*(-?\d+\.?\d*)\s*\]?\)?'),
  "hr":      re.compile(r'\bHR\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\b'),
  "or":      re.compile(r'\bOR\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\b'),
  "rr":      re.compile(r'\bRR\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\b')
}

def find_stats_spans(text: str) -> List[Dict[str,Any]]:
    out = []
    for kind, rx in STAT_RX.items():
        for m in rx.finditer(text):
            out.append({"kind": kind, "start": m.start(), "end": m.end(), "value": m.group(0)})
    return sorted(out, key=lambda x: x["start"])

# -----------------------
# Core chunking
# -----------------------

def build_text_chunks(struct: Dict[str, Any], paper_prefix: str, target_tokens=1000, max_tokens=1200, overlap=100) -> Tuple[List[Dict], Dict]:
    chunks = []
    metrics = {"n_sections": 0, "n_text_chunks": 0, "token_sum": 0, "token_sizes": []}

    for sec in struct.get("sections", []):
        title = normalize_whitespace(sec.get("title",""))
        if section_is_boilerplate(title):  # skip
            continue

        paras = [normalize_whitespace(p.get("text","")) for p in sec.get("paragraphs", []) if normalize_whitespace(p.get("text",""))]
        if not paras: 
            continue

        metrics["n_sections"] += 1

        # Split paragraphs into sentences, then pack
        sents = []
        for p in paras:
            sents.extend(sent_split(p))

        # Greedy packing
        i = 0
        while i < len(sents):
            cur = []
            cur_tokens = 0
            while i < len(sents) and (cur_tokens + approx_tokens(sents[i]) <= max_tokens or not cur):
                cur.append(sents[i]); cur_tokens += approx_tokens(sents[i]); i += 1
                if cur_tokens >= target_tokens: break

            text_block = " ".join(cur).strip()
            # compute stats micro-annotations within this block (optional; main stats live in doc['statistics'])
            stats_spans = find_stats_spans(text_block)

            c = {
                "id": chunk_id(f"{paper_prefix}:text"),
                "type": "text",
                "title": title,
                "section_category": sec.get("category","other"),
                "text": text_block,
                "stats_inline": stats_spans,  # hints for UI; your doc-level stats remain authoritative
            }
            chunks.append(c)
            metrics["n_text_chunks"] += 1
            metrics["token_sum"] += approx_tokens(text_block)
            metrics["token_sizes"].append(approx_tokens(text_block))

            # backtrack overlap in sentences for next window
            if overlap > 0 and i < len(sents):
                # move pointer back by ~overlap tokens (approx by sentences)
                back = 0; t = 0
                while back < len(cur) and t < overlap:
                    t += approx_tokens(cur[-1 - back]); back += 1
                i = max(0, i - back)

    return chunks, metrics

def build_table_chunks(struct: Dict[str, Any], paper_prefix: str) -> List[Dict]:
    out = []
    for idx, t in enumerate(struct.get("tables", []) or []):
        caption = normalize_whitespace(t.get("caption") or t.get("title") or "")
        data    = t.get("data") or t.get("cells")
        out.append({
            "id": chunk_id(f"{paper_prefix}:table"),
            "type": "table",
            "label": f"Table {idx+1}",
            "title": caption or f"Table {idx+1}",
            "caption": caption,
            "data": data,
            "source_pages": t.get("pages") or [],
            "bbox": t.get("bbox") or t.get("prov",{}).get("bbox"),
        })
    return out

def build_figure_chunks(struct: Dict[str, Any], paper_prefix: str) -> List[Dict]:
    out = []
    figs = struct.get("figures", []) or []
    for idx, f in enumerate(figs):
        caption = normalize_whitespace(f.get("caption",""))
        ocr = normalize_whitespace(f.get("ocr_text",""))
        textual = bool(ocr and len(ocr.split()) >= 10)
        out.append({
            "id": chunk_id(f"{paper_prefix}:figure"),
            "type": "figure",
            "label": f"Figure {idx+1}",
            "caption": caption,
            "ocr_text": ocr if textual else "",
            "textual": textual,
            "source_pages": [f.get("page")] if f.get("page") is not None else (f.get("pages") or []),
            "bbox": f.get("bbox") or f.get("prov",{}).get("bbox"),
            "image_path": f.get("image_path") or f.get("file")
        })
    return out

def attach_crossrefs(text_chunks: List[Dict], table_chunks: List[Dict], figure_chunks: List[Dict]) -> None:
    # naive index mapping by label
    tmap = {t["label"].lower(): t["id"] for t in table_chunks}
    fmap = {f["label"].lower(): f["id"] for f in figure_chunks}

    rx = re.compile(r'\b(Figure|Fig\.|Table)\s+(\d+[A-Za-z]?)\b', re.I)
    for c in text_chunks:
        txt = c.get("text","")
        linked_tables, linked_figs = set(), set()
        for m in rx.finditer(txt):
            kind = m.group(1).lower()
            num  = m.group(2).lower()
            if "fig" in kind:
                fid = fmap.get(f"figure {num}")
                if fid: linked_figs.add(fid)
            else:
                tid = tmap.get(f"table {num}")
                if tid: linked_tables.add(tid)
        if linked_tables:
            c["linked_tables"] = sorted(list(linked_tables))
        if linked_figs:
            c["linked_figures"] = sorted(list(linked_figs))

def build_stats_microchunks(stats: List[Dict[str,Any]], full_text: str, paper_prefix: str, window_sents=2) -> List[Dict]:
    if not stats or not full_text: return []
    sents = sent_split(full_text)
    # build char offsets of sentence boundaries
    offsets = []
    pos = 0
    for s in sents:
        start = full_text.find(s, pos)
        if start < 0: start = pos
        end = start + len(s)
        offsets.append((start, end))
        pos = end

    out = []
    for st in stats:
        if not isinstance(st, dict) or "start" not in st or "end" not in st:
            # skip doc-level stats without spans; you can still keep them at doc root
            continue
        # find sentence containing the stat
        span_mid = (st["start"] + st["end"]) // 2
        idx = 0
        for i,(a,b) in enumerate(offsets):
            if a <= span_mid <= b: idx = i; break
        i0 = max(0, idx - window_sents)
        i1 = min(len(sents), idx + window_sents + 1)
        ctx = " ".join(sents[i0:i1]).strip()
        out.append({
            "id": chunk_id(f"{paper_prefix}:stats"),
            "type": "stats",
            "title": f"Stats — {st.get('type','measure').upper()}",
            "text": ctx,
            "stat": st
        })
    return out

def compute_report(all_chunks: List[Dict], text_metrics: Dict) -> Dict:
    sizes = [approx_tokens(c["text"]) for c in all_chunks if c["type"] == "text" and c.get("text")]
    avg = (sum(sizes)/len(sizes)) if sizes else 0
    stdev = ( (sum((x-avg)**2 for x in sizes)/(len(sizes)-1))**0.5 ) if len(sizes) > 1 else 0
    return {
        "n_chunks_total": len(all_chunks),
        "n_text_chunks": text_metrics.get("n_text_chunks", 0),
        "avg_tokens_text": round(avg,1),
        "stdev_tokens_text": round(stdev,1),
        "n_sections": text_metrics.get("n_sections", 0)
    }

# -----------------------
# CLI
# -----------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True, help="Path to merged paper JSON")
    ap.add_argument("--outdir", required=True, help="Output directory for chunks")
    ap.add_argument("--paper_id", default=None, help="Optional paper id prefix")
    ap.add_argument("--target_tokens", type=int, default=1000)
    ap.add_argument("--max_tokens", type=int, default=1200)
    ap.add_argument("--overlap_tokens", type=int, default=100)
    args = ap.parse_args()

    infile = Path(args.infile)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    paper = json.loads(infile.read_text(encoding="utf-8"))

    title = paper.get("metadata",{}).get("title") or infile.stem
    prefix = args.paper_id or f"paper:{infile.stem}"

    struct = paper.get("structure", {}) or {}
    # 1) build chunks
    text_chunks, tm = build_text_chunks(struct, prefix, args.target_tokens, args.max_tokens, args.overlap_tokens)
    table_chunks    = build_table_chunks(struct, prefix)
    figure_chunks   = build_figure_chunks(struct, prefix)

    # 2) attach cross-refs into text
    attach_crossrefs(text_chunks, table_chunks, figure_chunks)

    # 3) stats micro-chunks (if doc-level stats exist with spans)
    stats_doc = paper.get("statistics", [])
    fulltext = "\n\n".join(p.get("text","") for s in struct.get("sections",[]) for p in s.get("paragraphs",[]))
    stat_chunks = build_stats_microchunks(stats_doc, fulltext, prefix)

    all_chunks = text_chunks + table_chunks + figure_chunks + stat_chunks

    # 4) write .jsonl
    chunks_path = outdir / f"{infile.stem}.chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # 5) small report
    report = compute_report(all_chunks, tm)
    report_path = outdir / f"{infile.stem}.chunks.report.json"
    report.update({
        "title": title,
        "source_json": str(infile),
        "n_tables": len(table_chunks),
        "n_figures": len(figure_chunks),
        "n_stats_microchunks": len(stat_chunks)
    })
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {chunks_path} ({report['n_chunks_total']} chunks)")
    print(f"Report: {report_path}")

if __name__ == "__main__":
    main()