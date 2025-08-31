# Testing Guide for MedParse-Docling

## Quick Start: Testing NLP-Hardened Branch

### Step 1: Switch to NLP Branch
```bash
git checkout feat/nlp-hardening-docling248
```

### Step 2: Single Article Test Commands

#### Option A: Using process_one.py (Recommended)
```bash
# Test with UMLS (requires API key)
python scripts/process_one.py \
  --pdf input/AMPLE2.pdf \
  --out out/test_nlp_umls.json \
  --linker umls

# Test with QuickUMLS (local, fast)
python scripts/process_one.py \
  --pdf input/AMPLE2.pdf \
  --out out/test_nlp_quick.json \
  --linker quickumls

# Test with scispaCy
python scripts/process_one.py \
  --pdf input/AMPLE2.pdf \
  --out out/test_nlp_scispacy.json \
  --linker scispacy
```

#### Option B: Using Integrated Pipeline (NLP branch only)
```bash
# Auto mode tries UMLS → QuickUMLS → scispaCy
python scripts/process_one_integrated.py input/AMPLE2.pdf --linker auto

# Specific linker
python scripts/process_one_integrated.py input/AMPLE2.pdf --linker umls
```

#### Option C: Comparative Evaluation
```bash
# Run all three linkers and compare
python bin/run_linkers.py --pdf input/AMPLE2.pdf --compare

# Output to specific directory
python bin/run_linkers.py \
  --pdf input/AMPLE2.pdf \
  --compare \
  --out-dir comparisons/
```

#### Option D: Legacy Test Script
```bash
./test_one_paper.sh "AMPLE2.pdf"
```

### Step 3: Verify Output

Check the generated JSON file:
```bash
# View summary
python -c "
import json
d = json.load(open('out/test_nlp_umls.json'))
print('Authors:', len(d['metadata'].get('authors', [])))
print('Structured refs:', len(d['metadata'].get('references_struct', [])))
print('Enriched refs:', len(d.get('references_enriched', [])))
print('Entities:', len(d.get('umls_links', [])))
print('Statistics:', len(d.get('statistics', [])))
print('Figures:', len(d['structure'].get('figures', [])))
print('Validation score:', d['validation']['completeness_score'])
"
```

## Test Scenarios

### 1. Basic Functionality Test
```bash
# Test core pipeline without GROBID
python test_pipeline.py
```

Expected output:
- ✓ Docling adapter
- ✓ Text normalization
- ✓ Statistics extraction
- ✓ Cross-references
- ✓ Validation

### 2. Full Pipeline Test
```bash
# Test with GROBID integration
python test_full_pipeline.py
```

Expected output:
- ✓ GROBID connection
- ✓ 22+ authors extracted
- ✓ 28 references structured
- ✓ References enriched
- ✓ Completeness score ≥70%

### 3. Figure Extraction Test
```bash
# Process a PDF and check figure output
python scripts/process_one.py --pdf input/AMPLE2.pdf --out test.json --linker umls

# Check figures
ls -la out/figures/AMPLE2_*.jpg

# Verify EXIF captions
exiftool out/figures/AMPLE2_figure1.jpg | grep Description
```

Expected:
- 5 figures extracted (watermark filtered)
- Each figure labeled (e.g., AMPLE2_figure1.jpg)
- EXIF Description contains caption

### 4. Reference Enrichment Test
```bash
# Requires NCBI_API_KEY in .env
python -c "
from scripts.ref_enricher import enrich_refs_from_struct
refs = [
    {'title': 'Malignant pleural effusion', 
     'doi': '10.1001/jama.2017.17426',
     'year': '2017'}
]
enriched = enrich_refs_from_struct(refs)
print('PMID:', enriched[0]['enrichment'].get('pmid'))
"
```

Expected: PMID should be populated

### 5. Text Normalization Test
```bash
python -c "
from scripts.text_normalize import normalize_for_nlp
text = 'This has ﬁgures and eﬀects. Odds ratio (or) inserted. Statis-\\ntics split.'
clean = normalize_for_nlp(text)
print('Original:', repr(text))
print('Cleaned:', repr(clean))
assert 'ﬁ' not in clean
assert 'Odds ratio (or)' not in clean
print('✓ Text normalization working')
"
```

### 6. Entity Linking with Filtering Test
```bash
python -c "
from scripts.filters import keep
# Should keep clinical concept
assert keep('diabetes', 'T047', 0.8) == True
# Should filter generic term
assert keep('text', 'T047', 0.9) == False
# Should filter non-clinical TUI
assert keep('water', 'T167', 0.9) == False
print('✓ Semantic filtering working')
"
```

## Performance Testing

