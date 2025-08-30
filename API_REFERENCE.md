# MedParse-Docling API Reference

Complete API documentation for all modules and functions in the MedParse-Docling system.

## Core Processing Modules

### `scripts/process_one.py`

Main entry point for single PDF processing.

#### Functions

##### `process_pdf(pdf_path, out_json, cfg_path, linker)`
Process a single PDF through the complete pipeline.

**Parameters:**
- `pdf_path` (Path): Path to input PDF file
- `out_json` (Path): Path for output JSON file
- `cfg_path` (Path): Path to Docling configuration YAML
- `linker` (str): Entity linker choice ("umls", "scispacy", "quickumls")

**Returns:** None (writes to file)

**Example:**
```python
from pathlib import Path
from scripts.process_one import process_pdf

process_pdf(
    pdf_path=Path("input/paper.pdf"),
    out_json=Path("out/json_umls/paper.json"),
    cfg_path=Path("config/docling_medical_config.yaml"),
    linker="umls"
)
```

---

### `scripts/postprocess.py`

Document merging and enrichment functions.

#### Functions

##### `parse_grobid_metadata(tei_xml)`
Extract metadata from GROBID TEI XML output.

**Parameters:**
- `tei_xml` (str): TEI XML string from GROBID

**Returns:** Dict with structure:
```python
{
    "title": str,
    "year": str,
    "authors": List[Dict[str, str]],  # family, given, display, ama
    "references_text": List[str]
}
```

##### `merge_outputs(docling_json, grobid_meta, grobid_refs, umls_client, abbrev_map)`
Merge Docling and GROBID outputs with UMLS enrichment.

**Parameters:**
- `docling_json` (Dict): Docling extraction results
- `grobid_meta` (Dict): GROBID metadata
- `grobid_refs` (Dict): GROBID references
- `umls_client` (UMLSClient): UMLS API client instance
- `abbrev_map` (Dict[str, str]): Abbreviation expansions

**Returns:** Dict with merged and enriched document

##### `enrich_with_umls(doc, umls, abbrev_map)`
Add UMLS concept links to document.

**Parameters:**
- `doc` (Dict): Document structure
- `umls` (UMLSClient): UMLS client instance
- `abbrev_map` (Dict[str, str]): Abbreviation mappings

**Returns:** Dict with added `umls_links` field

##### `concat_text(doc, limit_chars=300000)`
Concatenate all text from document sections.

**Parameters:**
- `doc` (Dict): Document structure
- `limit_chars` (int): Maximum character limit

**Returns:** str of concatenated text

##### `extract_trial_ids(text)`
Extract clinical trial identifiers from text.

**Parameters:**
- `text` (str): Document text

**Returns:** List[str] of trial IDs (NCT, ISRCTN, EudraCT)

##### `resolve_cross_references(doc)`
Find and mark cross-references to figures and tables.

**Parameters:**
- `doc` (Dict): Document structure (modified in place)

**Returns:** None (modifies doc)

---

### `scripts/umls_linker.py`

UMLS API integration for medical concept linking.

#### Classes

##### `UMLSClient`
Client for UMLS REST API.

**Constructor:**
```python
UMLSClient(api_key: str, cache: Optional[CacheManager] = None)
```

**Methods:**

###### `search_term(term, max_results=10)`
Search UMLS for matching concepts.

**Parameters:**
- `term` (str): Search term
- `max_results` (int): Maximum results to return

**Returns:** List[Dict] with concept matches

###### `get_cui_info(cui)`
Get detailed information for a CUI.

**Parameters:**
- `cui` (str): Concept Unique Identifier

**Returns:** Dict with concept details

#### Functions

##### `normalize_terms(text, abbrev_map)`
Expand abbreviations in text.

**Parameters:**
- `text` (str): Input text
- `abbrev_map` (Dict[str, str]): Abbreviation mappings

**Returns:** str with expanded abbreviations

##### `link_umls_phrases(phrases, client)`
Link phrases to UMLS concepts.

**Parameters:**
- `phrases` (List[str]): Terms to link
- `client` (UMLSClient): UMLS client instance

