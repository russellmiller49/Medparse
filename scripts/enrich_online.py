#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from urllib.parse import urlencode, quote
    from urllib.request import Request, urlopen
    import ssl
except Exception:  # pragma: no cover
    print("Python stdlib urllib not available", file=sys.stderr)
    raise

# Make local imports available
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.util.provenance import add_patch  # type: ignore


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


def first_author_family(md_authors: Any) -> Optional[str]:
    if isinstance(md_authors, list) and md_authors:
        first = md_authors[0]
        if isinstance(first, dict):
            fam = (first.get("family") or "").strip()
            if fam:
                return fam.lower()
            disp = (first.get("display") or "").strip()
            return disp.split()[-1].lower() if disp else None
        elif isinstance(first, str):
            parts = first.split()
            return parts[-1].lower() if parts else None
    return None


@dataclass
class CrossrefItem:
    doi: Optional[str]
    title: str
    container_title: Optional[str]
    year: Optional[int]
    volume: Optional[str]
    issue: Optional[str]
    pages: Optional[str]
    issn: Optional[str]
    url: Optional[str]
    first_author_family: Optional[str]


def _extract_year(msg: Dict[str, Any]) -> Optional[int]:
    for key in ("issued", "created", "published-print", "published-online"):
        obj = msg.get(key) or {}
        dps = obj.get("date-parts") or []
        if dps and isinstance(dps, list) and dps[0]:
            try:
                return int(dps[0][0])
            except Exception:
                continue
    return None


def _ascii_clean(s: str) -> str:
    try:
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    except Exception:
        return s


STOP = {"the","a","an","and","or","of","in","to","for","on","with","vs","versus","first","study","trial","randomized","uk","united","kingdom"}


def _shrink_title(title: str) -> str:
    toks = [t for t in norm_text(title).split() if t and t not in STOP]
    if len(toks) > 14:
        toks = toks[:14]
    return _ascii_clean(" ".join(toks))


