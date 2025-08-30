# MedParse-Docling User Guide

## Table of Contents
1. [Quick Start](#quick-start)
2. [Understanding the Pipeline](#understanding-the-pipeline)
3. [Basic Usage](#basic-usage)
4. [Advanced Usage](#advanced-usage)
5. [Comparing Entity Linkers](#comparing-entity-linkers)
6. [Interpreting Results](#interpreting-results)
7. [Best Practices](#best-practices)
8. [Common Workflows](#common-workflows)

## Quick Start

### Minimal Setup (UMLS only)
```bash
# 1. Set up environment
conda create -n medparse python=3.12 -y
conda activate medparse
pip install -r requirements.txt

# 2. Create .env file with your UMLS API key
echo "UMLS_API_KEY=your_key_here" > .env
echo "GROBID_URL=http://localhost:8070" >> .env

# 3. Start GROBID
docker run -d -p 8070:8070 lfoppiano/grobid:0.8.0

# 4. Process PDFs
cp your_papers/*.pdf input/
python scripts/run_batch.py --linker umls
```

### Full Setup (All Entity Linkers)
```bash
# Additional setup for local linkers
pip install scispacy spacy>=3.5 quickumls
python -m spacy download en_core_sci_md

# Add to .env
echo "QUICKUMLS_PATH=/path/to/quickumls/data" >> .env
echo "NCBI_API_KEY=your_ncbi_key" >> .env
echo "NCBI_EMAIL=your@email.com" >> .env
```

## Understanding the Pipeline

### Architecture Overview
```
PDF Input → Docling (structure) → GROBID (metadata) → Entity Linking → Enrichment → JSON Output
                ↓                      ↓                    ↓              ↓
           (sections,            (authors, refs)    (UMLS/scispaCy/   (stats, drugs,
            tables, figs)                             QuickUMLS)      trial IDs)
```

### Three Entity Linking Options

1. **UMLS (Online)**: Official UMLS API, most accurate, requires API key
2. **scispaCy (Local)**: Fast local processing, good for high volume
3. **QuickUMLS (Local)**: Fastest, requires pre-built index

## Basic Usage

### Process Single Paper
```bash
# Basic processing
python scripts/process_one.py \
  --pdf input/paper.pdf \
  --out out/json_umls/paper.json \
  --linker umls

# With different linker
python scripts/process_one.py \
  --pdf input/paper.pdf \
  --out out/json_scispacy/paper.json \
  --linker scispacy
```

### Batch Process All Papers
```bash
# Process all PDFs in input/ folder
python scripts/run_batch.py --linker umls

# Custom input/output folders
python scripts/run_batch.py \
  --input /path/to/pdfs \
  --out_root /path/to/output \
  --linker scispacy
```

### Compare Entity Linkers
```bash
# Run all three pipelines
python scripts/run_batch.py --linker umls
python scripts/run_batch.py --linker scispacy
python scripts/run_batch.py --linker quickumls

# Compare results
python scripts/compare_linkers.py --pdf_stems "paper1" "paper2"
```

## Advanced Usage

### Custom Configuration

#### Medical Abbreviations
Edit `config/abbreviations_med.json`:
```json
{
  "COPD": "Chronic obstructive pulmonary disease",
  "ARDS": "Acute respiratory distress syndrome",
  "IL-6": "Interleukin-6"
}
```

#### Docling Settings
Edit `config/docling_medical_config.yaml`:
```yaml
pipeline:
  - extractor.pdf_text
  - extractor.pdf_layout
  - enrich.sections
  - enrich.tables:
      mode: hybrid
      output_format: json
```

### Environment Variables
Create `.env` file:
```bash
# Required for UMLS
UMLS_API_KEY=your_umls_api_key

# Required for GROBID
GROBID_URL=http://localhost:8070

# Optional for PubMed enrichment
NCBI_API_KEY=your_ncbi_api_key
NCBI_EMAIL=your@email.com

# Required for QuickUMLS
QUICKUMLS_PATH=/path/to/quickumls/data
```

### Processing Options

#### Parallel Processing
```bash
# Process multiple papers in parallel
cat > parallel_process.sh << 'EOF'
#!/bin/bash
for pdf in input/*.pdf; do
  python scripts/process_one.py \
    --pdf "$pdf" \
    --out "out/json_umls/$(basename ${pdf%.pdf}).json" \
    --linker umls &
done
wait
EOF
chmod +x parallel_process.sh
./parallel_process.sh
```

#### Selective Processing
```bash
# Process only specific papers
for paper in "paper1.pdf" "paper2.pdf"; do
  python scripts/process_one.py \
    --pdf "input/$paper" \
    --out "out/json_umls/${paper%.pdf}.json" \
    --linker umls
done
```

## Comparing Entity Linkers

### Running A/B/C Comparison

1. **Process with all linkers:**
```bash
# Sequential processing
for linker in umls scispacy quickumls; do
  echo "Processing with $linker..."
  python scripts/run_batch.py --linker $linker
done
```

2. **Compare results:**
```bash
# Compare specific papers
python scripts/compare_linkers.py \
  --pdf_stems "3D printing for airway disease" \
              "A Multicenter RCT of Zephyr Endobronchial Valv"

# Compare all papers
python scripts/compare_linkers.py \
  --pdf_stems $(ls input/*.pdf | xargs -n1 basename | sed 's/.pdf//')
```

### Understanding Comparison Output
```
== paper_name ==
Title: Full Paper Title Here
UMLS: links=125 local=0 score=88
scispaCy: links=0 local=89 score=75
QuickUMLS: links=0 local=103 score=75
```

- **links**: UMLS concepts found via online API
- **local**: Concepts found via local linker
- **score**: Validation completeness score (0-100)

## Interpreting Results

### Output Structure
```
out/
├── json_umls/          # UMLS pipeline outputs
│   └── paper.json
├── json_scispacy/      # scispaCy pipeline outputs
│   └── paper.json
├── json_quickumls/     # QuickUMLS pipeline outputs
│   └── paper.json
├── figures/            # Extracted figure images
│   └── paper_fig_001.jpg
├── references/         # AMA-formatted references
│   └── paper.refs.csv
└── qa/                 # Quality assurance logs
    ├── paper__umls.qa.json
    ├── paper__scispacy.qa.json
    └── paper__quickumls.qa.json
```

### JSON Output Schema
```json
{
  "metadata": {
    "title": "Paper Title",
    "year": "2024",
    "authors": [
      {
        "family": "Smith",
        "given": "John",
        "display": "John Smith",
        "ama": "Smith J"
      }
    ]
  },
  "structure": {
    "sections": [...],
    "tables": [...],
    "figures": [...]
  },
  "umls_links": [
    {
      "phrase": "pneumonia",
      "cui": "C0032285",
      "preferred": "Pneumonia",
      "source": "UMLS"
    }
  ],
  "statistics": [
    {
      "type": "p_value",
      "value": 0.001,
      "context": "significant difference (p=0.001)"
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
  "validation": {
    "completeness_score": 88,
    "is_valid": true
  }
}
```

### QA Report Fields
```json
{
  "pdf": "paper.pdf",
  "n_sections": 8,
  "n_tables": 3,
  "n_figures": 5,
  "n_fig_crops": 5,
  "n_refs_csv": 45,
  "n_umls_links": 125,
  "n_local_links": 0,
  "linker": "umls",
  "completeness_score": 88,
  "is_valid": true
}
```

## Best Practices

### 1. API Key Management
- Store keys in `.env` file, never commit to git
- Use environment variables for production
- Rotate keys periodically

### 2. Processing Strategy
- Start with a small batch to test configuration
- Use UMLS for highest accuracy
- Use local linkers for high-volume processing
- Cache results to avoid redundant API calls

### 3. Quality Control
- Check QA reports for validation issues
- Review papers with completeness_score < 60
- Verify figure extraction visually
- Compare linker outputs for critical papers

### 4. Performance Optimization
- Process in batches of 10-20 papers
- Use parallel processing for large datasets
- Enable caching (automatic in `cache/` folder)
- Monitor API rate limits

### 5. Troubleshooting Steps
1. Check GROBID is running: `curl http://localhost:8070/api/isalive`
2. Verify API keys in `.env`
3. Check input PDF quality (not scanned images)
4. Review error logs in console output
5. Examine QA reports for specific issues

## Common Workflows

### Research Paper Analysis
```bash
# 1. Add papers to input folder
cp ~/research/papers/*.pdf input/

# 2. Process with UMLS for accuracy
python scripts/run_batch.py --linker umls

# 3. Extract all statistics
python -c "
import json
from pathlib import Path
for f in Path('out/json_umls').glob('*.json'):
    data = json.load(open(f))
    if data.get('statistics'):
        print(f'{f.stem}:', data['statistics'])
"
```

### Clinical Trial Mining
```bash
# Extract all trial IDs
python -c "
import json
from pathlib import Path
trials = []
for f in Path('out/json_umls').glob('*.json'):
    data = json.load(open(f))
    if data.get('trial_ids'):
        trials.extend(data['trial_ids'])
print('Unique trials:', set(trials))
"
```

### Drug Information Extraction
```bash
# Compile drug/dosage information
python -c "
import json
from pathlib import Path
import pandas as pd
drugs = []
for f in Path('out/json_umls').glob('*.json'):
    data = json.load(open(f))
    for drug in data.get('drugs', []):
        drug['paper'] = f.stem
        drugs.append(drug)
df = pd.DataFrame(drugs)
df.to_csv('drug_summary.csv', index=False)
print(df.groupby('drug')['dosage'].value_counts())
"
```

### Reference Network Analysis
```bash
# Extract all DOIs for citation network
python -c "
import json
from pathlib import Path
dois = []
for f in Path('out/json_umls').glob('*.json'):
    data = json.load(open(f))
    refs = data.get('references_enriched', [])
    for ref in refs:
        for hit in ref.get('hits', []):
            if hit.get('doi'):
                dois.append(hit['doi'])
print(f'Found {len(set(dois))} unique DOIs')
"
```

### Quality Assessment Dashboard
```bash
# Generate QA summary
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
}))

print('\n=== Papers Needing Review ===')
print(df[df['completeness_score'] < 70][['pdf', 'linker', 'completeness_score']])
"
```

## Tips for Different Use Cases

### High-Accuracy Medical Research
- Use UMLS linker exclusively
- Enable NCBI enrichment
- Manual review of papers with score < 80
- Cross-reference extracted stats with source

### Large-Scale Processing
- Use scispaCy for balance of speed/accuracy
- Process in parallel batches
- Implement retry logic for failed papers
- Use QuickUMLS for initial screening

### Real-Time Processing
- Pre-build QuickUMLS index
- Keep GROBID container always running
- Implement queuing system
- Cache all API responses

### Regulatory Compliance
- Document pipeline version
- Archive raw outputs
- Validate critical extractions manually
- Maintain audit trail of processing

## Getting Help

### Check Status
```bash
# System health check
./check_status.sh

# Detailed paper analysis
python scripts/process_one.py --pdf input/test.pdf --out test.json --linker umls
cat test.json | python -m json.tool | less
```

### Debug Mode
```bash
# Run with detailed logging
LOGURU_LEVEL=DEBUG python scripts/process_one.py \
  --pdf input/paper.pdf \
  --out debug.json \
  --linker umls 2>&1 | tee debug.log
```

### Common Issues
- **No UMLS links found**: Check API key, verify medical content
- **Low completeness score**: Review PDF quality, check GROBID status
- **Missing figures**: Ensure PDFs have embedded images (not scanned)
- **Slow processing**: Reduce batch size, check network connection