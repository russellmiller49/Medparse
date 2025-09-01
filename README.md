# medparse-docling

**IMPORTANT:** Follow the canonical implementation playbook at:
`/home/rjm/projects/ip_knowledge/medparse/medparse-docling/complete_medparse_implementation.md`
for build, run, and QA steps. Treat that document as source-of-truth.

High-fidelity medical PDF extraction with Docling → GROBID → UMLS (+ fallbacks) and comparative evaluation for entity linking. Features NLP-hardened text processing, structured references with PubMed enrichment, and comprehensive validation.

## Key Features

### Core Extraction
- **Docling 2.48+** compatible with GPU support
- **GROBID TEI** parsing for clean metadata and references
- **Structured references** with DOI→PMID resolution and PubMed enrichment
- **Figure extraction** with watermark filtering, caption labeling, and OCR capability
- **Table preservation** with caption and structure extraction
- **Statistics extraction** (p-values, CIs, HRs, ORs, sample sizes)
- **Cross-reference detection** (figure/table/citation references)

### NLP Hardening (Branch: feat/nlp-hardening-docling248)
- **Text normalization** without mutation (ligatures, hyphens, expansions)
- **Semantic filtering** of UMLS concepts (clinical TUIs only)
- **Clean author extraction** from TEI only (no contamination)
- **Span-based extraction** preserving character positions
- **Entity linking strategies**: UMLS → QuickUMLS → scispaCy fallback
- **OCR for text-heavy figures** with textuality scoring

### Quality Assurance
- **Validation framework** with completeness scoring
- **Reference synchronization** between CSV and JSON
- **Retry mechanisms** with exponential backoff
- **MD5-based caching** for API calls
- **QA logging** and metrics tracking

## Setup

### 1. Environment Setup
```bash
# Create conda environment
conda create -n medparse python=3.12 -y
conda activate medparse

# Install dependencies
pip install -r requirements.txt

# Optional: Install OCR support
pip install pytesseract
# Ensure tesseract is installed: apt-get install tesseract-ocr
```

### 2. Start GROBID
```bash
docker run -p 8070:8070 lfoppiano/grobid:0.8.0
```

### 3. Configure Environment Variables
Create `.env` file:
```env
# Required for full functionality
UMLS_API_KEY=your_umls_api_key_here
NCBI_API_KEY=your_ncbi_api_key_here
NCBI_EMAIL=your.email@example.com
GROBID_URL=http://localhost:8070

# Optional for local entity linking
QUICKUMLS_PATH=/path/to/quickumls/data
```

### 4. Optional: Setup Local Entity Linkers
```bash
# scispaCy
pip install scispacy spacy>=3.5
python -m spacy download en_core_sci_md

# QuickUMLS
pip install quickumls
# Download and prepare QuickUMLS data
```

## Quick Start: Single Article Test

### Basic Test (Main Branch)
```bash
# Place your PDF in input/ directory
cp your_paper.pdf input/

# Run with UMLS (most accurate, requires API key)
python scripts/process_one.py --pdf input/your_paper.pdf --out output.json --linker umls

# Run with QuickUMLS (fastest, local)
python scripts/process_one.py --pdf input/your_paper.pdf --out output.json --linker quickumls

# Run with scispaCy (balanced)
python scripts/process_one.py --pdf input/your_paper.pdf --out output.json --linker scispacy
```

### NLP-Hardened Test (Feature Branch)
```bash
# Switch to NLP hardening branch
git checkout feat/nlp-hardening-docling248

# Run with semantic filtering and text normalization
python scripts/process_one.py --pdf input/AMPLE2.pdf --out out/test_nlp.json --linker umls

# Test the integrated pipeline with all modules
python scripts/process_one_integrated.py input/AMPLE2.pdf --linker auto

# Run comparative evaluation
python bin/run_linkers.py --pdf input/AMPLE2.pdf --compare
```

### Test Scripts
```bash
# Quick pipeline test (no GROBID)
python test_pipeline.py

# Full pipeline test (with GROBID)
python test_full_pipeline.py

# Legacy script
./test_one_paper.sh "AMPLE2.pdf"
```

## Batch Processing

```bash
# Process all PDFs in input/ directory
python scripts/run_batch.py --linker umls

# Process with specific linker
python scripts/run_batch.py --linker quickumls --input-dir input/ --output-dir output/
```

## Comparative Evaluation

```bash
# Compare all three linkers on specific papers
python scripts/compare_linkers.py --pdf_stems paper1 paper2 paper3

# Full comparison with side-by-side outputs
python bin/run_linkers.py --pdf input/paper.pdf --compare --out-dir comparison/
```