**Returns:** List[Dict] with linked concepts:
```python
[{
    "phrase": str,
    "cui": str,
    "preferred": str,
    "source": "UMLS"
}]
```

---

### `scripts/local_linkers.py`

Local entity linking implementations.

#### Functions

##### `link_with_scispacy(text, model="en_core_sci_md")`
Link entities using scispaCy.

**Parameters:**
- `text` (str): Input text (max 500K chars)
- `model` (str): spaCy model name

**Returns:** List[Dict] with linked entities:
```python
[{
    "phrase": str,
    "cui": str,
    "preferred": str,
    "source": "scispaCy"
}]
```

##### `link_with_quickumls(text, quickumls_path=None)`
Link entities using QuickUMLS.

**Parameters:**
- `text` (str): Input text
- `quickumls_path` (Optional[str]): Path to QuickUMLS data

**Returns:** List[Dict] with linked entities:
```python
[{
    "phrase": str,
    "cui": str,
    "preferred": str,
    "source": "QuickUMLS"
}]
```

---

## Client Modules

### `scripts/grobid_client.py`

GROBID service client for bibliographic extraction.

#### Classes

##### `Grobid`
HTTP client for GROBID service.

**Constructor:**
```python
Grobid(url="http://localhost:8070", timeout=90)
```

**Methods:**

###### `process_fulltext(pdf_path)`
Process complete PDF document.

**Parameters:**
- `pdf_path` (str): Path to PDF file

**Returns:** Dict with `tei_xml` key

###### `process_biblio(pdf_path)`
Extract only references from PDF.

**Parameters:**
- `pdf_path` (str): Path to PDF file

**Returns:** Dict with `references_tei` key

---

### `scripts/ncbi_client.py`

NCBI E-utilities client for PubMed queries.

#### Classes

##### `NCBIClient`
Client for NCBI E-utilities API.

**Constructor:**
```python
NCBIClient(api_key: str, email: Optional[str] = None, 
          tool: str = "medparse-docling", timeout: int = 30)
```

**Methods:**

###### `esearch_pubmed(term, retmax=3)`
Search PubMed database.

**Parameters:**
- `term` (str): Search query
- `retmax` (int): Maximum results

**Returns:** str of XML response

###### `efetch_pubmed(pmids)`
Fetch PubMed records by ID.

**Parameters:**
- `pmids` (str): Comma-separated PMIDs

**Returns:** str of XML response

---

## Extraction Modules

### `scripts/stats_extractor.py`

Statistical information extraction.

#### Functions

##### `extract_statistics(text)`
Extract statistical values from text.

**Parameters:**
- `text` (str): Input text

**Returns:** List[Dict] with statistics:
```python
[{
    "type": str,  # p_value, confidence_interval, etc.
    "value": Union[float, str],
    "context": str
}]
```

**Supported types:**
- `p_value`: p-values (p<0.05, p=0.001)
- `confidence_interval`: CI ranges (95% CI [1.2-3.4])
- `hazard_ratio`: HR values
- `odds_ratio`: OR values
- `relative_risk`: RR values
- `sample_size`: n values

---

### `scripts/drug_extractor.py`

Pharmaceutical information extraction.

#### Functions

##### `extract_drugs_dosages(text)`
Extract drug names and dosages.

**Parameters:**
- `text` (str): Input text

**Returns:** List[Dict] with drugs:
```python
[{
    "drug": str,
    "dosage": Optional[str],
    "frequency": Optional[str],
    "route": Optional[str]
}]
```

---

### `scripts/section_classifier.py`

Section categorization for medical documents.

#### Functions

##### `classify_section(title)`
Classify section by title.

**Parameters:**
- `title` (str): Section title

**Returns:** str category from:
- `introduction`
- `methods`
- `results`
- `discussion`
- `conclusion`
- `abstract`
- `references`
- `supplementary`
- `other`

---

### `scripts/figure_cropper.py`

Figure extraction and processing.

#### Functions

##### `crop_figures(pdf_path, docling_doc, output_dir)`
Extract and save figure images from PDF.