### Single PDF Timing
```bash
time python scripts/process_one.py \
  --pdf input/AMPLE2.pdf \
  --out timing_test.json \
  --linker quickumls
```

Expected times:
- QuickUMLS: ~30-45 seconds
- scispaCy: ~45-60 seconds
- UMLS: ~60-90 seconds (with API calls)

### Batch Processing
```bash
# Place multiple PDFs in input/
time python scripts/run_batch.py --linker quickumls
```

## Validation Testing

### Check Validation Report
```bash
python -c "
import json
from scripts.validator import validate_extraction, generate_validation_report

doc = json.load(open('out/test_nlp_umls.json'))
validation = validate_extraction(doc)
report = generate_validation_report(validation)
print(report)
"
```

Expected report should show:
- Completeness Score: 70-90%
- Quality Level: GOOD or EXCELLENT
- Valid for NLP: YES

## Troubleshooting Tests

### 1. Check GROBID Connection
```bash
curl http://localhost:8070/api/isalive
# Should return: true
```

### 2. Test UMLS API Key
```bash
python -c "
from scripts.umls_linker import UMLSClient
import os
client = UMLSClient(api_key=os.getenv('UMLS_API_KEY'))
result = client.search('diabetes')
print(f'Found {len(result)} results for diabetes')
"
```

### 3. Test NCBI API Key
```bash
python -c "
import os
os.environ['NCBI_API_KEY'] = 'your_key_here'
from scripts.ref_enricher import _idconv_doi
pmid = _idconv_doi('10.1001/jama.2017.17426')
print(f'PMID: {pmid}')
"
```

### 4. Check QuickUMLS Installation
```bash
python -c "
from quickumls import QuickUMLS
import os
path = os.getenv('QUICKUMLS_PATH')
if path:
    matcher = QuickUMLS(path)
    print('QuickUMLS loaded successfully')
else:
    print('QUICKUMLS_PATH not set')
"
```

## Comparative Testing

### Compare Main vs NLP Branch
```bash
# Main branch
git checkout main
python scripts/process_one.py --pdf input/AMPLE2.pdf --out main_output.json --linker umls

# NLP branch
git checkout feat/nlp-hardening-docling248
python scripts/process_one.py --pdf input/AMPLE2.pdf --out nlp_output.json --linker umls

# Compare
python -c "
import json
main = json.load(open('main_output.json'))
nlp = json.load(open('nlp_output.json'))
print('Main branch:')
print('  Authors:', len(main['metadata'].get('authors', [])))
print('  Entities:', len(main.get('umls_links', [])))
print('NLP branch:')
print('  Authors:', len(nlp['metadata'].get('authors', [])))
print('  Entities:', len(nlp.get('umls_links', [])))
print('  Structured refs:', len(nlp['metadata'].get('references_struct', [])))
"
```

## Expected Test Results for AMPLE2.pdf

When testing with AMPLE2.pdf on the NLP-hardened branch:

- **Authors**: 22-23 (clean extraction from TEI)
- **Structured References**: 28
- **Enriched References**: 20-28 (depending on PubMed availability)
- **Figures**: 5 saved (1 watermark filtered)
- **Tables**: 3
- **Sections**: 15-20
- **Statistics**: 150-200
- **Cross-references**: 10-20
- **Completeness Score**: 70-85%
- **Quality Level**: "good" or "acceptable"

## Continuous Testing

### Pre-commit Test
```bash
# Run before committing
python test_pipeline.py && python test_full_pipeline.py
```

### Full Test Suite
```bash
# Create test script
cat > run_tests.sh << 'EOF'
#!/bin/bash
set -e
echo "Running pipeline tests..."
python test_pipeline.py
echo "Running full pipeline test..."
python test_full_pipeline.py
echo "Testing AMPLE2..."
python scripts/process_one.py --pdf input/AMPLE2.pdf --out test_output.json --linker quickumls
echo "All tests passed!"
EOF
chmod +x run_tests.sh
./run_tests.sh
```

## Debug Mode Testing

### Enable Debug Output
```bash
export DEBUG=1
python scripts/process_one.py --pdf input/AMPLE2.pdf --out debug.json --linker umls
```

### Check Logs
```bash
# View QA logs
cat out/qa/AMPLE2__umls.qa.json | python -m json.tool

# Check cache hits
ls -la cache/ | head -20
```

## Memory and Performance Profiling

### Memory Usage
```bash
# Monitor memory during processing
/usr/bin/time -v python scripts/process_one.py \
  --pdf input/AMPLE2.pdf \
  --out memory_test.json \
  --linker quickumls
```

### Profile Execution
```bash
python -m cProfile -o profile.stats scripts/process_one.py \
  --pdf input/AMPLE2.pdf \
  --out profile_test.json \
  --linker quickumls

# Analyze
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"
```