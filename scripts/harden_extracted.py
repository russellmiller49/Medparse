#!/usr/bin/env python3
import argparse
import json
import re
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

# Ensure project root on sys.path for local imports
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.util import sections as USections  # type: ignore
from scripts.util import name_utils as UNames  # type: ignore
from scripts.util import dois as UDois  # type: ignore
from scripts.util.provenance import add_patch  # type: ignore

YEAR_RE = re.compile(r"^\d{4}(?:-(?:0[1-9]|1[0-2]))?(?:-(?:0[1-9]|[12]\d|3[01]))?$")
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)


def is_blank(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, str):
        return not x.strip()
    if isinstance(x, (list, dict)):
        return len(x) == 0
    return False


def blank_or_invalid_year(year: Any) -> bool:
    if is_blank(year):
        return True
    return not YEAR_RE.match(str(year).strip())


def normalize_ws(s: str | None) -> str | None:
    if s is None:
        return None
    return re.sub(r"\s+", " ", s).strip()


def parse_year_from_filename(stem: str) -> str | None:
    m = re.search(r"(19|20)\d{2}", stem)
    return m.group(0) if m else None

def extract_authors_from_metadata(authors_field: Any) -> list[str]:
    names: list[str] = []
    if authors_field is None:
        return names
    if isinstance(authors_field, str):
        candidates = [a.strip() for a in authors_field.split(";") if a.strip()]
    elif isinstance(authors_field, list):
        candidates = []
        for a in authors_field:
            if isinstance(a, str):
                candidates.append(a.strip())
            elif isinstance(a, dict):
                nm = a.get("name") or a.get("full_name") or a.get("surname") or a.get("display") or ""
                if nm:
                    candidates.append(str(nm).strip())
    else:
        candidates = []

    # filter contributions/ack lines
    for c in candidates:
        if not c:
            continue
        if UNames.is_ack_like(c):
            continue
        names.append(c)
    # de-dup preserve order
    seen = set()
    out: List[str] = []
    for n in names:
        k = n.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(n)
    return out


def looks_like_name(token: str) -> bool:
    token = token.strip()
    if not token:
        return False
    # strip footnote numbers/symbols
    token = re.sub(r"[\d\*\u2020\u2021\+\-\^]+", "", token).strip()
    # simple heuristic: 2+ words, initial caps
    parts = [p for p in token.split() if p]
    if len(parts) < 2 or len(parts) > 6:
        return False
    caps = sum(1 for p in parts if re.match(r"[A-Z][A-Za-z\-\']+", p))
    return caps >= max(2, len(parts) - 1)


def extract_authors_from_sections(structure: dict) -> list[str]:
    sections = (structure or {}).get("sections") or []
    # Look into first few sections for a title listing authors
    for sec in sections[:5]:
        title = normalize_ws(sec.get("title") if isinstance(sec, dict) else None)
        if not title:
            continue
        # split by commas or ';'
        tokens = re.split(r",|;|\band\b|&", title)
        candidates = [t.strip() for t in tokens if t.strip()]
        names = [t for t in candidates if looks_like_name(t)]
        if len(names) >= 1:
            # clean digits and footnote markers
            cleaned = [re.sub(r"\s*\d+[\d,\s]*$", "", n).strip() for n in names]
            # de-dup
            out = []
            seen = set()
            for n in cleaned:
                k = n.lower()
                if k not in seen:
                    seen.add(k)
                    out.append(n)
            return out
        # try within first paragraph text if title not suitable
        paras = (sec.get("paragraphs") or []) if isinstance(sec, dict) else []
        for para in paras[:2]:
            txt = normalize_ws(para.get("text") if isinstance(para, dict) else str(para)) or ""
            if not txt:
                continue
            # avoid obvious non-author lines
            if re.search(r"^\d+\s|^department|^introduction|^abstract|^background", txt, re.I):
                continue
            tokens = re.split(r",|;|\band\b|&", txt)
            candidates = [t.strip() for t in tokens if t.strip()]
            names = [t for t in candidates if looks_like_name(t)]
            if len(names) >= 2:
                cleaned = [re.sub(r"\s*\d+[\d,\s]*$", "", n).strip() for n in names]
                out = []
                seen = set()
                for n in cleaned:
                    k = n.lower()
                    if k not in seen:
                        seen.add(k)
                        out.append(n)
                if out:
                    return out
    return []


def extract_abstract_from_structure(structure: dict) -> str | None:
    return USections.find_abstract(structure)


