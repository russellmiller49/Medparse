# Medparse - Clean Repository

This is a clean version of Medparse designed for processing medical documents and building knowledge bases.

## What's Included

- **Core API**: FastAPI-based medical text processing
- **UMLS Integration**: Medical concept linking
- **PDF Processing**: Document extraction and parsing
- **Text Processing**: Medical text normalization and chunking

## What's Removed

- Specific input documents
- Generated outputs and cache
- Test data and figures
- Batch processing scripts
- Debug and analysis scripts

## Quick Start

### 1. Setup Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export UMLS_API_KEY="your-umls-key"
export NCBI_API_KEY="your-ncbi-key"
export NCBI_EMAIL="your-email@example.com"
export GROBID_URL="http://localhost:8070"  # Optional
export API_KEY="your-secret-key"
```

### 2. Start the API

```bash
uvicorn api.main:app --reload --port 8099
```

### 3. Test the API

```bash
curl -X POST "http://localhost:8099/link" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"text": "Patient has pneumonia and requires treatment"}'
```

## Processing Your Documents

### Step 1: Prepare Documents

Organize your documents by type in the structured input directories:

1. **Articles**: Place medical journal articles in `input/articles/pdf/` or `input/articles/text/`
2. **Textbooks**: Place medical textbooks in `input/textbooks/pdf/` or `input/textbooks/text/`
3. **Guidelines**: Place clinical guidelines in `input/guidelines/pdf/` or `input/guidelines/text/`
4. **Manuals**: Place procedural manuals in `input/manuals/pdf/` or `input/manuals/text/`

### Step 2: Process Documents

```bash
# Process all document types
./scripts/process_all_documents.sh

# Process specific document types
./scripts/process_articles.sh      # Medical articles
./scripts/process_textbooks.sh     # Medical textbooks
./scripts/process_guidelines.sh    # Clinical guidelines
./scripts/process_manuals.sh       # Procedural manuals
```

### Step 3: Extract Medical Concepts

```bash
# Link UMLS concepts
python scripts/link_umls.py output/processed_documents/

# Apply semantic filtering
python scripts/apply_filters.py output/linked_documents/
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8099/healthz
```

### Text Linking
```bash
curl -X POST "http://localhost:8099/link" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"text": "Your medical text here"}'
```

### Document Extraction
```bash
curl -X POST "http://localhost:8099/extract" \
  -H "Content-Type: multipart/form-data" \
  -H "X-API-Key: your-secret-key" \
  -F "file=@your_document.pdf"
```

## Configuration

### Environment Variables
- `UMLS_API_KEY`: UMLS API key for concept linking
- `NCBI_API_KEY`: NCBI API key for PubMed enrichment
- `GROBID_URL`: GROBID server URL for PDF parsing
- `API_KEY`: Secret key for API authentication
- `MAX_UPLOAD_MB`: Maximum file upload size (default: 40MB)

### API Configuration
Edit `api/config.py` to customize:
- CORS settings
- Upload limits
- Processing pipelines
- Logging levels

## Integration with IP Assist Lite

This clean medparse repository is designed to work seamlessly with the clean IP Assist Lite repository:

1. **Start Medparse**: `uvicorn api.main:app --reload --port 8099`
2. **Start IP Assist Lite**: `./run.sh`
3. **Configure Connection**: Set `MEDPARSE_URL=http://127.0.0.1:8099` in IP Assist Lite

## Customization

### Medical Domains
- **Pulmonology**: Lung procedures and conditions
- **Cardiology**: Heart and vascular procedures
- **Gastroenterology**: Digestive system procedures
- **Urology**: Urinary system procedures

### Processing Options
- **UMLS Linking**: Enable/disable concept linking
- **Semantic Filtering**: Customize filtering rules
- **Text Normalization**: Adjust normalization settings
- **Chunking Strategy**: Modify text chunking parameters

## Development

### Running Tests
```bash
pytest tests/
```

### Code Quality
```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

## Support

- Check `README.md` for detailed documentation
- Review `api/` for API implementation
- See `scripts/` for processing utilities
- Check `tests/` for usage examples

---

**Ready to process your medical documents!** 🏥📄
