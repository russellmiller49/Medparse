# MedParse-Docling Architecture

## Overview

This document describes the modular architecture implemented for robust medical document processing with Docling 2.48+ compatibility.

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

#### `scripts/grobid_tei.py`
- Clean author extraction from TEI header only
- Handles name normalization (fixes run-on names)
- Extracts comprehensive metadata

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

#### `scripts/figures.py`
- OCR textuality scoring
- EXIF caption embedding
- Watermark filtering
- Caption-first indexing strategy

#### `scripts/ref_extract.py` & `scripts/ref_enrich.py`
- Reference extraction from GROBID TEI
- PubMed enrichment with fallbacks
- DOI → PMID resolution
- Title-based search fallback

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
   - Statistics (span-based)
   - Entities (UMLS/QuickUMLS/scispaCy)
   - Cross-references
   - Drugs & trial IDs
   ↓
6. Reference Enrichment (PubMed)
   ↓
7. Figure Processing (OCR, EXIF)
   ↓
8. Validation & Quality Assessment
   ↓
9. JSON Output
```

## Key Files

### Entry Points
- `bin/run_linkers.py`: Compare entity linkers
- `scripts/process_one_integrated.py`: Main integrated pipeline
- `test_pipeline.py`: Test harness

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

The pipeline validates:
- Metadata completeness (title, authors)
- Structure extraction (sections, tables, figures)
- Entity linking coverage
- Reference parsing and enrichment
- Text quality (ligature ratio < 0.1%)
- Cross-reference resolution

## Error Handling

- GROBID failures: Use Docling-only extraction
- UMLS unavailable: Fall back to QuickUMLS or scispaCy
- PubMed timeout: Return unenriched references
- OCR unavailable: Use caption-only indexing

## Performance Characteristics

- Docling: ~10-30s per PDF
- GROBID: ~5-10s per PDF
- Entity linking: 
  - UMLS API: ~1-2s per entity
  - QuickUMLS: ~0.1s per entity
  - scispaCy: ~0.5s per entity
- PubMed enrichment: ~0.5s per reference

## Future Enhancements

1. Multi-model entity linking ensemble
2. Abbreviation expansion with context
3. Section-specific entity linking rules
4. Citation context extraction
5. Table structure normalization
6. Chemical formula extraction
7. Dosage standardization