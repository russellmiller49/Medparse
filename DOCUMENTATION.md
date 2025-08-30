# MedParse-Docling Technical Documentation

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Component Details](#component-details)
3. [Data Flow](#data-flow)
4. [Module Reference](#module-reference)
5. [Configuration](#configuration)
6. [API Integrations](#api-integrations)
7. [Data Schemas](#data-schemas)
8. [Performance Considerations](#performance-considerations)
9. [Extension Points](#extension-points)

## System Architecture

### Overview
MedParse-Docling is a multi-stage medical document processing pipeline that combines:
- **Docling**: IBM's document understanding library for structure extraction
- **GROBID**: Machine learning library for bibliographic data extraction
- **UMLS/scispaCy/QuickUMLS**: Medical entity linking systems
- **Custom Enrichers**: Statistical, pharmaceutical, and clinical trial extractors

### Pipeline Stages

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   PDF Input │────▶│   Docling    │────▶│    GROBID    │
└─────────────┘     └──────────────┘     └──────────────┘
                           │                      │
                    Structure Data         Metadata & Refs
                           │                      │
                           ▼                      ▼
                    ┌──────────────────────────────┐
                    │      Merge & Normalize       │
                    └──────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     Entity Linking Layer      │
                    │  (UMLS/scispaCy/QuickUMLS)   │
                    └──────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     Enrichment Pipeline       │
                    │  • Statistics Extraction      │
                    │  • Drug/Dosage Detection      │
                    │  • Clinical Trial IDs         │
                    │  • Reference Enhancement      │
                    │  • Section Classification     │
                    └──────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   Validation & QA Layer       │
                    └──────────────────────────────┘
                                   │
                                   ▼
                           JSON Output + Assets
```

## Component Details

### 1. Document Parsing Layer

#### Docling Component
- **Purpose**: Extract document structure (sections, tables, figures)
- **Configuration**: `config/docling_medical_config.yaml`
- **Key Features**:
  - Hybrid table extraction
  - Figure boundary detection
  - Section hierarchy preservation
  - Citation linking

#### GROBID Component
- **Purpose**: Extract bibliographic metadata and references
- **Endpoints Used**:
  - `/api/processFulltextDocument`: Full paper analysis
  - `/api/processReferences`: Reference extraction
- **Output**: TEI XML format
- **Key Extractions**:
  - Authors with affiliations
  - Publication metadata
  - Structured references
  - Abstract sections

### 2. Entity Linking Layer

#### UMLS Linker (Online)
- **API**: UMLS REST API
- **Authentication**: API key required
- **Features**:
  - CUI (Concept Unique Identifier) resolution
  - Preferred term retrieval
  - Semantic type filtering
  - Multi-source vocabulary (SNOMEDCT, RXNORM, MSH)

#### scispaCy Linker (Local)
- **Model**: `en_core_sci_md`
- **Components**:
  - NER (Named Entity Recognition)
  - Abbreviation detection
  - UMLS entity linking
- **Processing**: 500K character limit per document

#### QuickUMLS Linker (Local)
- **Algorithm**: Approximate string matching
- **Similarity**: Jaccard coefficient (threshold: 0.9)
- **Mode**: Best match selection
- **Index**: Pre-built from UMLS Metathesaurus

### 3. Enrichment Pipeline

#### Statistics Extractor
```python
Patterns detected:
- p-values: p < 0.05, p=0.001
- Confidence intervals: 95% CI [1.2-3.4]
- Hazard ratios: HR 2.3 (95% CI 1.5-3.1)
- Odds ratios: OR 1.8 (1.2-2.7)
- Relative risk: RR 1.5 (1.1-2.0)
- Sample sizes: n=250, N=1000
```

#### Drug/Dosage Extractor
```python
Extraction patterns:
- Drug + dosage: "aspirin 100mg"
- Drug + frequency: "metformin twice daily"
- Complex regimens: "5mg/kg every 8 hours"
```

#### Clinical Trial ID Extractor
```python
Supported formats:
- NCT IDs: NCT12345678
- ISRCTN: ISRCTN12345678
- EudraCT: 2004-123456-12
```

### 4. Output Generation

#### Figure Cropper
- **Format**: JPEG with quality 95
- **Metadata**: EXIF caption embedding
- **Naming**: `{paper}_fig_{index:03d}.jpg`

#### Reference Formatter
- **Style**: AMA (American Medical Association)
- **Output**: CSV with structured fields
- **Enrichment**: PubMed metadata via NCBI API

## Data Flow

### Input Processing
```python
PDF → bytes → DocumentConverter → dict
    → bytes → GROBID client → TEI XML
```

### Merge Strategy
```python
1. Parse Docling structure (sections, tables, figures)
2. Parse GROBID metadata (title, authors, year)
3. Normalize text with abbreviation expansion
4. Apply entity linking based on selected pipeline
5. Enrich with statistics, drugs, trials
6. Validate completeness
7. Generate QA metrics
```

### Caching Strategy
```python
Cache key generation:
- UMLS lookups: MD5(term)
- NCBI searches: MD5(query)
- File storage: pickle serialization
- TTL: Indefinite (manual cache clearing)
```

## Module Reference

### Core Modules

#### `process_one.py`
Main entry point for single PDF processing.
```python
def process_pdf(
    pdf_path: Path,
    out_json: Path,
    cfg_path: Path,
    linker: str  # "umls" | "scispacy" | "quickumls"
) -> None
```

#### `postprocess.py`
Document merging and enrichment functions.
```python
def parse_grobid_metadata(tei_xml: str) -> Dict[str, Any]
def merge_outputs(docling_json: Dict, grobid_meta: Dict, 
                  grobid_refs: Dict, umls_client: UMLSClient,
                  abbrev_map: Dict[str,str]) -> Dict
def enrich_with_umls(doc: Dict, umls: UMLSClient, 
                     abbrev_map: Dict) -> Dict
```

#### `umls_linker.py`
UMLS API integration.
```python
class UMLSClient:
    def search_term(term: str) -> List[Dict]
    def get_cui_info(cui: str) -> Dict
    
def link_umls_phrases(phrases: List[str], 
                      client: UMLSClient) -> List[Dict]
```

#### `local_linkers.py`
Local entity linking implementations.
```python
def link_with_scispacy(text: str, 
                       model: str = "en_core_sci_md") -> List[Dict]
def link_with_quickumls(text: str, 
                        quickumls_path: str) -> List[Dict]
```

### Utility Modules

#### `cache_manager.py`
Persistent caching system.
```python
class CacheManager:
    def get(key: str) -> Optional[Any]
    def set(key: str, value: Any) -> None
    def cache_umls_lookup(term: str, result: Dict) -> None
```

#### `validator.py`
Quality assurance checks.
```python
def validate_extraction(doc: Dict) -> Dict:
    # Returns validation scores and issues
    {
        "validations": {...},
        "completeness_score": 0-100,
        "issues": [...],
        "is_valid": bool
    }
```

#### `env_loader.py`
Environment configuration.
```python
def load_env() -> Dict:
    # Returns all environment variables
    {
        "UMLS_API_KEY": str,
        "NCBI_API_KEY": str,
        "NCBI_EMAIL": str,
        "GROBID_URL": str,
        "QUICKUMLS_PATH": str
    }
```

## Configuration

### Environment Variables (.env)
```bash
# Required
UMLS_API_KEY=your_umls_api_key_here
GROBID_URL=http://localhost:8070

# Optional
NCBI_API_KEY=your_ncbi_api_key
NCBI_EMAIL=your@email.com
QUICKUMLS_PATH=/path/to/quickumls/data
```

### Docling Configuration (config/docling_medical_config.yaml)
```yaml
pipeline:
  - extractor.pdf_text        # Text extraction
  - extractor.pdf_layout      # Layout analysis
  - enrich.sections          # Section detection
  - enrich.paragraphs        # Paragraph segmentation
  - enrich.headers           # Header identification
  - enrich.footnotes         # Footnote extraction
  - enrich.tables:           # Table processing
      mode: hybrid
      output_format: json
      include_footnotes: true
  - enrich.figures:          # Figure extraction
      include_bboxes: true
      include_page_index: true
  - enrich.figure_captions   # Caption association
  - enrich.citations         # Citation detection
  - enrich.references        # Reference parsing

options:
  normalize_unicode: true
  merge_columns: true
  language: en
  deduplicate: true
  parallelism: 8
  emit_spans: true
```

### Medical Abbreviations (config/abbreviations_med.json)
```json
{
  "PTX": "Pneumothorax",
  "NSCLC": "Non-small cell lung cancer",
  "ARDS": "Acute respiratory distress syndrome",
  "COPD": "Chronic obstructive pulmonary disease",
  "IL-6": "Interleukin-6",
  "HR": "Hazard ratio",
  "OR": "Odds ratio",
  "RR": "Relative risk"
}
```

## API Integrations

### UMLS REST API
```python
Base URL: https://uts-ws.nlm.nih.gov/rest
Authentication: API Key in header

Endpoints:
- /search/current: Term search
- /content/current/CUI/{cui}: Concept details
- /content/current/source/MSH/descendants: Hierarchy
```

### NCBI E-utilities
```python
Base URL: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
Authentication: API Key as parameter

Endpoints:
- esearch.fcgi: Search PubMed
- efetch.fcgi: Retrieve records
- elink.fcgi: Find related articles
```

### GROBID
```python
Base URL: http://localhost:8070
Authentication: None (local service)

Endpoints:
- /api/processFulltextDocument: Complete analysis
- /api/processReferences: Reference extraction
- /api/processCitation: Single citation parsing
```

## Data Schemas

### Main Output JSON Schema
```typescript
interface MedParseOutput {
  metadata: {
    title: string;
    year: string;
    authors: Author[];
    references_text: string[];
  };
  
  structure: {
    sections: Section[];
    tables: Table[];
    figures: Figure[];
    citations: Citation[];
  };
  
  umls_links?: UMLSConcept[];
  umls_links_local?: UMLSConcept[];
  
  statistics: Statistic[];
  drugs: Drug[];
  trial_ids: string[];
  
  references_enriched?: EnrichedReference[];
  
  validation: ValidationResult;
  
  grobid: {
    references_tei: string;
  };
  
  provenance: object;
}

interface Author {
  family: string;
  given: string;
  display: string;
  ama: string;
}

interface Section {
  title: string;
  category: string;
  paragraphs: Paragraph[];
}

interface Paragraph {
  text: string;
  cross_refs?: CrossReference[];
}

interface Table {
  title?: string;
  caption?: string;
  headers?: string[];
  rows?: any[][];
  normalized?: boolean;
}

interface Figure {
  caption: string;
  bbox?: BoundingBox;
  page?: number;
}

interface UMLSConcept {
  phrase: string;
  cui: string;
  preferred: string;
  source: "UMLS" | "scispaCy" | "QuickUMLS";
}

interface Statistic {
  type: "p_value" | "confidence_interval" | "hazard_ratio" | 
        "odds_ratio" | "relative_risk" | "sample_size";
  value: number | string;
  context: string;
}

interface Drug {
  drug: string;
  dosage?: string;
  frequency?: string;
  route?: string;
}

interface ValidationResult {
  validations: Record<string, boolean>;
  completeness_score: number;
  issues: string[];
  is_valid: boolean;
}
```

### QA Report Schema
```typescript
interface QAReport {
  pdf: string;
  n_sections: number;
  n_tables: number;
  n_figures: number;
  n_fig_crops: number;
  missing_fig_bbox: number;
  n_refs_csv: number;
  n_umls_links: number;
  n_local_links: number;
  linker: "umls" | "scispacy" | "quickumls";
  completeness_score: number;
  is_valid: boolean;
}
```

## Performance Considerations

### Processing Times (per paper)
- Docling parsing: 5-15 seconds
- GROBID processing: 3-8 seconds
- UMLS linking (online): 10-30 seconds
- scispaCy linking (local): 5-10 seconds
- QuickUMLS linking (local): 2-5 seconds
- Total pipeline: 30-60 seconds

### Memory Requirements
- Base Python environment: 500MB
- Docling processing: 200-500MB per PDF
- scispaCy model: 500MB loaded
- QuickUMLS index: 1-2GB loaded
- Peak usage: 2-3GB for large PDFs

### Optimization Strategies

#### Batch Processing
```python
# Optimal batch sizes
UMLS: 5-10 papers (API rate limits)
scispaCy: 20-30 papers (memory constraints)
QuickUMLS: 50+ papers (CPU bound)
```

#### Parallel Processing
```python
# CPU cores utilization
from multiprocessing import Pool, cpu_count

def process_batch(pdfs):
    with Pool(min(cpu_count(), 8)) as pool:
        results = pool.map(process_single, pdfs)
    return results
```

#### Caching Strategy
```python
# Cache hit rates (typical)
UMLS terms: 60-70% after 100 papers
NCBI queries: 40-50% for common journals
Overall speedup: 2-3x with warm cache
```

### Scalability Limits
- Single machine: 100-200 papers/hour
- API constraints: UMLS 20 requests/second
- Storage: ~10MB per paper (JSON + assets)
- Network: 100KB-1MB per API call

## Extension Points

### Adding New Entity Linkers

1. Implement linker function in `local_linkers.py`:
```python
def link_with_custom(text: str, **kwargs) -> List[Dict[str, Any]]:
    # Your implementation
    return [
        {
            "phrase": "extracted phrase",
            "cui": "concept_id",
            "preferred": "preferred term",
            "source": "CustomLinker"
        }
    ]
```

2. Update `process_one.py`:
```python
elif linker == "custom":
    linked = link_with_custom(full_text)
    if linked:
        merged.setdefault("umls_links_local", []).extend(linked)
    linker_tag = "custom"
```

3. Add to argument choices:
```python
ap.add_argument("--linker", 
                choices=["umls","scispacy","quickumls","custom"],
                default="umls")
```

### Adding New Extractors

1. Create extractor module:
```python
# scripts/custom_extractor.py
def extract_custom_entities(text: str) -> List[Dict]:
    # Pattern matching or ML-based extraction
    return extracted_entities
```

2. Integrate into pipeline:
```python
# In process_one.py
from scripts.custom_extractor import extract_custom_entities
merged["custom_entities"] = extract_custom_entities(full_text)
```

### Custom Validation Rules

1. Extend validator:
```python
# In validator.py
checks["has_custom_field"] = bool(doc.get("custom_field"))
checks["custom_validation"] = validate_custom_logic(doc)
```

### Output Format Adapters

1. Create adapter module:
```python
# scripts/output_adapters.py
def to_bioc_format(doc: Dict) -> str:
    # Convert to BioC XML
    return bioc_xml

def to_fhir_format(doc: Dict) -> Dict:
    # Convert to FHIR resources
    return fhir_bundle
```

## Security Considerations

### API Key Management
- Store in environment variables
- Never commit to version control
- Rotate periodically
- Use read-only keys when possible

### Input Validation
- PDF size limits (recommended: <50MB)
- Malformed PDF detection
- Path traversal prevention
- Injection attack mitigation

### Data Privacy
- Local processing options available
- No data retention by default
- Configurable anonymization
- HIPAA compliance considerations

## Troubleshooting

### Common Issues

#### GROBID Connection Failed
```bash
# Check service status
curl http://localhost:8070/api/isalive

# Restart container
docker restart grobid_container

# Check logs
docker logs grobid_container
```

#### UMLS API Authentication Failed
```python
# Verify API key
curl -H "Authorization: apikey YOUR_KEY" \
  https://uts-ws.nlm.nih.gov/rest/search/current?string=test

# Check key permissions
# Ensure "UMLS REST API" is enabled in profile
```

#### Memory Errors
```bash
# Increase Python memory limit
export PYTHONMAXMEM=4G

# Process smaller batches
python scripts/run_batch.py --batch_size 5

# Clear cache if too large
rm -rf cache/*.pkl
```

#### Slow Processing
```python
# Profile bottlenecks
import cProfile
cProfile.run('process_pdf(...)', 'stats.prof')

# Common causes:
# - Network latency (use local linkers)
# - Large PDFs (preprocess/split)
# - API rate limits (implement backoff)
```

## Development Guidelines

### Code Style
- Type hints for all functions
- Docstrings for public APIs
- Black formatter compliance
- Pylint score > 8.0

### Testing Strategy
```python
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# End-to-end tests
pytest tests/e2e/

# Coverage target: >80%
pytest --cov=scripts --cov-report=html
```

### Contribution Workflow
1. Fork repository
2. Create feature branch
3. Implement with tests
4. Update documentation
5. Submit pull request

### Release Process
1. Version bump in `__version__`
2. Update CHANGELOG.md
3. Tag release
4. Build artifacts
5. Publish to PyPI (future)