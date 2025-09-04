# MedParse-Docling User Guide

A comprehensive guide for processing medical literature PDFs into RAG-ready JSON documents with complete content preservation and 100% abstract coverage.

## Table of Contents
- [Quick Start](#quick-start)
- [Getting Started](#getting-started)
- [Complete Pipeline](#complete-pipeline)
- [Basic Usage](#basic-usage)
- [NLP-Hardened Features](#nlp-hardened-features)
- [Advanced Features](#advanced-features)
- [Understanding the Output](#understanding-the-output)
- [Verification & Quality](#verification--quality)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Quick Start

```bash
# Process PDFs → Extract → Enrich → Clean → RAG-Ready
python scripts/run_batch.py papers/ out/batch_processed/
python scripts/harden_extracted.py out/batch_processed/ out/hardened/
python scripts/prepare_for_rag.py out/hardened/ out/rag_ready_complete/ --mode full
python scripts/fix_missing_abstracts.py out/rag_ready_complete/ --only-missing
python scripts/audit_abstracts.py out/rag_ready_complete/
```

Result: Complete JSONs in `out/rag_ready_complete/` with 100% abstract coverage.

## Getting Started

### Prerequisites
- Python 3.12+
- Docker (for GROBID)
- API Keys (UMLS, NCBI)
- 4GB+ RAM recommended
- GPU optional (speeds up Docling)

### Initial Setup

1. **Clone and setup environment:**
```bash
git clone <your-repo-url>
cd medparse-docling
conda create -n medparse python=3.12 -y
conda activate medparse
pip install -r requirements.txt
```

2. **Configure API keys:**
```bash
cp .env.example .env
# Edit .env and add your API keys:
nano .env
```

Required API keys:
- **UMLS_API_KEY**: Get from https://uts.nlm.nih.gov/uts/profile
- **NCBI_API_KEY**: Get from https://www.ncbi.nlm.nih.gov/account/
- **NCBI_EMAIL**: Your email for NCBI

3. **Start GROBID:**
```bash
docker run -d -p 8070:8070 --name grobid lfoppiano/grobid:0.8.0
```

4. **Test installation:**
```bash
python test_pipeline.py
# Should show ✓ for all components
```

## Basic Usage

### Processing a Single PDF

#### Standard Extraction (Main Branch)
```bash
# Basic command with UMLS
python scripts/process_one.py --pdf input/paper.pdf --out output.json --linker umls

# With QuickUMLS (faster, local)
python scripts/process_one.py --pdf input/paper.pdf --out output.json --linker quickumls

# With scispaCy (balanced)
python scripts/process_one.py --pdf input/paper.pdf --out output.json --linker scispacy
```

#### NLP-Hardened Extraction (Recommended)
```bash
# Switch to NLP branch for better quality
git checkout feat/nlp-hardening-docling248

# Run with enhanced processing
python scripts/process_one.py --pdf input/paper.pdf --out output.json --linker umls

# Or use integrated pipeline with auto-fallback
python scripts/process_one_integrated.py input/paper.pdf --linker auto
```

### Quick Test with Sample Paper
```bash
# Test with AMPLE2.pdf (included sample)
python scripts/process_one.py --pdf input/AMPLE2.pdf --out test.json --linker umls

# Check results
python -c "
import json
d = json.load(open('test.json'))
print('✓ Authors:', len(d['metadata']['authors']))
print('✓ References:', len(d['metadata'].get('references_struct', [])))
print('✓ Figures:', len(d['structure']['figures']))
print('✓ Score:', d['validation']['completeness_score'], '%')
"
```

### Batch Processing

Process multiple PDFs at once:
```bash
# Process all PDFs in input/ directory
python scripts/run_batch.py --linker umls

# Custom directories
python scripts/run_batch.py \
  --input-dir /path/to/pdfs \
  --output-dir /path/to/output \
  --linker quickumls
```

### Comparative Analysis

Compare different entity linking approaches:
```bash
# Run all three linkers and generate comparison
python bin/run_linkers.py --pdf input/paper.pdf --compare

# Output will be in:
# - out/json_umls/paper.json
# - out/json_quickumls/paper.json  
# - out/json_scispacy/paper.json
```

## NLP-Hardened Features

The `feat/nlp-hardening-docling248` branch includes advanced text processing:

### 1. Text Normalization
Automatically fixes common PDF extraction issues:
- **Ligature correction**: ﬁ → fi, ﬀ → ff, ﬂ → fl
- **Hyphenation removal**: "statis-\ntics" → "statistics"
- **Inline expansion removal**: "Odds ratio (or)" → "Odds ratio"
- **Whitespace normalization**: Multiple spaces → single space

```python
from scripts.text_normalize import normalize_for_nlp

text = "This has ﬁgures and eﬀects. Statis-\ntics split."
clean = normalize_for_nlp(text)
# Result: "This has figures and effects. Statistics split."
```

### 2. Semantic Filtering
Only extracts clinically relevant concepts:

```python
# Clinical TUIs that are kept:
T047: Disease or Syndrome
T191: Neoplastic Process  
T061: Therapeutic Procedure
T059: Laboratory Procedure
T060: Diagnostic Procedure
T121: Pharmacologic Substance
T200: Clinical Drug
T123: Biologically Active Substance
T184: Sign or Symptom

# Generic terms like "text", "value", "study" are filtered out
```

### 3. Clean Author Extraction
- Authors extracted ONLY from GROBID TEI header
- No contamination from references or affiliations
- Structured format with family/given/display/AMA

### 4. Structured References
- Both raw text and structured formats preserved
- Automatic synchronization between CSV and JSON
- Full metadata extraction (title, authors, year, DOI, PMID)

### 5. Enhanced Figure Processing
- Watermark detection and filtering
- Automatic figure labeling (Figure 1, Figure 2, etc.)
- OCR for text-heavy figures (charts, diagrams)
- EXIF caption embedding

## Advanced Features

### Reference Enrichment

Automatically enrich references with PubMed metadata:

```python
from scripts.ref_enricher import enrich_refs_from_struct

refs = [
    {"title": "Some paper", "doi": "10.1234/example", "year": "2023"}
]
enriched = enrich_refs_from_struct(refs)
# Adds: pmid, mesh terms, abstract, full author list
```

Features:
- DOI → PMID resolution
- Title-based fallback search
- MeSH term extraction
- Abstract retrieval
- Author list completion

### Figure Extraction with OCR

Extract and analyze figures:

```bash
# Figures are automatically extracted to out/figures/
ls -la out/figures/*.jpg

# View EXIF caption metadata
exiftool out/figures/paper_figure1.jpg | grep Description

# Check for OCR text (NLP branch)
python -c "
import json
doc = json.load(open('output.json'))
for fig in doc['structure']['figures']:
    if fig.get('ocr_text'):
        print(f\"Figure with text: {fig['caption'][:50]}...\")
"
```

### Statistics Extraction

Automatically extracts statistical values:
- P-values (p<0.001, p=0.05)
- Confidence intervals (95% CI: 1.2-3.4)
- Hazard ratios (HR 2.3)
- Odds ratios (OR 1.5)
- Sample sizes (n=100)

### Cross-Reference Detection

Identifies references to figures, tables, and citations:
```json
{
  "cross_refs": [
    {
      "type": "figure",
      "reference": "Figure 1",
      "context": "As shown in Figure 1, the results..."
    },
    {
      "type": "table",
      "reference": "Table 2",
      "context": "summarized in Table 2"
    }
  ]
}
```

### Custom Entity Linking

Use specific UMLS concepts:

```python
from scripts.umls_linker import UMLSClient
from scripts.cache_manager import CacheManager

cache = CacheManager(Path("cache"))
umls = UMLSClient(api_key="your_key", cache=cache)

# Search for specific concept
results = umls.search("diabetes mellitus")
best_match = umls.best_concept("type 2 diabetes")
```

## Understanding the Output

### JSON Structure

The output JSON contains these main sections:

```json
{
  "metadata": {
    "title": "Paper title",
    "authors": [
      {
        "family": "Smith",
        "given": "John",
        "display": "John Smith",
        "ama": "Smith J"
      }
    ],
    "year": "2024",
    "journal": "Journal Name",
    "doi": "10.1234/example",
    "references_struct": [...],  // Structured references (NLP branch)
    "references_raw": [...]       // Raw text references
  },
  
  "structure": {
    "sections": [
      {
        "title": "Introduction",
        "paragraphs": ["..."],
        "category": "introduction"
      }
    ],
    "tables": [
      {
        "caption": "Table 1: Results",
        "cells": [...],
        "mentions": ["see Table 1"]
      }
    ],
    "figures": [
      {
        "caption": "Figure 1: Study design",
        "image_path": "out/figures/paper_figure1.jpg",
        "ocr_text": "...",  // If text detected (NLP branch)
        "mentions": ["Figure 1 shows"]
      }
    ]
  },
  
  "references_enriched": [  // NLP branch feature
    {
      "title": "Referenced paper",
      "pmid": "12345678",
      "doi": "10.1234/ref",
      "enrichment": {
        "mesh": ["Diabetes Mellitus", "Insulin"],
        "abstract": "...",
        "authors": [...]
      }
    }
  ],
  
  "umls_links": [
    {
      "text": "diabetes",
      "cui": "C0011849",
      "tui": "T047",  // Semantic type
      "preferred": "Diabetes Mellitus",
      "score": 0.95
    }
  ],
  
  "statistics": [
    {
      "type": "p_value",
      "value": "p<0.001",
      "context": "significant difference (p<0.001)",
      "start": 1234,  // Character position
      "end": 1241
    }
  ],
  
  "drugs": [
    {
      "drug": "aspirin",
      "dosage": "100mg",
      "frequency": "daily"
    }
  ],
  
  "trial_ids": ["NCT04280705"],
  
  "cross_refs": [
    {
      "type": "figure",
      "reference": "Figure 1",
      "context": "As shown in Figure 1"
    }
  ],
  
  "validation": {
    "completeness_score": 85,
    "quality_level": "good",
    "is_valid": true,
    "checks": {
      "has_title": true,
      "has_authors": true,
      "authors_are_valid": true,
      "has_sections": true,
      "refs_structured": true,  // NLP branch
      "refs_enriched_some": true,  // NLP branch
      "umls_links": true
    }
  }
}
```

### Output Files

After processing, you'll find:

```
out/
├── json_umls/paper.json         # Full extraction with UMLS entities
├── json_quickumls/paper.json    # With QuickUMLS entities
├── json_scispacy/paper.json     # With scispaCy entities
├── figures/
│   ├── paper_figure1.jpg        # Extracted figure with EXIF caption
│   ├── paper_figure2.jpg        # Labeled by figure number
│   └── ...                      # Watermarks filtered out
├── references/paper.refs.csv    # AMA-formatted references
└── qa/paper__umls.qa.json      # Quality metrics
```

### CSV Reference Format

The references CSV contains:
```csv
#,ama,title,journal,year,volume,issue,pages,doi,pmid,authors
1,"Smith J, Jones M. Title here. JAMA. 2023;123(4):100-105.","Title here","JAMA","2023","123","4","100-105","10.1234/example","12345678","Smith J; Jones M"
```

## Working with Different Linkers

### UMLS (Most Accurate)
- **Pros:** Official UMLS concepts, highest accuracy, comprehensive coverage
- **Cons:** Requires API key, slower (network calls), rate limited
- **Best for:** Final production extractions, publications
- **Speed:** ~60-90 seconds per paper

```bash
python scripts/process_one.py --pdf input/paper.pdf --out output.json --linker umls
```

### QuickUMLS (Fastest)
- **Pros:** Local processing, very fast, no API limits
- **Cons:** Requires local installation (~4GB), less comprehensive
- **Best for:** Development, testing, batch processing
- **Speed:** ~20-30 seconds per paper

```bash
# Setup QuickUMLS first
pip install quickumls
# Download QuickUMLS data and set QUICKUMLS_PATH in .env

python scripts/process_one.py --pdf input/paper.pdf --out output.json --linker quickumls
```

### scispaCy (Balanced)
- **Pros:** Good accuracy, local processing, includes context
- **Cons:** Larger model size, moderate speed
- **Best for:** Research, when UMLS unavailable
- **Speed:** ~30-45 seconds per paper

```bash
# Setup scispaCy
pip install scispacy
python -m spacy download en_core_sci_md

python scripts/process_one.py --pdf input/paper.pdf --out output.json --linker scispacy
```

## Troubleshooting

### Common Issues and Solutions

#### 1. GROBID Connection Error
```bash
# Check if GROBID is running
docker ps | grep grobid

# If not running, start it
docker start grobid

# Test connection
curl http://localhost:8070/api/isalive
# Should return: true
```

#### 2. No Entities Found
```bash
# Check UMLS API key
python -c "
import os
from scripts.umls_linker import UMLSClient
client = UMLSClient(api_key=os.getenv('UMLS_API_KEY'))
print('Testing UMLS...')
results = client.search('diabetes')
print(f'Found {len(results)} results')
"
```

#### 3. Missing Figures
- Ensure PDF has extractable images (not scanned)
- Check coordinate system handling (BOTTOMLEFT)
- Verify GPU support for Docling (if available)

#### 4. Reference Enrichment Failing
```bash
# Test NCBI API
python -c "
from scripts.ref_enricher import _idconv_doi
pmid = _idconv_doi('10.1001/jama.2017.17426')
print(f'PMID: {pmid}')  # Should return a PMID
"
```

#### 5. Slow Processing
- Use QuickUMLS for faster local processing
- Enable caching (automatic in cache/ directory)
- Process in batches with run_batch.py
- Check GPU availability for Docling

#### 6. Memory Issues
```bash
# Monitor memory usage
watch -n 1 free -h

# For large PDFs, process one at a time
python scripts/process_one.py --pdf large.pdf --out output.json --linker quickumls
```

### Debug Mode

Enable detailed logging:
```bash
export DEBUG=1
python scripts/process_one.py --pdf input/paper.pdf --out debug.json --linker umls

# Check logs
tail -f debug.log  # If logging to file
```

### Validation Issues

Check extraction quality:
```python
import json
from scripts.validator import validate_extraction, generate_validation_report

# Load your output
doc = json.load(open('output.json'))

# Run validation
validation = validate_extraction(doc)
report = generate_validation_report(validation)
print(report)

# Common issues:
# - Score < 60%: Missing critical components
# - No authors: GROBID parsing issue
# - No entities: Linker configuration problem
# - No references: Check GROBID processing
```

## Best Practices

### 1. PDF Preparation
- Use original PDFs (not scanned)
- Ensure text is selectable
- Higher resolution improves figure extraction
- Remove password protection

### 2. Optimal Settings
```bash
# For accuracy (research/publication)
git checkout feat/nlp-hardening-docling248
python scripts/process_one.py --pdf input/paper.pdf --out output.json --linker umls

# For speed (development/testing)
python scripts/process_one.py --pdf input/paper.pdf --out output.json --linker quickumls

# For offline processing
python scripts/process_one.py --pdf input/paper.pdf --out output.json --linker scispacy
```

### 3. Quality Control
- Always check validation score (aim for >70%)
- Review extracted authors for contamination
- Verify figure count matches PDF
- Check reference enrichment coverage (>50%)

### 4. Performance Tips
- Use batch processing for multiple PDFs
- Enable GPU for Docling if available
- Cache API responses (automatic)
- Use local linkers for development
- Process during off-peak hours for API services

### 5. Data Management
```bash
# Clean cache periodically (keeps last 30 days)
find cache/ -mtime +30 -delete

# Archive outputs
tar -czf outputs_$(date +%Y%m%d).tar.gz out/

# Track processing metrics
cat out/qa/*.qa.json | jq '.completeness_score' | awk '{sum+=$1} END {print "Average score:", sum/NR}'
```

## Common Workflows

### Research Paper Analysis
```bash
# 1. Add papers to input folder
cp ~/research/papers/*.pdf input/

# 2. Switch to NLP branch for best quality
git checkout feat/nlp-hardening-docling248

# 3. Process with UMLS for accuracy
python scripts/run_batch.py --linker umls

# 4. Extract all statistics
python -c "
import json
from pathlib import Path
for f in Path('out/json_umls').glob('*.json'):
    data = json.load(open(f))
    if data.get('statistics'):
        print(f'{f.stem}:')
        for stat in data['statistics'][:5]:
            print(f'  - {stat['type']}: {stat['value']}')
"
```

### Clinical Trial Mining
```bash
# Extract all trial IDs and drugs
python -c "
import json
from pathlib import Path

trials = set()
drugs = []

for f in Path('out/json_umls').glob('*.json'):
    data = json.load(open(f))
    trials.update(data.get('trial_ids', []))
    for drug in data.get('drugs', []):
        drugs.append(f\"{f.stem}: {drug['drug']} {drug.get('dosage', '')}\")

print('Unique trials:', sorted(trials))
print('\nDrugs found:')
for drug in drugs:
    print(f'  - {drug}')
"
```

### Systematic Review Support
```bash
# Process review papers and extract key data
python bin/run_linkers.py --pdf input/review.pdf --compare

# Generate evidence table
python -c "
import json
import pandas as pd
from pathlib import Path

data = []
for f in Path('out/json_umls').glob('*.json'):
    doc = json.load(open(f))
    data.append({
        'Paper': f.stem,
        'Year': doc['metadata'].get('year'),
        'Authors': len(doc['metadata'].get('authors', [])),
        'References': len(doc['metadata'].get('references_struct', [])),
        'Statistics': len(doc.get('statistics', [])),
        'Clinical Entities': len(doc.get('umls_links', [])),
        'Score': doc['validation']['completeness_score']
    })

df = pd.DataFrame(data)
df.to_csv('evidence_table.csv', index=False)
print(df.to_string())
"
```

### Reference Network Analysis
```bash
# Build citation network
python -c "
import json
from pathlib import Path
import networkx as nx

G = nx.DiGraph()

for f in Path('out/json_umls').glob('*.json'):
    doc = json.load(open(f))
    paper = doc['metadata']['title'][:30]
    
    for ref in doc.get('references_enriched', []):
        if ref.get('enrichment', {}).get('pmid'):
            G.add_edge(paper, ref['enrichment']['pmid'])

print(f'Network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges')
print(f'Most cited: {sorted(G.in_degree(), key=lambda x: x[1], reverse=True)[:5]}')
"
```

### Quality Dashboard
```bash
# Generate comprehensive QA report
python -c "
import json
from pathlib import Path
import pandas as pd

qa_data = []
for f in Path('out/qa').glob('*.qa.json'):
    qa_data.append(json.load(open(f)))

df = pd.DataFrame(qa_data)

print('=== Processing Summary ===')
print(df.groupby('linker').agg({
    'completeness_score': ['mean', 'min', 'max'],
    'n_umls_links': 'mean',
    'n_local_links': 'mean',
    'is_valid': 'sum'
}).round(1))

print('\n=== Papers Needing Review (score < 70) ===')
low_quality = df[df['completeness_score'] < 70]
if not low_quality.empty:
    print(low_quality[['pdf', 'linker', 'completeness_score']].to_string())
else:
    print('All papers meet quality threshold!')

print('\n=== Extraction Statistics ===')
print(f'Total sections: {df['n_sections'].sum()}')
print(f'Total tables: {df['n_tables'].sum()}')
print(f'Total figures: {df['n_figures'].sum()}')
print(f'Total references: {df['n_refs_csv'].sum()}')
"
```

## Expected Results

When processing AMPLE2.pdf with NLP-hardened branch:

| Metric | Expected Value |
|--------|---------------|
| Authors | 22-23 |
| Structured References | 28 |
| Enriched References | 20-28 |
| Figures | 5 (1 watermark filtered) |
| Tables | 3 |
| Sections | 15-20 |
| Statistics | 150-200 |
| Clinical Entities (UMLS) | 100-150 |
| Cross-references | 10-20 |
| Completeness Score | 70-85% |
| Processing Time | 60-90 seconds |

## Support and Resources

### Getting Help
- Check TESTING.md for detailed test procedures
- Review ARCHITECTURE.md for technical details
- See examples/ directory for sample outputs
- GitHub Issues for bug reports

### Useful Links
- [UMLS API Documentation](https://documentation.uts.nlm.nih.gov/rest/home.html)
- [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [GROBID Documentation](https://grobid.readthedocs.io/)
- [Docling Documentation](https://github.com/DS4SD/docling)

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Citation
If you use this tool in research:
```bibtex
@software{medparse-docling,
  title = {MedParse-Docling: NLP-Hardened Medical Document Extraction},
  author = {Your Name},
  year = {2024},
  url = {https://github.com/your-repo/medparse-docling}
}
```