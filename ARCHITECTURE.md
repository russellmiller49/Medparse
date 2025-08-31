# MedParse-Docling Architecture

## Overview

This document describes the modular architecture implemented for robust medical document processing with Docling 2.48+ compatibility. The system provides two operational modes: standard extraction (main branch) and NLP-hardened extraction (feat/nlp-hardening-docling248 branch).

## Core Principles

1. **No Text Mutation**: All extraction operations preserve original text with character spans
2. **Modular Design**: Each component has a single responsibility
3. **Graceful Degradation**: Services fail gracefully when unavailable
4. **Clean Data Sources**: Authors from GROBID only, never from references

## Module Structure

### Data Adapters

#### `scripts/docling_adapter.py`
- Normalizes Docling output regardless of version changes
- Returns uniform structure: texts, figures, tables, sections
- Isolates Docling API changes to single module
- Handles .model_dump() for Docling 2.48+

#### `scripts/grobid_tei.py`
- Clean author extraction from TEI header only
- Handles name normalization (fixes run-on names)
- Extracts comprehensive metadata

#### `scripts/grobid_authors.py` (NEW)
- TEI-only author extraction
- Prevents reference/affiliation contamination
- Structured author objects with family/given/display/AMA formats

#### `scripts/grobid_references.py` (NEW)
- Parses TEI biblStruct to structured dicts
- Maintains both raw and structured references
- Enables synchronization between CSV and JSON

### Text Processing

#### `scripts/text_normalize.py`
- Fixes Unicode ligatures (ﬁ → fi, ﬀ → ff)
- Normalizes dashes and spaces
- Removes PDF extraction artifacts
- De-hyphenates line breaks
- **Never modifies source text** - creates normalized copies

### Entity Linking (`scripts/linking/`)

#### Components:
- `types.py`: Clinical TUI filtering (only relevant medical concepts)
- `scispacy_spans.py`: Entity span detection
- `umls_api.py`: UMLS API integration with caching
- `quickumls_fallback.py`: Local QuickUMLS for speed
- `linker_router.py`: Coordinates linking strategies

#### Strategy:
1. Primary: UMLS API (exact match)
2. Fallback: QuickUMLS (local, fast)
3. Span detection: scispaCy

### Extraction Modules

#### `scripts/stats_extractor.py`
- Span-based statistics extraction
- Detects: p-values, CIs, HRs, ORs, sample sizes
- Preserves character positions
- Never inserts inline expansions

#### `scripts/figures.py` & `scripts/figure_cropper.py`
- BOTTOMLEFT coordinate handling for Docling 2.48
- Watermark detection and filtering
- Caption extraction and figure labeling
- EXIF metadata embedding

#### `scripts/fig_ocr.py` (NLP Branch)
- OCR textuality scoring
- Conditional OCR for text-heavy figures
- Integrates with figure pipeline

#### `scripts/ref_extract.py` & `scripts/ref_enrich.py`
- Reference extraction from GROBID TEI
- PubMed enrichment with fallbacks
- DOI → PMID resolution
- Title-based search fallback

#### `scripts/ref_enricher.py` (NEW)
- Robust PubMed metadata enrichment
- Uses structured references as input
- Handles DOI conversion and title search
- Includes MeSH terms and abstracts

#### `scripts/crossrefs.py`
- Detects figure/table/citation references
- Preserves character spans
- Links to actual targets

### Validation

#### `scripts/validator.py`
- Comprehensive NLP-readiness checks
- Weighted scoring system
- Critical issues vs warnings
- Quality level assessment

## Pipeline Flow

### Main Branch Flow
```
1. PDF Input
   ↓
2. Docling (DocumentConverter) → Raw structure
   ↓
3. GROBID → TEI metadata & references
   ↓
4. Parse TEI → Structured authors & references
   ↓
5. Figure Extraction (with watermark filtering)
   ↓
6. Entity Linking (UMLS/QuickUMLS/scispaCy)
   ↓
7. Reference Enrichment (PubMed)
   ↓
8. Statistics & Cross-references
   ↓
9. Validation
   ↓
10. JSON + CSV Output
```

### NLP-Hardened Branch Flow
```
1. PDF Input
   ↓
2. Docling Adapter → Normalized structure
   ↓
3. GROBID → Clean metadata & references
   ↓
4. Text Normalization → NLP-ready copy (original preserved)
   ↓
5. Parallel Extraction:
   - Filtered Entity Linking (clinical TUIs only)
   - Statistics (span-based)
   - Cross-references
   - Drugs & trial IDs
   ↓
6. Reference Enrichment (PubMed)
   ↓
7. Figure Processing (OCR, EXIF)
   ↓
8. Enhanced Validation
   ↓
9. JSON Output
```

## Key Files

### Entry Points
- `scripts/process_one.py`: Main processing script (both branches)
- `scripts/process_one_integrated.py`: Integrated pipeline (NLP branch)
- `bin/run_linkers.py`: Comparative entity linker evaluation
- `scripts/run_batch.py`: Batch processing
- `test_pipeline.py`: Component testing
- `test_full_pipeline.py`: End-to-end testing with GROBID

### Configuration
- `.env`: API keys and service URLs
- Requirements: lxml, httpx, pillow, (optional: spacy, pytesseract)

## Usage Examples

```bash
# Compare entity linkers
python bin/run_linkers.py --pdf input/AMPLE2.pdf --compare

# Process with specific linker
python scripts/process_one_integrated.py input/AMPLE2.pdf --linker umls

# Test pipeline components
python test_pipeline.py
```

## Validation Metrics

### Standard Validation (Main Branch)
- Metadata completeness (title, authors)
- Structure extraction (sections, tables, figures)
- Entity presence (any linker)
- Reference extraction
- Cross-reference detection

### Enhanced Validation (NLP Branch)
- All standard checks plus:
- Structured reference validation
- Enrichment coverage (≥50% refs with PMIDs)
- Author contamination detection
- UMLS link quality (TUI filtering)
- Figure OCR text extraction
- Text normalization metrics

## Error Handling

- GROBID failures: Use Docling-only extraction
- UMLS unavailable: Fall back to QuickUMLS or scispaCy
- PubMed timeout: Return unenriched references
- OCR unavailable: Use caption-only indexing

## Performance Characteristics

- Docling: ~10-30s per PDF (faster with GPU)
- GROBID: ~5-10s per PDF
- Entity linking: 
  - UMLS API: ~1-2s per entity (with caching)
  - QuickUMLS: ~0.1s per entity (local)
  - scispaCy: ~0.5s per entity
- PubMed enrichment: ~0.5s per reference
- Figure extraction: ~0.1s per figure
- OCR (if enabled): ~1-2s per textual figure
- Full pipeline: ~60-90s per 10-page PDF

## Future Enhancements

1. Multi-model entity linking ensemble
2. Abbreviation expansion with context
3. Section-specific entity linking rules
4. Citation context extraction
5. Table structure normalization
6. Chemical formula extraction
7. Dosage standardization