**Parameters:**
- `pdf_path` (Path): Input PDF path
- `docling_doc` (Dict): Docling extraction results
- `output_dir` (Path): Output directory for images

**Returns:** Dict with statistics:
```python
{
    "n_saved": int,
    "n_missing_bbox": int,
    "saved_files": List[str]
}
```

**Output format:** JPEG images with EXIF captions

---

## Reference Processing

### `scripts/references_csv.py`

Reference formatting in AMA style.

#### Functions

##### `write_references_csv(tei_xml, output_path)`
Convert GROBID references to AMA CSV.

**Parameters:**
- `tei_xml` (str): GROBID references TEI
- `output_path` (Path): Output CSV path

**Returns:** int count of references written

**CSV columns:**
- `authors`: AMA formatted author list
- `title`: Article title
- `journal`: Journal name
- `year`: Publication year
- `volume`: Volume number
- `pages`: Page range
- `doi`: Digital Object Identifier

---

### `scripts/references_enricher.py`

PubMed enrichment for references.

#### Functions

##### `extract_ref_items(tei_xml)`
Parse reference items from TEI XML.

**Parameters:**
- `tei_xml` (str): GROBID TEI XML

**Returns:** List[Dict] with reference items

##### `enrich_items_with_ncbi(items, ncbi, cache=None)`
Add PubMed metadata to references.

**Parameters:**
- `items` (List[Dict]): Reference items
- `ncbi` (NCBIClient): NCBI client instance
- `cache` (Optional[CacheManager]): Cache instance

**Returns:** List[Dict] with added `hits` field containing PubMed data

---

## Utility Modules

### `scripts/cache_manager.py`

Persistent caching system.

#### Classes

##### `CacheManager`
File-based cache using pickle.

**Constructor:**
```python
CacheManager(cache_dir: Path = Path("cache"))
```

**Methods:**

###### `get(key)`
Retrieve cached value.

**Parameters:**
- `key` (str): Cache key

**Returns:** Optional[Any] cached value or None

###### `set(key, value)`
Store value in cache.

**Parameters:**
- `key` (str): Cache key
- `value` (Any): Value to cache

**Returns:** None

###### `cache_umls_lookup(term, result)`
Cache UMLS lookup result.

**Parameters:**
- `term` (str): Search term
- `result` (Dict): UMLS result

**Returns:** None

###### `get_umls_lookup(term)`
Retrieve cached UMLS result.

**Parameters:**
- `term` (str): Search term

**Returns:** Optional[Dict] cached result

---

### `scripts/validator.py`

Quality assurance and validation.

#### Functions

##### `validate_extraction(doc)`
Validate extraction completeness.

**Parameters:**
- `doc` (Dict): Document structure

**Returns:** Dict with validation results:
```python
{
    "validations": Dict[str, bool],  # Individual checks
    "completeness_score": int,       # 0-100 score
    "issues": List[str],             # Problems found
    "is_valid": bool                 # Overall validity
}
```

**Validation checks:**
- `has_title`: Title extracted
- `has_authors`: Authors found
- `authors_are_objects`: Authors properly structured
- `has_sections`: Sections extracted
- `tables_have_headers`: Tables have headers
- `figures_have_captions`: Figures have captions
- `references_parsed`: References found
- `umls_links_found`: UMLS concepts linked

---

### `scripts/qa_logger.py`

Quality assurance reporting.

#### Functions

##### `write_qa(qa_dir, stem, qa_data)`
Write QA report to JSON file.

**Parameters:**
- `qa_dir` (Path): Output directory
- `stem` (str): File stem name
- `qa_data` (Dict): QA metrics

**Returns:** None

**QA data structure:**
```python
{
    "pdf": str,
    "n_sections": int,
    "n_tables": int,
    "n_figures": int,
    "n_fig_crops": int,
    "missing_fig_bbox": int,
    "n_refs_csv": int,
    "n_umls_links": int,
    "n_local_links": int,
    "linker": str,
    "completeness_score": int,
    "is_valid": bool
}
```

---

### `scripts/table_normalizer.py`

