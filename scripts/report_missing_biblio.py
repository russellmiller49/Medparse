#!/usr/bin/env python3
import csv
import json
import sys
from pathlib import Path
from urllib.parse import urlencode


def norm_first_author(auth):
    if not auth:
        return ""
    if isinstance(auth, list) and auth:
        a0 = auth[0]
        if isinstance(a0, dict):
            fam = (a0.get("family") or "").strip()
            if fam:
                return fam
            disp = (a0.get("display") or "").strip()
            return (disp.split()[-1] if disp else "")
        elif isinstance(a0, str):
            return a0.split()[-1]
    return ""


def build_crossref_url(title: str, year: str | int | None, author_last: str | None):
    q = title or ""
    params = {
        "query.bibliographic": q,
        "rows": "5",
    }
    if year:
        params["filter"] = f"from-pub-date:{str(year)[:4]}-01-01,until-pub-date:{str(year)[:4]}-12-31"
    if author_last:
        params["query.author"] = author_last
    return "https://api.crossref.org/works?" + urlencode(params)


def main():
    issues_csv = Path("out/reports_post_enrich/quality_issues.csv")
    if not issues_csv.exists():
        print("issues CSV not found; run audit first.", file=sys.stderr)
        sys.exit(1)

    # collect candidates
    cand_files = []
    with issues_csv.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            issues = row.get("issues") or ""
            if "META_DOI_MISSING" in issues or "META_JOURNAL_MISSING" in issues:
                cand_files.append(row["file"]) 

    # dedupe
    cand_files = sorted(dict.fromkeys(cand_files))

    rows = []
    for fp in cand_files:
        p = Path(fp)
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        md = obj.get("metadata", {})
        title = md.get("title") or ""
        year = md.get("year") or md.get("year_norm") or ""
        first_last = norm_first_author(md.get("authors"))
        doi = md.get("doi") or ""
        journal = md.get("journal") or md.get("journal_full") or ""
        url = build_crossref_url(title, year, first_last)
        rows.append({
            "file": str(p),
            "title": title,
            "year": str(year)[:4] if year else "",
            "first_author": first_last,
            "doi": doi,
            "journal": journal,
            "crossref_url": url,
        })

    out_csv = Path("out/reports/remaining_doi_journal_gaps.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "file", "title", "year", "first_author", "doi", "journal", "crossref_url"
        ])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Wrote {len(rows)} rows to {out_csv}")


if __name__ == "__main__":
    main()
