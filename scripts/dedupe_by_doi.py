#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List


def norm_doi(v: str | None) -> str:
    if not v:
        return ""
    s = str(v).strip().lower()
    if s.startswith("https://doi.org/"):
        s = s.split("/", 3)[-1]
    return s


def list_duplicates(inp: Path) -> Dict[str, List[Path]]:
    by_doi: Dict[str, List[Path]] = {}
    for p in sorted(inp.glob("*.json")):
        if p.name == "processing_report.json":
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        md = obj.get("metadata") or {}
        doi = norm_doi(md.get("doi"))
        if not doi:
            continue
        by_doi.setdefault(doi, []).append(p)
    return {k: v for k, v in by_doi.items() if len(v) > 1}


def main():
    ap = argparse.ArgumentParser(description="Detect duplicate JSONs by DOI; optional delete extras")
    ap.add_argument("--in", dest="inp", default="out/hardened", help="Input dir of JSONs")
    ap.add_argument("--report", dest="report", default="out/reports/duplicates_by_doi.csv")
    ap.add_argument("--apply", action="store_true", help="Delete duplicates, keep first by filename sorting")
    args = ap.parse_args()

    inp = Path(args.inp)
    dups = list_duplicates(inp)
    # write summary report
    from csv import DictWriter
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", newline="", encoding="utf-8") as f:
        w = DictWriter(f, fieldnames=["doi", "count", "files"])
        w.writeheader()
        for doi, files in sorted(dups.items()):
            w.writerow({"doi": doi, "count": len(files), "files": ";".join(str(p) for p in files)})

    print(f"Found {len(dups)} duplicate DOI groups; report: {args.report}")

    if args.apply:
        # Detailed removal report including original PDF filenames
        detail_path = Path("out/reports/duplicates_removed.csv")
        with open(detail_path, "w", newline="", encoding="utf-8") as df:
            dw = DictWriter(df, fieldnames=["doi", "kept_file", "removed_file", "kept_pdf", "removed_pdf"]) 
            dw.writeheader()
            removed = 0
            for doi, files in sorted(dups.items()):
                files = sorted(files, key=lambda p: str(p))
                keep = files[0]
                # load kept PDF name
                try:
                    kept_obj = json.loads(keep.read_text(encoding="utf-8"))
                    kept_pdf = (kept_obj.get("provenance", {}) or {}).get("orig_pdf_filename") or ""
                except Exception:
                    kept_pdf = ""
                for p in files[1:]:
                    try:
                        obj = json.loads(p.read_text(encoding="utf-8"))
                        removed_pdf = (obj.get("provenance", {}) or {}).get("orig_pdf_filename") or ""
                    except Exception:
                        removed_pdf = ""
                    dw.writerow({
                        "doi": doi,
                        "kept_file": str(keep),
                        "removed_file": str(p),
                        "kept_pdf": kept_pdf,
                        "removed_pdf": removed_pdf,
                    })
                    p.unlink(missing_ok=True)
                    removed += 1
                    print(f"Removed duplicate {p} (doi={doi}); kept {keep}")
        print(f"Removed {removed} duplicate files. Details: {detail_path}")


if __name__ == "__main__":
    main()
