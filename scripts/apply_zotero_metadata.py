#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.util.provenance import add_patch  # type: ignore


def log_manual_patch(prov: Dict[str, Any], path: str, old: Any, new: Any, note: str) -> None:
    prov.setdefault("patches", []).append({
        "op": "manual_replace",
        "path": path,
        "from": old,
        "to": new,
        "source": "manual_patch",
        "note": note,
        "confidence": 0.99,
    })


def norm_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.lower()
    out = []
    prev_space = False
    for ch in s:
        if ch.isalnum():
            out.append(ch)
            prev_space = False
        else:
            if not prev_space:
                out.append(" ")
                prev_space = True
    return " ".join("".join(out).split())


def token_set(s: str) -> set:
    return set(t for t in norm_text(s).split() if len(t) >= 2)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def parse_year_int(y: Any) -> Optional[int]:
    try:
        s = str(y)
        for i in range(len(s) - 3):
            sub = s[i : i + 4]
            if sub.isdigit() and sub.startswith(("19", "20")):
                return int(sub)
    except Exception:
        return None
    return None


@dataclass
class CSLItem:
    id: Optional[str]
    title: str
    title_norm: str
    doi: Optional[str]
    container_title: Optional[str]
    abstract: Optional[str]
    volume: Optional[str]
    issue: Optional[str]
    pages: Optional[str]
    issn: Optional[str]
    url: Optional[str]
    year: Optional[int]
    authors: List[str]