def extract_doi_from_front_sections(obj: dict, front_chars: int) -> str | None:
    # 1) metadata direct fields first
    md = obj.get("metadata") or {}
    for k in ("doi", "DOI", "doi_url"):
        v = md.get(k)
        if isinstance(v, str):
            m = DOI_RE.search(v)
            if m:
                return m.group(0)

    # 2) Build a front-matter text from early sections and paragraphs
    s = obj.get("structure") or {}
    secs = s.get("sections") or []
    front_titles_stop = re.compile(r"^references|^bibliography|^works cited", re.I)
    text_parts: List[str] = []
    for sec in secs[:10]:
        title = (sec.get("title") or "").strip()
        if front_titles_stop.search(title):
            break
        paras = sec.get("paragraphs") or [] if isinstance(sec, dict) else []
        for para in paras[:5]:
            txt = para.get("text") if isinstance(para, dict) else str(para)
            if isinstance(txt, str) and txt:
                text_parts.append(txt)
        if sum(len(t) for t in text_parts) >= front_chars:
            break
    blob = re.sub(r"\s+", " ", "\n".join(text_parts))[:front_chars]
    cands = UDois.extract_candidate_dois(blob)
    return cands[0] if cands else None


@dataclass
class FixResult:
    changed: bool
    fixes: list[dict]
    new_obj: dict


def harden_one(p: Path, front_chars: int, provenance_level: str = "summary", save_fixlog: bool = False) -> FixResult | None:
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

    md = obj.get("metadata")
    if not isinstance(md, dict):
        return FixResult(False, [], obj)

    new_obj = deepcopy(obj)
    new_md = new_obj.setdefault("metadata", {})
    fixes: list[dict] = []

    # Title from filename fallback
    if is_blank(new_md.get("title")):
        title = re.sub(r"[_\-]+", " ", p.stem).strip().title()
        fixes.append({"field": "title", "action": "fallback:filename", "new": title})
        new_md["title"] = title
        add_patch(new_obj, "metadata.title", None, title, source="fallback:filename")

    # Year validation and fallback from filename
    year = new_md.get("year")
    norm_res = USections.normalize_year(new_md)
    if norm_res.get("changed"):
        fixes.append({"field": "year", "action": norm_res.get("source", "normalize:iso"), "old": year, "new": new_md.get("year")})
        add_patch(new_obj, "metadata.year", year, new_md.get("year"), source=norm_res.get("source", "normalize:iso"))
    if is_blank(new_md.get("year")):
        fn_year = parse_year_from_filename(p.stem)
        if fn_year:
            old = new_md.get("year")
            new_md["year"] = int(fn_year)
            fixes.append({"field": "year", "action": "fallback:filename", "old": old, "new": int(fn_year)})
            add_patch(new_obj, "metadata.year", old, int(fn_year), source="fallback:filename")
        else:
            # last resort: if Zotero provided year_norm, promote to year
            yn = new_md.get("year_norm")
            try:
                if yn is not None:
                    yi = int(str(yn)[:4])
                    old = new_md.get("year")
                    new_md["year"] = yi
                    fixes.append({"field": "year", "action": "from_year_norm", "old": old, "new": yi})
                    add_patch(new_obj, "metadata.year", old, yi, source="from_year_norm")
            except Exception:
                pass

    # Authors cleaning and fallback from sections
    def to_author_objs(tokens: List[str]) -> List[dict]:
        out = []
        for t in tokens:
            cls = UNames.classify_entry(t)
            if cls.get("drop"):
                continue
            if cls.get("group"):
                out.append({"given": "", "family": "", "suffix": None, "degrees": [], "group": True, "display": t})
                continue
            person = UNames.to_person(t)
            if person:
                person.setdefault("group", False)
                out.append(person)
        # de-dup by display or given+family
        seen = set()
        dedup = []
        for a in out:
            key = (a.get("display") or f"{a.get('given','')}|{a.get('family','')}").lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(a)
        return dedup

    author_tokens = extract_authors_from_metadata(new_md.get("authors"))
    author_objs: List[dict] = []
    if author_tokens:
        author_objs = to_author_objs(author_tokens)
    if not author_objs:
        # try section title line
        line = USections.find_author_title_line(new_obj.get("structure") or {})
        if line:
            tokens = [t for t in re.split(r",|;|\band\b|&", line) if t and t.strip()]
            author_objs = to_author_objs([t.strip() for t in tokens])
            if author_objs:
                fixes.append({"field": "authors", "action": "from_sections", "new": [a.get("display") or f"{a.get('given')} {a.get('family')}" for a in author_objs]})
                add_patch(new_obj, "metadata.authors", new_md.get("authors"), author_objs, source="from_sections")
                new_md["authors"] = author_objs
    else:
        # replace with structured objects
        fixes.append({"field": "authors", "action": "filtered_ack_like", "old": new_md.get("authors"), "new": [a.get("display") or f"{a.get('given')} {a.get('family')}" for a in author_objs]})
        add_patch(new_obj, "metadata.authors", new_md.get("authors"), author_objs, source="filtered_ack_like")
        new_md["authors"] = author_objs

    # DOI normalization (best-effort)
    doi = new_md.get("doi") or new_md.get("DOI")
    if is_blank(doi):
        found = extract_doi_from_front_sections(new_obj, front_chars)
        if found:
            fixes.append({
                "field": "doi",
                "action": "front_matter_scan",
                "new": found,
            })
            new_md["doi"] = found
            add_patch(new_obj, "metadata.doi", None, found, source="front_matter_scan")
    else:
        m = DOI_RE.search(str(doi))
        if m and m.group(0) != doi:
            fixes.append({
                "field": "doi",
                "action": "normalize_extract",
                "old": doi,
                "new": m.group(0),
            })
            new_md["doi"] = m.group(0)
            add_patch(new_obj, "metadata.doi", doi, m.group(0), source="normalize_extract")

    # Journal canonicalization from synonyms (if ever present)
    journal = new_md.get("journal_full") or new_md.get("journal") or new_md.get("journal_name") or new_md.get("venue") or new_md.get("source") or new_md.get("container-title")
    if journal:
        if new_md.get("journal_full") != journal:
            fixes.append({"field": "journal_full", "action": "canonicalize", "old": new_md.get("journal_full"), "new": journal})
            add_patch(new_obj, "metadata.journal_full", new_md.get("journal_full"), journal, source="canonicalize")
            new_md["journal_full"] = journal

    # Abstract from structure if missing
    if is_blank(new_md.get("abstract")):
        abstract = extract_abstract_from_structure(new_obj.get("structure") or {})
        if abstract:
            fixes.append({
                "field": "abstract",
                "action": "from_structure",
                "new": abstract[:120] + ("…" if len(abstract) > 120 else ""),
            })
            new_md["abstract"] = abstract
            add_patch(new_obj, "metadata.abstract", None, abstract[:2000], source="from_structure")

    # Record fixes in provenance.patches (already added per change)
    changed = len(fixes) > 0
    if changed and save_fixlog:
        validation = new_obj.setdefault("validation", {})
        hard = validation.setdefault("hardening", {})
        log = hard.setdefault("fixes", [])
        log.extend(fixes)

    return FixResult(changed, fixes, new_obj)