## Output Structure

```
out/
├── json_umls/           # UMLS-linked extractions
│   └── paper.json       # Complete extraction with entities
├── json_quickumls/      # QuickUMLS-linked extractions
├── json_scispacy/       # scispaCy-linked extractions
├── figures/             # Extracted figure images
│   ├── paper_figure1.jpg   # With EXIF caption metadata
│   └── paper_figure2.jpg   # Labeled by figure number
├── references/          # Reference CSVs
│   └── paper.refs.csv   # AMA-formatted references
└── qa/                  # Quality assurance logs
    └── paper__umls.qa.json  # Metrics and validation

```

## JSON Output Schema

```json
{
  "metadata": {
    "title": "...",
    "authors": [
      {"family": "Smith", "given": "John", "display": "John Smith", "ama": "Smith J"}
    ],
    "year": "2024",
    "journal": "...",
    "references_struct": [...],  // Structured references
    "references_raw": [...]      // Raw reference text
  },
  "structure": {
    "sections": [...],
    "tables": [...],
    "figures": [
      {
        "caption": "Figure 1: ...",
        "image_path": "out/figures/paper_figure1.jpg",
        "ocr_text": "..."  // If figure contains text
      }
    ]
  },
  "references_enriched": [
    {
      "title": "...",
      "pmid": "12345678",
      "doi": "10.1234/...",
      "enrichment": {
        "mesh": [...],
        "abstract": "..."
      }
    }
  ],
  "umls_links": [...],      // Filtered medical entities
  "statistics": [...],      // Extracted statistics
  "cross_refs": [...],      // Figure/table references
  "validation": {
    "completeness_score": 85,
    "quality_level": "good",
    "is_valid": true
  }
}
```

## Advanced Features

### Text Normalization (NLP Branch)
```python
from scripts.text_normalize import normalize_for_nlp

# Fixes ligatures, removes inline expansions, de-hyphenates
clean_text = normalize_for_nlp(raw_text)
```

### Semantic Filtering
```python
from scripts.filters import keep

# Only keep clinical concepts
filtered = [e for e in entities if keep(e["text"], e["tui"], e["score"])]
```

### Reference Enrichment
```python
from scripts.ref_enricher import enrich_refs_from_struct

# Enriches with PubMed metadata
enriched = enrich_refs_from_struct(references_struct)
```

## Validation

The pipeline includes comprehensive validation:

- **Metadata**: Title, authors, year, journal
- **Structure**: Sections with content, tables, figures
- **References**: Structured extraction, enrichment coverage
- **Entities**: Medical concept linking
- **Quality Score**: 0-100% completeness rating

Run validation report:
```python
from scripts.validator import validate_extraction, generate_validation_report

validation = validate_extraction(doc)
report = generate_validation_report(validation)
print(report)
```

## Troubleshooting

### Common Issues

1. **GROBID not responding**
   - Ensure Docker container is running: `docker ps`
   - Check port 8070 is accessible
   - Restart: `docker restart <container_id>`

2. **No entities found**
   - Check UMLS_API_KEY is valid
   - Verify text normalization is working
   - Try fallback linkers (QuickUMLS, scispaCy)

3. **Missing figures**
   - Check Docling GPU support is enabled
   - Verify PDF has extractable images
   - Check coordinate system (BOTTOMLEFT vs TOPLEFT)

4. **Reference enrichment failing**
   - Verify NCBI_API_KEY is set
   - Check rate limits (0.1s delay between calls)
   - Some references may not have PMIDs

### Debug Mode
```bash
# Enable debug output
export DEBUG=1
python scripts/process_one.py --pdf input/paper.pdf --out debug.json --linker umls
```

## Performance Tips

- **Batch processing**: Use `run_batch.py` for multiple PDFs
- **Caching**: API responses are cached in `cache/` directory
- **GPU acceleration**: Docling uses GPU if available
- **Limit entities**: Filter candidates before UMLS lookup
- **Local linkers**: QuickUMLS is 10x faster than UMLS API

## Contributing

1. Create feature branch from `main`
2. Implement changes with tests
3. Update documentation
4. Submit pull request

## Citation

If you use this tool in research, please cite:
```
MedParse-Docling: NLP-Hardened Medical Document Extraction Pipeline
https://github.com/your-repo/medparse-docling
```

## License

[Your License Here]

## Support

For issues or questions:
- GitHub Issues: [Create an issue](https://github.com/your-repo/issues)
- Email: support@example.com