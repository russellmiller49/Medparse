Medparse End-to-End Pipeline

This document describes the clean, reproducible path from PDFs to enriched, hardened, deduplicated JSON with reports and provenance.

Inputs
- PDFs: put into `input/`
- Optional Zotero export: `out/zero/zero_export.json` (CSL‑JSON) and `out/zero/zero_export.csv` (CSV with Key and File Attachments). Overrides live in `out/zero/overrides.json`.

Key Outputs
- Extracted JSON: `out/batch_processed/*.json`
- Hardened/enriched JSON: `out/hardened/*.json`
- Reports: under `out/reports*` and final snapshot `out/reports_final/`

One‑Command Pipeline

1) Run the full flow (extract → merge Zotero → harden → enrich online → dedupe → final audit):

  make pipeline ZOTERO_JSON=out/zero/zero_export.json ZOTERO_CSV=out/zero/zero_export.csv EMAIL=you@example.com

2) Dry‑run for the metadata merge + enrichment (no writes to JSON):

  make pipeline-dry ZOTERO_JSON=out/zero/zero_export.json ZOTERO_CSV=out/zero/zero_export.csv EMAIL=you@example.com

Stage Details

Extract (PDF → JSON)
- Script: `batch_process_all.py` (uses `scripts/process_one.py` and Docling/GROBID stack configured in `config/docling_medical_config.yaml`).
- Output: `out/batch_processed/` per‑paper JSON including structure, references, assets, and initial metadata.

Audit (baseline)
- Script: `scripts/audit_extracted.py IN_DIR --out OUT_DIR`
- Validates presence of title/year/authors/doi/journal/abstract; emits per‑file issue codes and a summary JSON/CSV.

Merge Zotero (offline enrichment with provenance)
- Script: `scripts/apply_zotero_metadata.py --in IN_DIR --zotero-json CSL.json --zotero-csv CSV.csv --out OUT --report REPORT`
- Matching order: DOI → exact normalized title → fuzzy title → author+year. Supports `--overrides out/zero/overrides.json` and records changes to `provenance.patches` and `provenance.zotero`.

Hardening (offline, deterministic)
- Script: `scripts/harden_extracted.py IN_DIR --out OUT --front-matter-chars 6000 --save-fixlog`
- Fixes/normalizes: title (fallback to filename), year (normalize/derive), authors (filter/structure), DOI (front‑matter scan), journal (canonicalize synonyms), abstract (from early sections). Idempotent; patch provenance recorded.

Online Enrichment (Crossref, strict)
- Script: `scripts/enrich_online.py --in IN_DIR --out OUT --report REPORT --email you@example.com`
- Queries Crossref with strict acceptance; fills DOI/journal/vol/issue/pages/issn/url/year_norm; provenance `source="crossref"` with confidence.

Deduplicate (by DOI)
- Script: `scripts/dedupe_by_doi.py --in OUT --report out/reports/duplicates_by_doi.csv --apply`
- Writes removal detail report with original PDF basenames to `out/reports/duplicates_removed.csv` for mirrored PDF cleanup.

Final Audit
- Script: `scripts/audit_extracted.py out/hardened --out out/reports_final`
- Gates: in practice we target Authors empty=0; Titles 100%; Year 100%; DOI/Journals 100% (after online); Abstract coverage varies by extraction.

Manual Overrides (optional)
- File: `out/zero/overrides.json`
- Supports by‑filename entries of the form `{ "doi": "…", "year": 2000, "journal": "…", "volume": "…", "issue": "…", "pages": "…", "authors": ["Given Family", …] }`.
- Values are applied with `source="manual_patch"` in provenance.

Key Scripts (keep)
- Extraction: `scripts/process_one.py`, `scripts/grobid_*`, `scripts/docling_adapter.py`, linkers under `scripts/linking/` and `scripts/umls_*`.
- Quality and enrichment: `scripts/audit_extracted.py`, `scripts/apply_zotero_metadata.py`, `scripts/harden_extracted.py`, `scripts/enrich_online.py`, `scripts/dedupe_by_doi.py`, `scripts/report_missing_biblio.py`, and helpers in `scripts/util/`.

Legacy/Optional (retain for now)
- Reference‑specific enrichers (`scripts/ref_enrich.py`, `scripts/references_*`, `scripts/crossrefs.py`) and standalone fallbacks (`scripts/abstract_fallback.py`, `scripts/authors_fallback.py`). These are referenced by the extraction stage; do not delete unless the extraction code is refactored to depend solely on hardening.

Notes
- All changes to metadata are provenance‑logged under `provenance.patches` (op/path/from/to/source/confidence).
- Strict CI gates can be added by running merge with `--strict` and auditing `out/reports_final/quality_summary.json` thresholds.