Table structure normalization.

#### Functions

##### `normalize_table(table)`
Normalize table structure for consistency.

**Parameters:**
- `table` (Dict): Table structure (modified in place)

**Returns:** None

**Normalization:**
- Ensures consistent headers
- Aligns row/column counts
- Handles merged cells
- Cleans empty cells

---

### `scripts/env_loader.py`

Environment configuration loader.

#### Functions

##### `load_env()`
Load environment variables from .env file.

**Parameters:** None

**Returns:** Dict with environment variables:
```python
{
    "UMLS_API_KEY": Optional[str],
    "NCBI_API_KEY": Optional[str],
    "NCBI_EMAIL": Optional[str],
    "GROBID_URL": str,  # defaults to http://localhost:8070
    "QUICKUMLS_PATH": Optional[str]
}
```

---

### `scripts/utils.py`

General utility functions.

#### Functions

##### `robust_api_call(max_attempts=3)`
Decorator for retry logic on API calls.

**Parameters:**
- `max_attempts` (int): Maximum retry attempts

**Returns:** Decorated function with exponential backoff

**Example:**
```python
@robust_api_call()
def api_function():
    # API call that might fail
    pass
```

---

## Batch Processing

### `scripts/run_batch.py`

Batch processing for multiple PDFs.

#### Functions

##### `main(inp="input", out_root="out", linker="umls")`
Process all PDFs in directory.

**Parameters:**
- `inp` (str): Input directory path
- `out_root` (str): Output root directory
- `linker` (str): Entity linker choice

**Returns:** None

**Output structure:**
```
out_root/
├── json_{linker}/   # JSON outputs
├── figures/         # Figure images
├── references/      # Reference CSVs
└── qa/             # QA reports
```

---

### `scripts/compare_linkers.py`

Compare results across different entity linkers.

#### Functions

##### `compare(stem, out_root="out")`
Compare single paper across linkers.

**Parameters:**
- `stem` (str): Paper filename stem
- `out_root` (str): Output directory root

**Returns:** None (prints comparison)

##### `main(stems, out_root="out")`
Compare multiple papers.

**Parameters:**
- `stems` (List[str]): Paper filename stems
- `out_root` (str): Output directory root

**Returns:** None (prints comparisons)

**Output format:**
```
== paper_stem ==
Title: Paper Title
UMLS: links=125 local=0 score=88
scispaCy: links=0 local=89 score=75
QuickUMLS: links=0 local=103 score=75
```

---

## Configuration Files

### `config/docling_medical_config.yaml`
Docling pipeline configuration.

**Structure:**
```yaml
pipeline:
  - extractor.pdf_text
  - extractor.pdf_layout
  - enrich.sections
  - enrich.tables:
      mode: hybrid
      output_format: json
  - enrich.figures:
      include_bboxes: true
options:
  normalize_unicode: true
  language: en
```

### `config/abbreviations_med.json`
Medical abbreviation expansions.

**Structure:**
```json
{
  "COPD": "Chronic obstructive pulmonary disease",
  "HR": "Hazard ratio"
}
```

---

## Environment Variables

### Required
- `UMLS_API_KEY`: UMLS REST API key
- `GROBID_URL`: GROBID service URL (default: http://localhost:8070)

### Optional
- `NCBI_API_KEY`: NCBI E-utilities API key
- `NCBI_EMAIL`: Email for NCBI API
- `QUICKUMLS_PATH`: Path to QuickUMLS data directory

---

## Error Handling

All API functions use the `@robust_api_call()` decorator for automatic retry with exponential backoff. Network errors and temporary failures are retried up to 3 times.

### Exception Types
- `FileNotFoundError`: Invalid PDF path
- `ConnectionError`: GROBID/API connection failed
- `ValueError`: Invalid linker choice
- `KeyError`: Missing required configuration

### Logging
Uses `loguru` for structured logging:
- `DEBUG`: Detailed processing steps
- `INFO`: Normal operation messages
- `WARNING`: Validation issues, fallbacks
- `ERROR`: Processing failures
- `SUCCESS`: Completion messages