def load_csl_json(path: Path) -> List[CSLItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items: List[CSLItem] = []
    for it in data:
        title = it.get("title") or ""
        tnorm = norm_text(title)
        year = None
        issued = it.get("issued") or {}
        dps = issued.get("date-parts") or []
        if dps and isinstance(dps, list) and dps[0]:
            try:
                year = int(dps[0][0])
            except Exception:
                year = None
        doi = (it.get("DOI") or it.get("doi") or None)
        cont = it.get("container-title") or it.get("container_title") or None
        issn = it.get("ISSN") or it.get("issn") or None
        authors: List[str] = []
        for a in it.get("author") or []:
            if isinstance(a, dict):
                given = (a.get("given") or "").strip()
                family = (a.get("family") or "").strip()
                literal = (a.get("literal") or "").strip()
                if given or family:
                    authors.append((given + " " + family).strip())
                elif literal:
                    authors.append(literal)
        items.append(
            CSLItem(
                id=(it.get("id") or None),
                title=title,
                title_norm=tnorm,
                doi=(doi.lower() if isinstance(doi, str) else None),
                container_title=(cont if isinstance(cont, str) else None),
                abstract=(it.get("abstract") or None),
                volume=(str(it.get("volume")) if it.get("volume") is not None else None),
                issue=(str(it.get("issue")) if it.get("issue") is not None else None),
                pages=(it.get("page") or it.get("pages") or None),
                issn=(issn if isinstance(issn, str) else None),
                url=(it.get("URL") or it.get("url") or None),
                year=year,
                authors=authors,
            )
        )
    return items


@dataclass
class CSVInfo:
    key: Optional[str]
    pdf_basenames: List[str]
    title_norm: Optional[str]


def load_zotero_csv(path: Path) -> Dict[str, CSVInfo]:
    out: Dict[str, CSVInfo] = {}
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            # Columns vary; handle common cases
            key = (row.get("Key") or row.get("key") or row.get("ID") or row.get("Id") or "").strip() or None
            title = (row.get("Title") or row.get("title") or "").strip()
            tnorm = norm_text(title) if title else None
            attachments = (
                row.get("File Attachments")
                or row.get("Attachments")
                or row.get("File")
                or row.get("file")
                or ""
            )
            pdfs: List[str] = []
            if attachments:
                parts = [p.strip() for p in attachments.split(";") if p.strip()]
                for p in parts:
                    # Strip leading protocol/storage prefix
                    base = os.path.basename(p)
                    if base.lower().endswith(".pdf"):
                        pdfs.append(base)
            if key or tnorm:
                out_key = key or (tnorm or "")
                out[out_key] = CSVInfo(key=key, pdf_basenames=pdfs, title_norm=tnorm)
    return out


def first_author_last_from_json(md_authors: Any) -> Optional[str]:
    if md_authors is None:
        return None
    if isinstance(md_authors, list) and md_authors:
        first = md_authors[0]
        if isinstance(first, dict):
            fam = (first.get("family") or "").strip()
            if fam:
                return fam.lower()
            disp = (first.get("display") or "").strip()
            return disp.lower() or None
        elif isinstance(first, str):
            parts = first.split()
            if parts:
                return parts[-1].lower()
    return None


def merge_fields(obj: dict, csl: CSLItem, csvinfo: Optional[CSVInfo], match_method: str, confidence: Optional[float]) -> Tuple[dict, List[str]]:
    changed_fields: List[str] = []
    now_iso = datetime.utcnow().isoformat() + "Z"
    md = obj.setdefault("metadata", {})

    def set_field(path: str, key: str, new_val: Any, source: str):
        nonlocal changed_fields
        old_val = md.get(key)
        if old_val != new_val and new_val is not None:
            md[key] = new_val
            add_patch(obj, f"metadata.{key}", old_val, new_val, source)
            changed_fields.append(key)

    # Title: prefer richer Zotero if longer
    if not isinstance(md.get("title"), str) or len(md.get("title", "")) < len(csl.title or ""):
        set_field("metadata.title", "title", csl.title, "zotero:title")

    # Year_norm & keep raw year
    if csl.year:
        set_field("metadata.year_norm", "year_norm", str(csl.year), "zotero:year_norm")

    # Authors: replace with CSL author strings
    if csl.authors:
        set_field("metadata.authors", "authors", csl.authors, "zotero:authors")

    # DOI, Journal, Abstract, Volume/Issue/Pages/ISSN/URL
    if csl.doi:
        if not md.get("doi"):
            set_field("metadata.doi", "doi", csl.doi, "zotero:doi")
    if csl.container_title:
        if not md.get("journal"):
            set_field("metadata.journal", "journal", csl.container_title, "zotero:journal")
    if csl.abstract:
        if not md.get("abstract") or len(str(md.get("abstract") or "")) < 500:
            set_field("metadata.abstract", "abstract", csl.abstract.strip(), "zotero:abstract")
    if csl.volume and not md.get("volume"):
        set_field("metadata.volume", "volume", csl.volume, "zotero:volume")
    if csl.issue and not md.get("issue"):
        set_field("metadata.issue", "issue", csl.issue, "zotero:issue")
    if csl.pages and not md.get("pages"):
        set_field("metadata.pages", "pages", csl.pages, "zotero:pages")
    if csl.issn and not md.get("issn"):
        set_field("metadata.issn", "issn", csl.issn, "zotero:issn")
    if csl.url and not md.get("url"):
        set_field("metadata.url", "url", csl.url, "zotero:url")

    # provenance
    prov = obj.setdefault("provenance", {})
    if csvinfo and csvinfo.pdf_basenames:
        # keep first PDF basename
        if prov.get("orig_pdf_filename") != csvinfo.pdf_basenames[0]:
            old = prov.get("orig_pdf_filename")
            prov["orig_pdf_filename"] = csvinfo.pdf_basenames[0]
            add_patch(obj, "provenance.orig_pdf_filename", old, csvinfo.pdf_basenames[0], "zotero:csv")
    zez = prov.setdefault("zotero", {})
    if csvinfo and csvinfo.key:
        zez["key"] = csvinfo.key
    if csl.id and not zez.get("id"):
        zez["id"] = csl.id
    zez["source"] = "zotero_csl+csv"
    zez["exported_at"] = now_iso
    zez["match_method"] = match_method
    zez["match_confidence"] = confidence

    return obj, changed_fields


def build_indices(csl_items: List[CSLItem]):
    by_doi: Dict[str, CSLItem] = {}
    by_title: Dict[str, List[CSLItem]] = {}
    by_auth_year: Dict[str, List[CSLItem]] = {}
    for it in csl_items:
        if it.doi:
            by_doi[it.doi.lower()] = it
        by_title.setdefault(it.title_norm, []).append(it)
        if it.authors and it.year:
            first_last = it.authors[0].split()[-1].lower()
            key = f"{first_last}|{it.year}"
            by_auth_year.setdefault(key, []).append(it)
    return by_doi, by_title, by_auth_year


def main():
    ap = argparse.ArgumentParser(description="Merge Zotero CSL-JSON/CSV metadata into extracted JSONs.")
    ap.add_argument("--in", dest="inp", default="out/batch_processed", help="Input directory of extracted JSONs")
    ap.add_argument("--zotero-json", required=True, help="Path to Zotero CSL-JSON export")
    ap.add_argument("--zotero-csv", required=True, help="Path to Zotero CSV export")
    ap.add_argument("--out", dest="outdir", default="out/hardened", help="Output directory for merged JSONs")
    ap.add_argument("--report", dest="reportdir", default="out/reports", help="Output directory for merge reports")
    ap.add_argument("--dry-run", action="store_true", help="Do not write files; reports only")
    ap.add_argument("--min-fuzzy", type=float, default=0.85, help="Min Jaccard for fuzzy title match")
    ap.add_argument("--strict", action="store_true", help="Strict mode: skip writing unmatched; fail if >5% unmatched or DOI conflicts")
    ap.add_argument("--overrides", help="JSON overrides mapping filename/title_norm to Zotero key or DOI", default=None)
    args = ap.parse_args()

    inp = Path(args.inp)
    outdir = Path(args.outdir)
    reportdir = Path(args.reportdir)
    reportdir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        outdir.mkdir(parents=True, exist_ok=True)

    csl_items = load_csl_json(Path(args.zotero_json))
    csvmap = load_zotero_csv(Path(args.zotero_csv))
    by_doi, by_title, by_auth_year = build_indices(csl_items)
    by_id = {it.id: it for it in csl_items if it.id}

    overrides = {}
    if args.overrides:
        try:
            overrides = json.loads(Path(args.overrides).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: failed to load overrides: {e}")

    report_rows: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {
        "total": 0,
        "matched_doi": 0,
        "matched_title_exact": 0,
        "matched_title_fuzzy": 0,
        "matched_author_year": 0,
        "unmatched": 0,
        "doi_conflicts": 0,
        "errors": 0,
        "notes": [],
    }

    files = sorted(p for p in inp.glob("*.json") if p.name != "processing_report.json")
    for p in files:
        summary["total"] += 1
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            summary["errors"] += 1
            report_rows.append({
                "file": str(p),
                "status": "error",
                "error": str(e),
            })
            continue
        md = obj.get("metadata") or {}
        title = md.get("title") or ""
        tnorm = norm_text(title)
        doi_json = (md.get("doi") or "").lower().strip() or None
        year_json = parse_year_int(md.get("year"))
        first_last = first_author_last_from_json(md.get("authors"))

        match: Optional[CSLItem] = None
        method = ""
        conf: Optional[float] = None

        # 0) Overrides by filename or title_norm
        ov_match = None
        if overrides:
            ov_by_fn = (overrides.get('by_filename') or {})
            ov_by_title = (overrides.get('by_title') or {})
            # filename overrides may be a string or an object {doi:..., key:...}
            ov_entry = ov_by_fn.get(p.name)
            if isinstance(ov_entry, dict):
                kdoi = ov_entry.get('doi')
                kid = ov_entry.get('key')
                if isinstance(kdoi, str) and kdoi.lower() in by_doi:
                    ov_match = by_doi[kdoi.lower()]
                    method = 'override:doi'
                    conf = 1.0
                elif isinstance(kid, str) and kid in by_id:
                    ov_match = by_id[kid]
                    method = 'override:id'
                    conf = 1.0
            elif isinstance(ov_entry, str):
                k = ov_entry
                if k.lower().startswith('10.') and k.lower() in by_doi:
                    ov_match = by_doi[k.lower()]
                    method = 'override:doi'
                    conf = 1.0
                elif k in by_id:
                    ov_match = by_id[k]
                    method = 'override:id'
                    conf = 1.0
            # title overrides may contain literal field values; cache for later
            ov_title_fields = None
            if tnorm:
                ov_title_fields = ov_by_title.get(tnorm)
                if ov_title_fields is None:
                    # try raw lower as fallback
                    ov_title_fields = ov_by_title.get((title or '').strip().lower())
            if ov_match is not None:
                match = ov_match
            # if no match yet and override provides fields, we will apply them later
        if ov_match is not None:
            match = ov_match

        # Apply any by-filename manual field overrides (e.g., year/pages) regardless of match
        changed_from_fn = []
        if overrides and isinstance(ov_entry, dict):
            md_local = obj.setdefault('metadata', {})
            prov_local = obj.setdefault('provenance', {})
            def manual_set_fn(k, v):
                old = md_local.get(k)
                if v is not None and old != v:
                    md_local[k] = v
                    log_manual_patch(prov_local, f'metadata.{k}', old, v, note='override:by_filename')
                    changed_from_fn.append(k)
            for k in ('year','journal','volume','issue','pages','authors','doi'):
                if k in ov_entry:
                    val = ov_entry[k]
                    if k == 'year' and isinstance(val, (int,str)):
                        try:
                            yi = int(str(val)[:4])
                        except Exception:
                            yi = None
                        if yi is not None:
                            manual_set_fn('year', yi)
                            manual_set_fn('year_norm', str(yi))
                    elif k == 'authors' and isinstance(val, list):
                        manual_set_fn('authors', val)
                    elif k == 'doi' and isinstance(val, str):
                        manual_set_fn('doi', val)
                    else:
                        manual_set_fn(k, val)
        # 1) DOI (if not overridden)
        if doi_json and doi_json in by_doi:
            match = by_doi[doi_json]
            method = "doi"
            conf = 1.0
            summary["matched_doi"] += 1
        # 2) exact title
        elif tnorm and tnorm in by_title:
            lst = by_title[tnorm]
            match = lst[0]
            method = "title_exact"
            conf = 1.0
            summary["matched_title_exact"] += 1
        else:
            # 3) fuzzy title
            best: Tuple[Optional[CSLItem], float] = (None, 0.0)
            if tnorm:
                a = token_set(title)
                for it in csl_items:
                    b = token_set(it.title)
                    s = jaccard(a, b)
                    if s > best[1]:
                        best = (it, s)
                if best[0] is not None and best[1] >= args.min_fuzzy:
                    match = best[0]
                    method = "title_fuzzy"
                    conf = round(best[1], 4)
                    summary["matched_title_fuzzy"] += 1

        # 4) author+year backup (if still no match)
        if match is None and first_last and year_json is not None:
            key = f"{first_last}|{year_json}"
            lst = by_auth_year.get(key)
            if lst:
                match = lst[0]
                method = "author_year"
                conf = 0.9
                summary["matched_author_year"] += 1

        if match is None:
            summary["unmatched"] += 1
            # Apply manual field overrides by title if provided
            if overrides and 'ov_title_fields' in locals() and ov_title_fields:
                prov = obj.setdefault('provenance', {})
                md = obj.setdefault('metadata', {})
                changed_fields = []
                def manual_set(k, v):
                    nonlocal changed_fields
                    old = md.get(k)
                    if old != v and v is not None:
                        md[k] = v
                        log_manual_patch(prov, f'metadata.{k}', old, v, note='override:by_title')
                        changed_fields.append(k)
                # known fields
                if 'journal' in ov_title_fields:
                    manual_set('journal', ov_title_fields['journal'])
                if 'year' in ov_title_fields:
                    y = ov_title_fields['year']
                    manual_set('year', int(y))
                    manual_set('year_norm', str(y))
                if 'volume' in ov_title_fields:
                    manual_set('volume', str(ov_title_fields['volume']))
                if 'pages' in ov_title_fields:
                    manual_set('pages', ov_title_fields['pages'])
                if 'authors' in ov_title_fields and isinstance(ov_title_fields['authors'], list):
                    manual_set('authors', ov_title_fields['authors'])

                status = 'manual_override' if changed_fields else 'unmatched'
                report_rows.append({
                    'file': str(p),
                    'status': status,
                    'match_method': 'override:by_title' if changed_fields else '',
                    'match_confidence': '',
                    'changed_fields': ';'.join(changed_fields),
                    'doi_json': doi_json or '',
                    'doi_zotero': '',
                    'doi_conflict': '',
                    'pdf_basename': '',
                    'title_norm': tnorm,
                })
                # write out if not dry-run
                if changed_fields and not args.dry_run:
                    (outdir / p.name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
                continue
            else:
                report_rows.append({
                    "file": str(p),
                    "status": "unmatched",
                    "title_norm": tnorm,
                })
                if not args.strict and not args.dry_run:
                    # pass-through write
                    (outdir / p.name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
                continue

        # check DOI conflict
        doi_conflict = False
        if doi_json and match.doi and doi_json != match.doi:
            doi_conflict = True
            summary["doi_conflicts"] += 1

        # Merge and write
        csvinfo = None
        # CSV: prefer by key if match.id; else by title
        if match.id and match.id in csvmap:
            csvinfo = csvmap[match.id]
        else:
            # attempt by normalized title match
            for info in csvmap.values():
                if info.title_norm and info.title_norm == match.title_norm:
                    csvinfo = info
                    break

        merged_obj, changed = merge_fields(obj, match, csvinfo, match_method=method, confidence=conf)
        status = "changed" if changed else "unchanged"

        if not args.dry_run and (not args.strict or (args.strict and not doi_conflict)):
            (outdir / p.name).write_text(json.dumps(merged_obj, ensure_ascii=False, indent=2), encoding="utf-8")

        report_rows.append({
            "file": str(p),
            "status": status,
            "match_method": method,
            "match_confidence": conf if conf is not None else "",
            "changed_fields": ";".join(changed),
            "doi_json": doi_json or "",
            "doi_zotero": match.doi or "",
            "doi_conflict": "yes" if doi_conflict else "",
            "pdf_basename": (csvinfo.pdf_basenames[0] if csvinfo and csvinfo.pdf_basenames else ""),
        })

    # Write reports
    rep_csv = reportdir / "zotero_merge_report.csv"
    with rep_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "file",
            "status",
            "match_method",
            "match_confidence",
            "changed_fields",
            "doi_json",
            "doi_zotero",
            "doi_conflict",
            "pdf_basename",
            "title_norm",
            "error",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in report_rows:
            if "error" not in row:
                row["error"] = ""
            w.writerow(row)

    rep_json = reportdir / "zotero_merge_summary.json"
    rep_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Strict gates
    if args.strict:
        if summary["total"] > 0 and (summary["unmatched"] / summary["total"]) > 0.05:
            print("Strict mode: too many unmatched files", file=sys.stderr)
            sys.exit(2)
        if summary["doi_conflicts"] > 0:
            print("Strict mode: DOI conflicts detected", file=sys.stderr)
            sys.exit(3)

    print("Zotero merge complete.")
    for k in ("total", "matched_doi", "matched_title_exact", "matched_title_fuzzy", "matched_author_year", "unmatched", "doi_conflicts"):
        print(f"  {k}: {summary[k]}")


if __name__ == "__main__":
    main()
