import json
from pathlib import Path
import argparse

def load_json(out_root, linker, stem):
    p = Path(out_root) / f"json_{linker}" / f"{stem}.json"
    if not p.exists(): return None
    return json.loads(p.read_text(encoding="utf-8"))

def summary(doc):
    if not doc: return {"links":0,"local":0,"score":None,"title":None}
    return {
        "title": doc.get("metadata",{}).get("title"),
        "links": len(doc.get("umls_links", [])),
        "local": len(doc.get("umls_links_local", [])),
        "score": doc.get("validation",{}).get("completeness_score")
    }

def compare(stem, out_root="out"):
    umls = load_json(out_root,"umls",stem)
    sspa = load_json(out_root,"scispacy",stem)
    quml = load_json(out_root,"quickumls",stem)
    
    su = summary(umls); ss = summary(sspa); sq = summary(quml)
    print(f"\n== {stem} ==")
    print(f"Title: {su['title'] or ss['title'] or sq['title']}")
    print(f"UMLS: links={su['links']} local={su['local']} score={su['score']}")
    print(f"scispaCy: links={ss['links']} local={ss['local']} score={ss['score']}")
    print(f"QuickUMLS: links={sq['links']} local={sq['local']} score={sq['score']}")

def main(stems, out_root="out"):
    for s in stems:
        compare(s, out_root=out_root)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf_stems", nargs="+", required=True, help="filestems without .pdf")
    ap.add_argument("--out_root", default="out")
    a = ap.parse_args()
    main(a.pdf_stems, out_root=a.out_root)

