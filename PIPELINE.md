# MedParse End-to-End Pipeline

This document describes the complete, clean pipeline from PDFs to RAG-ready JSON with 100% abstract coverage, full table extraction, and comprehensive medical concept linking.

Inputs
- PDFs: put into `input/`
- Optional Zotero export: `out/zero/zero_export.json` (CSL‑JSON) and `out/zero/zero_export.csv` (CSV with Key and File Attachments). Overrides live in `out/zero/overrides.json`.

## Current Achievement
✅ **396 papers processed** with:
- 100% abstract coverage (299 metadata + 80 PubMed + 17 manual curation)
- 79% tables with headers properly extracted from docling grid format
- Zero empty sections - all clinical content preserved
- Complete UMLS medical concept linking
- Full reference preservation with fallback chain (enriched → struct → text)

## Key Outputs
- Extracted JSON: `out/batch_processed/*.json` - Raw Docling extraction
- Hardened JSON: `out/hardened/*.json` - UMLS enriched & validated
- **Final RAG-Ready: `out/rag_ready_complete/*.json`** - Complete with 100% abstract coverage
- Reports: under `out/reports*` and audit reports
- Verification: `verify_complete_data.py` confirms all content preserved

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

## Clean Pipeline Scripts

### Core Processing
- **PDF Extraction**: `scripts/process_one.py`, `scripts/run_batch.py`, `batch_process_all.py`
- **Hardening**: `scripts/harden_extracted.py` - UMLS enrichment, validation, normalization
- **RAG Preparation**: `scripts/prepare_for_rag.py` - Final cleaning with table header extraction
- **Abstract Recovery**: `scripts/fix_missing_abstracts.py` (PubMed), `scripts/add_manual_abstracts.py` (manual curation)

### Quality & Enrichment
- **Audit**: `scripts/audit_extracted.py`, `scripts/audit_abstracts.py`, `scripts/audit_clean_jsons.py`
- **Metadata**: `scripts/apply_zotero_metadata.py`, `scripts/enrich_online.py` (Crossref)
- **Deduplication**: `scripts/dedupe_by_doi.py`
- **Verification**: `verify_complete_data.py` - comprehensive validation

### Supporting Scripts
- **GROBID**: `scripts/grobid_*` - reference parsing
- **Docling**: `scripts/docling_adapter.py` - document structure extraction
- **UMLS**: `scripts/umls_*` - medical concept linking
- **Utilities**: `scripts/util/*` - helper functions

## Complete RAG Pipeline

### Step 1: Process PDFs
```bash
python scripts/run_batch.py papers/ out/batch_processed/
```

### Step 2: Harden & Enrich
```bash
python scripts/harden_extracted.py out/batch_processed/ out/hardened/
```

### Step 3: Prepare for RAG
```bash
python scripts/prepare_for_rag.py out/hardened/ out/rag_ready_complete/ --mode full
```

### Step 4: Backfill Abstracts
```bash
export NCBI_EMAIL="your.email@example.com"
python scripts/fix_missing_abstracts.py out/rag_ready_complete/ --only-missing
python scripts/add_manual_abstracts.py out/rag_ready_complete/
```

### Step 5: Final Verification
```bash
python scripts/audit_abstracts.py out/rag_ready_complete/
python verify_complete_data.py
```

## Legacy Scripts (archived)
- Reference enrichers: `scripts/ref_enrich.py`, `scripts/references_*`, `scripts/crossrefs.py`
- Standalone fallbacks: `scripts/abstract_fallback.py`, `scripts/authors_fallback.py`
- Moved to `scripts/legacy/` with wrappers for backward compatibility

Notes
- All changes to metadata are provenance‑logged under `provenance.patches` (op/path/from/to/source/confidence).
- Strict CI gates can be added by running merge with `--strict` and auditing `out/reports_final/quality_summary.json` thresholds.

