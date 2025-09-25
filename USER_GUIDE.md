# Medparse - User Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Document Processing](#document-processing)
3. [API Usage](#api-usage)
4. [Configuration](#configuration)
5. [Best Practices](#best-practices)
6. [Examples](#examples)
7. [FAQ](#faq)

## Getting Started

### Prerequisites

- Python 3.11+
- Docker (optional, for GROBID)
- UMLS API key (optional)
- NCBI API key (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/medparse.git
cd medparse

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration
```

### Quick Start

```bash
# Start the API server
uvicorn api.main:app --reload --port 8099

# Test the API
curl http://localhost:8099/healthz
```

## Document Processing

### Document Types

Medparse supports four main document types, each optimized for specific content:

#### 1. Articles (`articles/`)
- **Purpose**: Medical journal articles, research papers, case studies
- **Features**: Abstract extraction, reference linking, clinical terminology focus
- **Best for**: Evidence-based medicine, research findings, case studies

#### 2. Textbooks (`textbooks/`)
- **Purpose**: Medical textbooks, comprehensive references, educational materials
- **Features**: Chapter structure, figure/table extraction, comprehensive terminology
- **Best for**: Educational content, comprehensive medical knowledge

#### 3. Guidelines (`guidelines/`)
- **Purpose**: Clinical practice guidelines, protocols, standards
- **Features**: Recommendation extraction, evidence levels, clinical algorithms
- **Best for**: Clinical decision support, protocol adherence

#### 4. Manuals (`manuals/`)
- **Purpose**: Procedural manuals, technical documentation, equipment guides
- **Features**: Step-by-step procedures, safety warnings, troubleshooting
- **Best for**: Procedural guidance, equipment operation, safety protocols

### Processing Workflow

#### Step 1: Organize Your Documents

```
input/
├── articles/
│   ├── pdf/
│   │   ├── research_paper_1.pdf
│   │   └── case_study_2.pdf
│   └── text/
│       └── article_3.txt
├── textbooks/
│   ├── pdf/
│   │   └── medical_textbook.pdf
│   └── text/
│       └── textbook_chapter.txt
├── guidelines/
│   ├── pdf/
│   │   └── clinical_guideline.pdf
│   └── text/
│       └── protocol.txt
└── manuals/
    ├── pdf/
    │   └── procedure_manual.pdf
    └── text/
        └── equipment_guide.txt
```

#### Step 2: Process Documents

```bash
# Process all document types
./scripts/process_all_documents.sh

# Process specific types
./scripts/process_articles.sh
./scripts/process_textbooks.sh
./scripts/process_guidelines.sh
./scripts/process_manuals.sh
```

#### Step 3: Review Results

```bash
# Check processed files
ls -la output/articles/
ls -la output/textbooks/
ls -la output/guidelines/
ls -la output/manuals/
```

## API Usage

### Authentication

All API requests require an API key:

```bash
# Set your API key
export MEDPARSE_API_KEY="your-secret-key"

# Or include in requests
curl -H "X-API-Key: your-secret-key" ...
```

### Text Linking

Link medical concepts in text to UMLS:

```bash
curl -X POST "http://localhost:8099/link" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "text": "Patient has pneumonia and requires antibiotic treatment",
    "document_type": "article",
    "focus_terms": ["diagnosis", "treatment"]
  }'
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
    },
    {
      "concept": "Antibiotic",
      "cui": "C0003239",
      "preferred_name": "Antibiotic",
      "semantic_types": ["Pharmacologic Substance"],
      "confidence": 0.89
    }
  ],
  "processing_time": 0.234,
  "document_type": "article"
}
```

### Document Extraction

Extract structured content from PDFs:

```bash
curl -X POST "http://localhost:8099/extract" \
  -H "X-API-Key: your-secret-key" \
  -F "file=@medical_article.pdf" \
  -F "document_type=article" \
  -F "extract_abstract=true" \
  -F "extract_references=true"
```

**Response:**
```json
{
  "document_id": "doc_12345",
  "title": "Treatment of Community-Acquired Pneumonia",
  "abstract": "This study evaluates the effectiveness of...",
    "sections": [
      {
        "title": "Introduction",
      "content": "Community-acquired pneumonia (CAP) is...",
      "chunks": [
        {
          "text": "Community-acquired pneumonia (CAP) is a common...",
          "chunk_id": "chunk_001",
          "metadata": {
            "section": "Introduction",
            "page": 1,
            "umls_links": [
              {
                "concept": "Community-Acquired Pneumonia",
                "cui": "C0032285",
                "confidence": 0.92
              }
            ]
          }
        }
      ]
    }
  ],
  "references": [
    {
      "title": "Clinical Practice Guidelines",
      "authors": ["Smith, J.", "Doe, A."],
      "year": 2023,
      "doi": "10.1000/example"
    }
  ],
  "processing_time": 2.456
}
```

### Health Check

Monitor API status:

```bash
curl http://localhost:8099/healthz
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-25T10:00:00Z",
  "version": "0.1.0",
  "services": {
    "umls_api": "connected",
    "grobid": "connected",
    "database": "connected"
  }
}
```

## Configuration

### Environment Variables

Create a `.env` file with your configuration:

```bash
# API Configuration
API_KEY=your-secret-key
API_TITLE=Medparse API
API_VERSION=0.1.0

# UMLS Configuration (optional)
UMLS_API_KEY=your-umls-key
NCBI_API_KEY=your-ncbi-key
NCBI_EMAIL=your-email@example.com

# GROBID Configuration (optional)
GROBID_URL=http://localhost:8070

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:7860,http://localhost:7862

# Upload Configuration
MAX_UPLOAD_MB=40

# Processing Configuration
ENABLE_PIPELINE=true
ENABLE_UMLS_LINKING=true
ENABLE_SEMANTIC_FILTERING=true
```

### Document Type Settings

Customize processing for different document types:

```yaml
# config/document_types.yaml
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

## Best Practices

### Document Preparation

1. **Use High-Quality PDFs**: Ensure PDFs are text-based, not scanned images
2. **Organize by Type**: Place documents in appropriate type directories
3. **Use Descriptive Names**: Use clear, descriptive filenames
4. **Check File Sizes**: Keep files under 40MB for optimal processing

### Processing Strategy

1. **Process in Batches**: Process documents by type for better organization
2. **Monitor API Status**: Check health endpoint before processing
3. **Review Results**: Always review processed outputs for quality
4. **Handle Errors**: Implement proper error handling in your workflows

### Performance Optimization

1. **Use Appropriate Chunk Sizes**: Adjust chunk sizes based on document type
2. **Enable Caching**: Use caching for repeated concept lookups
3. **Batch Processing**: Process multiple documents concurrently
4. **Monitor Resources**: Keep an eye on memory and CPU usage

## Examples

### Example 1: Processing Medical Articles

```bash
# 1. Place articles in input directory
cp medical_articles/*.pdf input/articles/pdf/

# 2. Process articles
./scripts/process_articles.sh

# 3. Check results
ls -la output/articles/
cat output/articles/article_1_linked.json | jq '.umls_links'
```

### Example 2: Processing Clinical Guidelines

```bash
# 1. Place guidelines in input directory
cp clinical_guidelines/*.pdf input/guidelines/pdf/

# 2. Process guidelines
./scripts/process_guidelines.sh

# 3. Extract recommendations
jq '.recommendations' output/guidelines/guideline_1_linked.json
```

### Example 3: API Integration

```python
import requests
import json

# Configure API
API_BASE = "http://localhost:8099"
API_KEY = "your-secret-key"

# Link medical concepts
def link_concepts(text, document_type="article"):
    response = requests.post(
        f"{API_BASE}/link",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        },
        json={
            "text": text,
            "document_type": document_type
        }
    )
    return response.json()

# Extract document content
def extract_document(file_path, document_type="article"):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {'document_type': document_type}
        headers = {'X-API-Key': API_KEY}
        
        response = requests.post(
            f"{API_BASE}/extract",
            files=files,
            data=data,
            headers=headers
        )
    return response.json()

# Example usage
concepts = link_concepts("Patient has pneumonia")
print(f"Found {len(concepts['umls_links'])} concepts")

document = extract_document("medical_article.pdf")
print(f"Extracted {len(document['sections'])} sections")
```

### Example 4: Batch Processing

```python
import os
import asyncio
import aiohttp

async def process_documents_batch(document_dir, document_type):
    """Process multiple documents concurrently."""
    files = [f for f in os.listdir(document_dir) if f.endswith('.pdf')]
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for file in files:
            task = process_document(session, file, document_type)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return results

async def process_document(session, file_path, document_type):
    """Process a single document."""
    with open(file_path, 'rb') as f:
        data = aiohttp.FormData()
        data.add_field('file', f, filename=file_path)
        data.add_field('document_type', document_type)
        
        async with session.post(
            'http://localhost:8099/extract',
            data=data,
            headers={'X-API-Key': 'your-secret-key'}
        ) as response:
            return await response.json()

# Process all articles
results = asyncio.run(process_documents_batch('input/articles/pdf/', 'article'))
print(f"Processed {len(results)} articles")
```

## FAQ

### Q: What file formats are supported?
A: Medparse supports PDF and plain text files. For PDFs, text-based PDFs work best. Scanned PDFs may require OCR preprocessing.

### Q: How do I get UMLS API access?
A: UMLS API access requires registration at https://uts.nlm.nih.gov/. You'll need to agree to their terms of use and provide your email address.

### Q: Can I process documents without UMLS linking?
A: Yes, you can disable UMLS linking by setting `ENABLE_UMLS_LINKING=false` in your environment variables.

### Q: What's the difference between document types?
A: Each document type has optimized processing settings:
- **Articles**: Focus on abstracts, references, clinical terminology
- **Textbooks**: Focus on chapters, figures, comprehensive coverage
- **Guidelines**: Focus on recommendations, evidence levels, algorithms
- **Manuals**: Focus on procedures, steps, safety warnings

### Q: How can I improve processing accuracy?
A: 
1. Use high-quality, text-based PDFs
2. Ensure proper document type classification
3. Use appropriate chunk sizes for your content
4. Enable semantic filtering for better concept relevance

### Q: Can I customize the processing pipeline?
A: Yes, you can modify the processing scripts and configuration files to customize the pipeline for your specific needs.

### Q: How do I handle large documents?
A: Large documents are automatically chunked during processing. You can adjust chunk sizes in the configuration to optimize for your use case.

### Q: What if processing fails?
A: Check the logs for error messages, verify your API keys are correct, and ensure the medparse API is running. Common issues include network connectivity, invalid file formats, or API rate limits.

### Q: Can I integrate medparse with other systems?
A: Yes, medparse provides a REST API that can be integrated with any system that can make HTTP requests. The API returns structured JSON data that can be easily processed by other applications.

### Q: How do I monitor API performance?
A: Use the health check endpoint (`/healthz`) to monitor API status. You can also check the processing time in API responses and monitor server resources.