def crossref_query(title: str, year: Optional[int], ua_email: str, author_last: Optional[str] = None, delay_s: float = 0.2, rows: int = 5) -> List[CrossrefItem]:
    qtitle = _shrink_title(title)
    params = {
        "rows": str(rows),
        "select": "DOI,title,author,issued,container-title,ISSN,URL,volume,issue,page",
        "query.title": qtitle,
    }
    if author_last:
        params["query.author"] = author_last
    if year:
        params["filter"] = f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"
    url = "https://api.crossref.org/works?" + urlencode(params)
    headers = {
        "User-Agent": f"Medparse/1.0 (mailto:{ua_email})",
        "Accept": "application/json",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # pragma: no cover
        # Retry once without certificate verification (CLI envs sometimes lack CA bundle)
        try:
            ctx = ssl._create_unverified_context()
            with urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []
    finally:
        time.sleep(delay_s)
    items = []
    for it in (data.get("message", {}).get("items", []) or [])[:rows]:
        title_list = it.get("title") or []
        title0 = title_list[0] if title_list else ""
        cauth = None
        auths = it.get("author") or []
        if auths:
            a0 = auths[0]
            if isinstance(a0, dict):
                cauth = (a0.get("family") or "").strip().lower() or None
        items.append(
            CrossrefItem(
                doi=(it.get("DOI") or "").lower() or None,
                title=title0,
                container_title=((it.get("container-title") or [None])[0] if isinstance(it.get("container-title"), list) else it.get("container-title")),
                year=_extract_year(it),
                volume=str(it.get("volume")) if it.get("volume") is not None else None,
                issue=str(it.get("issue")) if it.get("issue") is not None else None,
                pages=(it.get("page") or None),
                issn=((it.get("ISSN") or [None])[0] if isinstance(it.get("ISSN"), list) else it.get("ISSN")),
                url=(it.get("URL") or None),
                first_author_family=cauth,
            )
        )
    return items


def score_candidate(src_title: str, src_year: Optional[int], src_first_last: Optional[str], cand: CrossrefItem) -> float:
    a = token_set(src_title)
    b = token_set(cand.title)
    s = jaccard(a, b)
    bonus = 0.0
    if src_year and cand.year and abs(src_year - cand.year) <= 0:
        bonus += 0.04
    if src_first_last and cand.first_author_family and src_first_last == cand.first_author_family:
        bonus += 0.06
    return s + bonus


def enrich_one(p: Path, ua_email: str) -> Tuple[Dict[str, Any], List[str]]:
    obj = json.loads(p.read_text(encoding="utf-8"))
    md = obj.setdefault("metadata", {})
    title = md.get("title") or ""
    year = None
    # Prefer normalized year fields if present
    yraw = md.get("year") or md.get("year_norm")
    try:
        if yraw is not None:
            year = int(str(yraw)[:4])
    except Exception:
        year = None
    first_last = first_author_family(md.get("authors"))

    need_doi = not bool(md.get("doi"))
    need_journal = not bool(md.get("journal") or md.get("journal_full") or md.get("container-title"))
    if not (need_doi or need_journal):
        return obj, []

    cands = crossref_query(title, year, ua_email=ua_email)
    if not cands:
        return obj, []
    best: Tuple[Optional[CrossrefItem], float] = (None, 0.0)
    for c in cands:
        sc = score_candidate(title, year, first_last, c)
        if sc > best[1]:
            best = (c, sc)
    cand, score = best
    if cand is None:
        return obj, []

    # acceptance: very strict
    accept = score >= 0.92 or (score >= 0.88 and year and cand.year == year and first_last and cand.first_author_family == first_last)
    if not accept:
        return obj, []

    changed: List[str] = []
    # DOI
    if need_doi and cand.doi:
        old = md.get("doi")
        md["doi"] = cand.doi
        add_patch(obj, "metadata.doi", old, cand.doi, source="crossref", confidence=score)
        changed.append("doi")
    # Journal
    if need_journal and cand.container_title:
        old = md.get("journal") or md.get("journal_full")
        md["journal"] = cand.container_title
        add_patch(obj, "metadata.journal", old, cand.container_title, source="crossref", confidence=score)
        changed.append("journal")
    # Fill volume/issue/pages if missing (optional)
    for k, val in ("volume", cand.volume), ("issue", cand.issue), ("pages", cand.pages), ("issn", cand.issn), ("url", cand.url):
        if val and not md.get(k):
            old = md.get(k)
            md[k] = val
            add_patch(obj, f"metadata.{k}", old, val, source="crossref", confidence=score)
            changed.append(k)
    # Normalize year_norm if missing and we trust the candidate
    if cand.year and not md.get("year_norm"):
        old = md.get("year_norm")
        md["year_norm"] = str(cand.year)
        add_patch(obj, "metadata.year_norm", old, str(cand.year), source="crossref", confidence=score)
        changed.append("year_norm")
    return obj, changed


def main():
    ap = argparse.ArgumentParser(description="Online enrichment for DOI/journal using Crossref (strict matching).")
    ap.add_argument("--in", dest="inp", default="out/hardened", help="Input directory of JSONs")
    ap.add_argument("--out", dest="outdir", default="out/hardened", help="Output directory for enriched JSONs")
    ap.add_argument("--report", dest="reportdir", default="out/reports", help="Output directory for reports")
    ap.add_argument("--dry-run", action="store_true", help="Report changes only; do not write files")
    ap.add_argument("--email", default="devnull@example.com", help="Contact email for Crossref User-Agent")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of files")
    args = ap.parse_args()

    inp = Path(args.inp)
    outdir = Path(args.outdir)
    reportdir = Path(args.reportdir)
    reportdir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        outdir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in inp.glob("*.json") if p.name != "processing_report.json")
    if args.limit:
        files = files[: args.limit]

    changed_total = 0
    unchanged_total = 0
    errors = 0
    rows: List[Dict[str, Any]] = []

    for p in files:
        try:
            obj_before = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            errors += 1
            rows.append({"file": str(p), "status": "error", "error": str(e)})
            continue
        md = obj_before.get("metadata") or {}
        if md.get("doi") and (md.get("journal") or md.get("journal_full")):
            unchanged_total += 1
            rows.append({"file": str(p), "status": "skip_complete"})
            continue
        try:
            obj_after, changed_fields = enrich_one(p, ua_email=args.email)
        except Exception as e:  # pragma: no cover
            errors += 1
            rows.append({"file": str(p), "status": "error", "error": str(e)})
            continue
        if changed_fields:
            changed_total += 1
            rows.append({
                "file": str(p),
                "status": "changed" if not args.dry_run else "dry-run",
                "changed_fields": ";".join(sorted(set(changed_fields))),
            })
            if not args.dry_run:
                (outdir / p.name).write_text(json.dumps(obj_after, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            unchanged_total += 1
            rows.append({"file": str(p), "status": "unchanged"})

    # Write reports
    import csv

    csv_path = reportdir / ("enrich_online_dryrun.csv" if args.dry_run else "enrich_online_changes.csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "status", "changed_fields", "error"])
        w.writeheader()
        for r in rows:
            if "changed_fields" not in r:
                r["changed_fields"] = ""
            if "error" not in r:
                r["error"] = ""
            w.writerow(r)

    summary = {
        "total": len(files),
        "changed": changed_total,
        "unchanged": unchanged_total,
        "errors": errors,
        "report": str(csv_path),
        "dry_run": bool(args.dry_run),
    }
    (reportdir / "enrich_online_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Online enrichment complete.")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
