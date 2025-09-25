# Medparse - Technical Documentation

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [API Reference](#api-reference)
3. [Configuration](#configuration)
4. [Processing Pipeline](#processing-pipeline)
5. [UMLS Integration](#umls-integration)
6. [Development Guide](#development-guide)
7. [Deployment](#deployment)
8. [Troubleshooting](#troubleshooting)

## Architecture Overview

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  Document       │    │   UMLS API      │
│   (Port 8099)   │◄──►│  Processing     │◄──►│   Integration   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Health Check  │    │  Text           │    │   Concept        │
│   Endpoints     │    │  Extraction     │    │   Linking        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Modules

- **`api/`**: FastAPI application and endpoints
- **`medparse/`**: Core document processing library
- **`medparse_ifu/`**: Instructions for Use (IFU) processing
- **`scripts/`**: Processing utilities and tools
- **`schema/`**: Data schemas and validation

### Data Flow

1. **Input**: PDF/text documents → Input directories
2. **Processing**: Document extraction → Text normalization → Chunking
3. **Linking**: UMLS concept identification → Semantic filtering
4. **Output**: Structured JSON with linked concepts

## API Reference

### Base URL
```
http://localhost:8099
```

### Authentication
```bash
X-API-Key: your-secret-key
```

### Endpoints

#### Health Check
```http
GET /healthz
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-25T10:00:00Z",
  "version": "0.1.0"
}
```

#### Text Linking
```http
POST /link
Content-Type: application/json
X-API-Key: your-secret-key
```

**Request:**
```json
{
  "text": "Patient has pneumonia and requires treatment",
  "document_type": "article",
  "focus_terms": ["diagnosis", "treatment"]
}
```

**Response:**
```json
{
  "umls_links": [
    {
      "concept": "Pneumonia",
      "cui": "C0032285",
      "preferred_name": "Pneumonia",
      "semantic_types": ["Disease or Syndrome"],
      "confidence": 0.95
    }
  ],
  "processing_time": 0.234,
  "document_type": "article"
}
```

#### Document Extraction
```http
POST /extract
Content-Type: multipart/form-data
X-API-Key: your-secret-key
```

**Request:**
```
file: document.pdf
document_type: textbook
extract_figures: true
extract_tables: true
```

**Response:**
```json
{
  "document_id": "doc_12345",
  "title": "Medical Textbook Chapter",
  "abstract": "Chapter summary...",
  "sections": [
    {
      "title": "Introduction",
      "content": "Section content...",
      "chunks": [
        {
          "text": "Chunk content...",
          "chunk_id": "chunk_001",
          "metadata": {
            "section": "Introduction",
            "page": 1
          }
        }
      ]
    }
  ],
  "figures": [
    {
      "caption": "Figure 1: Anatomy",
      "figure_id": "fig_001",
      "page": 2
    }
  ],
  "tables": [
    {
      "title": "Table 1: Procedures",
      "table_id": "tbl_001",
      "page": 3
    }
  ],
  "processing_time": 2.456
}
```

### Error Responses

#### 400 Bad Request
```json
{
  "error": "Invalid request format",
  "details": "Missing required field: text"
}
```

#### 401 Unauthorized
```json
{
  "error": "Authentication required",
  "details": "Invalid or missing API key"
}
```

#### 500 Internal Server Error
```json
{
  "error": "Processing failed",
  "details": "UMLS API connection timeout"
}
```

## Configuration

### Environment Variables

```bash
# API Configuration
API_KEY=your-secret-key
API_TITLE=Medparse API
API_VERSION=0.1.0

# UMLS Configuration
UMLS_API_KEY=your-umls-key
UMLS_BASE_URL=https://uts-ws.nlm.nih.gov/rest

# NCBI Configuration
NCBI_API_KEY=your-ncbi-key
NCBI_EMAIL=your-email@example.com

# GROBID Configuration (optional)
GROBID_URL=http://localhost:8070

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:7860,http://localhost:7862

# Upload Configuration
MAX_UPLOAD_MB=40

# Pipeline Configuration
ENABLE_PIPELINE=true
ENABLE_UMLS_LINKING=true
ENABLE_SEMANTIC_FILTERING=true
```

### Processing Settings

#### Document Type Settings
```yaml
document_types:
  article:
    chunk_size: 500
    chunk_overlap: 100
    extract_abstract: true
    extract_references: true
    focus_terms: ["diagnosis", "treatment", "outcomes"]
  
  textbook:
    chunk_size: 1000
    chunk_overlap: 200
    extract_chapters: true
    extract_figures: true
    extract_tables: true
    focus_terms: ["anatomy", "physiology", "pathology"]
  
  guideline:
    chunk_size: 750
    chunk_overlap: 150
    extract_recommendations: true
    extract_evidence_levels: true
    focus_terms: ["recommendations", "evidence", "protocols"]
  
  manual:
    chunk_size: 600
    chunk_overlap: 120
    extract_procedures: true
    extract_steps: true
    focus_terms: ["procedures", "steps", "safety"]
```

## Processing Pipeline

### 1. Document Ingestion
```python
# Input validation
def validate_document(file_path: str, document_type: str) -> bool:
    """Validate document format and type."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document not found: {file_path}")
    
    if document_type not in ["article", "textbook", "guideline", "manual"]:
        raise ValueError(f"Invalid document type: {document_type}")
    
    return True
```

### 2. Text Extraction
```python
# PDF processing
def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF using GROBID or PyPDF2."""
    if GROBID_URL:
        return extract_with_grobid(file_path)
    else:
        return extract_with_pypdf2(file_path)

# Text normalization
def normalize_text(text: str) -> str:
    """Normalize text for processing."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Fix common OCR errors
    text = fix_ocr_errors(text)
    # Normalize medical terms
    text = normalize_medical_terms(text)
    return text
```

### 3. Chunking Strategy
```python
# Semantic chunking
def create_semantic_chunks(text: str, chunk_size: int, overlap: int) -> List[Dict]:
    """Create semantically meaningful chunks."""
    sentences = split_into_sentences(text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) > chunk_size:
            if current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "chunk_id": f"chunk_{len(chunks):03d}",
                    "metadata": extract_metadata(current_chunk)
                })
            current_chunk = sentence
        else:
            current_chunk += " " + sentence
    
    return chunks
```

### 4. UMLS Concept Linking
```python
# Concept identification
def identify_concepts(text: str) -> List[Dict]:
    """Identify UMLS concepts in text."""
    # Extract medical phrases
    phrases = extract_medical_phrases(text)
    
    # Query UMLS API
    concepts = []
    for phrase in phrases:
        umls_results = query_umls_api(phrase)
        for result in umls_results:
            concepts.append({
                "concept": result["concept"],
                "cui": result["cui"],
                "preferred_name": result["preferred_name"],
                "semantic_types": result["semantic_types"],
                "confidence": calculate_confidence(phrase, result)
            })
    
    return concepts
```

## UMLS Integration

### API Configuration
```python
class UMLSClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://uts-ws.nlm.nih.gov/rest"
        self.session = requests.Session()
    
    def search_concepts(self, query: str) -> List[Dict]:
        """Search for UMLS concepts."""
        url = f"{self.base_url}/search/current"
        params = {
            "string": query,
            "apiKey": self.api_key,
            "sabs": "MSH,RXNORM,SNOMEDCT_US"
        }
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json()["result"]["results"]
```

### Semantic Filtering
```python
def apply_semantic_filter(concepts: List[Dict], document_type: str) -> List[Dict]:
    """Filter concepts based on semantic relevance."""
    allowed_types = {
        "article": ["Disease or Syndrome", "Therapeutic or Preventive Procedure"],
        "textbook": ["Anatomical Structure", "Physiologic Function"],
        "guideline": ["Health Care Activity", "Clinical Attribute"],
        "manual": ["Manufactured Object", "Health Care Activity"]
    }
    
    filtered_concepts = []
    for concept in concepts:
        if any(tui in allowed_types.get(document_type, []) for tui in concept.get("semantic_types", [])):
            filtered_concepts.append(concept)
    
    return filtered_concepts
```

## Development Guide

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/your-org/medparse.git
cd medparse

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_umls_linker.py

# Run with coverage
pytest --cov=medparse --cov-report=html

# Run integration tests
pytest tests/integration/
```

### Code Quality
```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .

# Security check
bandit -r .
```

### Adding New Document Types

1. **Update Configuration**:
```yaml
# config/document_types.yaml
new_type:
  chunk_size: 800
  chunk_overlap: 160
  extract_custom_field: true
  focus_terms: ["custom", "terms"]
```

2. **Create Processing Script**:
```python
# scripts/process_new_type.py
def process_new_type_document(file_path: str) -> Dict:
    """Process new document type."""
    # Custom processing logic
    pass
```

3. **Update API Endpoints**:
```python
# api/routers/extract.py
@router.post("/extract")
async def extract_document(
    file: UploadFile,
    document_type: str = "article"
):
    if document_type == "new_type":
        return await process_new_type(file)
    # ... existing logic
```

## Deployment

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8099

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8099"]
```

```bash
# Build image
docker build -t medparse-api .

# Run container
docker run -p 8099:8099 \
  -e UMLS_API_KEY=your-key \
  -e NCBI_API_KEY=your-key \
  medparse-api
```

### Production Deployment

#### Using Gunicorn
```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn api.main:app \
  --bind 0.0.0.0:8099 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker
```

#### Using Nginx
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8099;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Monitoring and Logging

```python
# api/logging.py
import logging
from pythonjsonlogger import jsonlogger

# Configure structured logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)
```

## Troubleshooting

### Common Issues

#### 1. UMLS API Connection Issues
```bash
# Check API key
curl -H "Authorization: apikey your-key" \
  "https://uts-ws.nlm.nih.gov/rest/search/current?string=pneumonia"

# Check network connectivity
ping uts-ws.nlm.nih.gov
```

#### 2. GROBID Connection Issues
```bash
# Check GROBID status
curl http://localhost:8070/api/isalive

# Restart GROBID
docker restart grobid
```

#### 3. Memory Issues
```python
# Monitor memory usage
import psutil

def check_memory():
    memory = psutil.virtual_memory()
    if memory.percent > 90:
        logger.warning(f"High memory usage: {memory.percent}%")
```

#### 4. Processing Timeouts
```python
# Configure timeouts
import asyncio

async def process_with_timeout(coro, timeout=30):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("Processing timeout")
        raise
```

### Performance Optimization

#### 1. Caching
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_umls_concept(cui: str) -> Dict:
    """Cache UMLS concept lookups."""
    return query_umls_api(cui)
```

#### 2. Batch Processing
```python
async def process_documents_batch(files: List[str]) -> List[Dict]:
    """Process multiple documents concurrently."""
    tasks = [process_document(file) for file in files]
    return await asyncio.gather(*tasks)
```

#### 3. Database Optimization
```python
# Use connection pooling
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20
)
```

### Debugging

#### Enable Debug Mode
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
uvicorn api.main:app --reload --log-level debug
```

#### API Testing
```bash
# Test health endpoint
curl http://localhost:8099/healthz

# Test text linking
curl -X POST http://localhost:8099/link \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"text": "Patient has pneumonia"}'

# Test document extraction
curl -X POST http://localhost:8099/extract \
  -H "X-API-Key: your-key" \
  -F "file=@test.pdf"
```

#### Log Analysis
```bash
# View logs
tail -f logs/medparse.log

# Search for errors
grep "ERROR" logs/medparse.log

# Monitor API calls
grep "POST /link" logs/medparse.log
```