def main():
    ap = argparse.ArgumentParser(description="Harden extracted JSON metadata with offline heuristics.")
    ap.add_argument("input", nargs="?", default="out/batch_processed", help="Input directory")
    ap.add_argument("--out", default="out/hardened", help="Output directory for hardened JSONs")
    ap.add_argument("--dry-run", action="store_true", help="Do not write output files; write report only")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of files for quick runs")
    ap.add_argument("--enrich", choices=["offline", "online"], default="offline", help="Enrichment mode (default offline)")
    ap.add_argument("--max-workers", type=int, default=6, help="Max workers (unused placeholder)")
    ap.add_argument("--front-matter-chars", type=int, default=6000, help="Chars to scan in front matter for DOI")
    ap.add_argument("--save-fixlog", action="store_true", help="Persist fix details under validation.hardening")
    ap.add_argument("--provenance-level", choices=["summary", "full"], default="summary", help="Provenance detail level")
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.out)
    report_dir = Path("out/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in in_dir.rglob("*.json") if p.name != "processing_report.json")
    if args.limit:
        files = files[: args.limit]

    changed_count = 0
    nochange_count = 0
    errors = 0
    report_rows = []

    for p in files:
        res = harden_one(p, front_chars=args.__dict__.get("front_matter_chars", 6000), provenance_level=args.provenance_level, save_fixlog=args.save_fixlog)
        if res is None:
            errors += 1
            report_rows.append({"file": str(p), "status": "error"})
            continue
        if res.changed:
            changed_count += 1
            # write file if not dry-run
            if not args.dry_run:
                target = out_dir / p.name
                target.write_text(json.dumps(res.new_obj, ensure_ascii=False, indent=2), encoding="utf-8")
            # capture diff summary
            diff = {}
            for f in res.fixes:
                field = f.get("field")
                diff[field] = {
                    k: f.get(k) for k in ("action", "old", "new") if k in f
                }
            report_rows.append({
                "file": str(p),
                "status": "changed" if not args.dry_run else "dry-run",
                "changes": json.dumps(diff, ensure_ascii=False),
            })
        else:
            nochange_count += 1
            report_rows.append({"file": str(p), "status": "unchanged"})

    # Write report CSV
    import csv

    with (report_dir / ("hardening_dry_run.csv" if args.dry_run else "hardening_changes.csv")).open(
        "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.DictWriter(f, fieldnames=["file", "status", "changes"])
        w.writeheader()
        for row in report_rows:
            if "changes" not in row:
                row["changes"] = ""
            w.writerow(row)

    summary = {
        "input_files": len(files),
        "changed": changed_count,
        "unchanged": nochange_count,
        "errors": errors,
        "output_dir": str(out_dir),
        "dry_run": bool(args.dry_run),
    }
    (report_dir / "hardening_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("Hardening complete.")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
