#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path

# Strict tokens per spec
ACK_TOKENS = (
    "author contributions",
    "contribution",
    "guarantor",
    "ethics",
    "conflict of interest",
    "acknowledg",
    "funding",
    "data availability",
    "investigator list",
    "supplementary",
)


def detect_ack_like(tokens):
    if not tokens:
        return False, 0.0
    hits = 0
    for t in tokens:
        if isinstance(t, str):
            low = t.lower()
            if any(tok in low for tok in ACK_TOKENS):
                hits += 1
    ratio = hits / max(1, len(tokens))
    return hits > 0, ratio


def is_blank(x):
    if x is None:
        return True
    if isinstance(x, str):
        return not x.strip()
    if isinstance(x, (list, dict)):
        return len(x) == 0
    return False


def audit_dir(in_dir: Path, out_dir: Path, limit: int | None = None):
    files = sorted(p for p in in_dir.rglob("*.json"))
    if limit:
        files = files[:limit]
    year_re = re.compile(r"^\d{4}(?:-(?:0[1-9]|1[0-2]))?(?:-(?:0[1-9]|[12]\d|3[01]))?$")

    summary = {
        "total_files": 0,
        "json_errors": 0,
        "missing_metadata": 0,
        "missing_title": 0,
        "missing_year": 0,
        "invalid_year_format": 0,
        "missing_authors": 0,
        "empty_authors": 0,
        "authors_ack_like": 0,
        "missing_doi": 0,
        "missing_journal": 0,
        "missing_abstract": 0,
        "has_references_text": 0,
        "has_references_struct": 0,
        "empty_references_struct": 0,
    }

    details_rows = []

    for p in files:
        summary["total_files"] += 1
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            summary["json_errors"] += 1
            details_rows.append({
                "file": str(p),
                "error": "json_error",
            })
            continue

        md = obj.get("metadata")
        if not isinstance(md, dict):
            summary["missing_metadata"] += 1
            details_rows.append({
                "file": str(p),
                "error": "missing_metadata",
            })
            continue

        # Title
        title = md.get("title")
        if is_blank(title):
            summary["missing_title"] += 1

        # Year
        year = md.get("year")
        if is_blank(year):
            summary["missing_year"] += 1
        else:
            ys = str(year).strip()
            if not year_re.match(ys):
                summary["invalid_year_format"] += 1

        # Authors
        authors = md.get("authors")
        if authors is None:
            summary["missing_authors"] += 1
        else:
            # normalize to list of strings
            norm = []
            group_only = True
            if isinstance(authors, str):
                norm = [a.strip() for a in authors.split(";") if a.strip()]
                group_only = False
            elif isinstance(authors, list):
                for a in authors:
                    if isinstance(a, str):
                        norm.append(a.strip())
                        group_only = False
                    elif isinstance(a, dict):
                        # new schema: person object or group
                        if a.get("group"):
                            display = a.get("display") or ""
                            if display:
                                norm.append(display)
                        else:
                            given = (a.get("given") or "").strip()
                            family = (a.get("family") or "").strip()
                            if given or family:
                                norm.append((given + " " + family).strip())
                                group_only = False
            if not norm:
                summary["empty_authors"] += 1
            else:
                ack_like, _ = detect_ack_like(norm)
                if ack_like:
                    summary["authors_ack_like"] += 1

        # DOI / Journal / Abstract
        doi = md.get("doi") or md.get("DOI")
        if is_blank(doi):
            summary["missing_doi"] += 1

        journal = md.get("journal") or md.get("journal_name") or md.get("venue")
        if is_blank(journal):
            summary["missing_journal"] += 1

        abstract = md.get("abstract") or md.get("abstract_text")
        if is_blank(abstract):
            summary["missing_abstract"] += 1

        # References
        if "references_text" in md:
            summary["has_references_text"] += 1
        if "references_struct" in md:
            summary["has_references_struct"] += 1
            rs = md.get("references_struct")
            if isinstance(rs, list) and len(rs) == 0:
                summary["empty_references_struct"] += 1

        # Row of issue codes for this file
        issues = []
        if is_blank(title): issues.append("META_TITLE_MISSING")
        if is_blank(year):
            issues.append("META_YEAR_MISSING")
        else:
            ys = str(year).strip()
            if not year_re.match(ys) and not isinstance(year, int):
                issues.append("YEAR_FORMAT_INVALID")
        if is_blank(doi): issues.append("META_DOI_MISSING")
        if is_blank(journal): issues.append("META_JOURNAL_MISSING")
        if is_blank(abstract): issues.append("ABSTRACT_MISSING")
        if authors is None:
            issues.append("AUTHORS_MISSING")
        elif is_blank(authors):
            issues.append("AUTHORS_EMPTY")
        else:
            # Build normalized list to check ack-like and group-only
            norm = []
            groups = 0
            total = 0
            if isinstance(authors, list):
                for a in authors:
                    total += 1
                    if isinstance(a, dict) and a.get("group"):
                        groups += 1
                        disp = a.get("display") or ""
                        if disp:
                            norm.append(disp)
                    elif isinstance(a, dict):
                        given = (a.get("given") or "").strip()
                        family = (a.get("family") or "").strip()
                        if given or family:
                            norm.append((given + " " + family).strip())
                    elif isinstance(a, str):
                        norm.append(a.strip())
            else:
                norm = [str(authors)]
            ack_like, _ = detect_ack_like(norm)
            if ack_like:
                issues.append("AUTHORS_ACK_LIKE")
            if total > 0 and groups == total:
                issues.append("AUTHORS_GROUP_ONLY")
        details_rows.append({
            "file": str(p),
            "issues": ",".join(issues) if issues else "",
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    # Write summary JSON
    (out_dir / "quality_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    # Write CSV of issues
    with (out_dir / "quality_issues.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "issues", "error"])
        w.writeheader()
        for row in details_rows:
            if "error" not in row:
                row["error"] = ""
            w.writerow(row)

    return summary


def main():
    ap = argparse.ArgumentParser(description="Audit extracted JSON quality.")
    ap.add_argument("input", nargs="?", default="out/batch_processed", help="Input directory")
    ap.add_argument("--out", default="out/reports", help="Output directory for reports")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of files for quick runs")
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.out)
    summary = audit_dir(in_dir, out_dir, args.limit)

    # Print succinct summary
    print("Audit complete. Summary:")
    for k in sorted(summary.keys()):
        print(f"  {k}: {summary[k]}")


if __name__ == "__main__":
    main()
