# Medparse - Medical Document Processing API

A powerful FastAPI-based service for processing medical documents, extracting structured content, and linking medical concepts to UMLS (Unified Medical Language System).

## 🏥 Overview

Medparse is designed to transform unstructured medical documents into structured, searchable, and semantically enriched data. It supports multiple document types with specialized processing optimized for medical content.

## ✨ Key Features

- **📄 Multi-Format Support**: Process PDFs and text files
- **🔗 UMLS Integration**: Link medical concepts to standardized terminology
- **🎯 Document Type Optimization**: Specialized processing for articles, textbooks, guidelines, and manuals
- **🚀 Fast API**: RESTful API with automatic documentation
- **🧠 Semantic Filtering**: Intelligent concept filtering based on document context
- **📊 Structured Output**: JSON output with metadata, citations, and linked concepts

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- UMLS API key (optional)
- NCBI API key (optional)

### Installation
```bash
git clone https://github.com/your-org/medparse.git
cd medparse
pip install -r requirements.txt
```

### Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### Start the API
```bash
uvicorn api.main:app --reload --port 8099
```

### Test the API
```bash
curl http://localhost:8099/healthz
```

## 📚 Document Types

### 🔬 Articles
- **Purpose**: Medical journal articles, research papers, case studies
- **Features**: Abstract extraction, reference linking, clinical terminology focus
- **Processing**: `./scripts/process_articles.sh`

### 📖 Textbooks  
- **Purpose**: Medical textbooks, comprehensive references, educational materials
- **Features**: Chapter structure, figure/table extraction, comprehensive terminology
- **Processing**: `./scripts/process_textbooks.sh`

### 📋 Guidelines
- **Purpose**: Clinical practice guidelines, protocols, standards
- **Features**: Recommendation extraction, evidence levels, clinical algorithms
- **Processing**: `./scripts/process_guidelines.sh`

### 📖 Manuals
- **Purpose**: Procedural manuals, technical documentation, equipment guides
- **Features**: Step-by-step procedures, safety warnings, troubleshooting
- **Processing**: `./scripts/process_manuals.sh`

## 🏗️ Directory Structure

```
medparse/
├── api/                    # FastAPI application
│   ├── main.py            # Main application
│   ├── routers/           # API endpoints
│   └── models.py          # Data models
├── medparse/              # Core processing library
│   ├── extract/           # Text extraction
│   ├── linking/           # UMLS concept linking
│   └── layout/            # Document layout analysis
├── scripts/               # Processing utilities
│   ├── process_articles.sh      # Article processing
│   ├── process_textbooks.sh     # Textbook processing
│   ├── process_guidelines.sh    # Guidelines processing
│   ├── process_manuals.sh       # Manual processing
│   └── process_all_documents.sh # Process all types
├── input/                 # Organized input directories
│   ├── articles/          # Article PDFs and text
│   ├── textbooks/         # Textbook PDFs and text
│   ├── guidelines/        # Guideline PDFs and text
│   └── manuals/           # Manual PDFs and text
├── output/                # Processed documents
├── schema/                # Data schemas
└── tests/                 # Test suite
```

## 🔧 API Endpoints

### Health Check
```http
GET /healthz
```

### Text Linking
```http
POST /link
Content-Type: application/json
X-API-Key: your-secret-key

{
  "text": "Patient has pneumonia and requires treatment",
  "document_type": "article"
}
```

### Document Extraction
```http
POST /extract
Content-Type: multipart/form-data
X-API-Key: your-secret-key

file: document.pdf
document_type: textbook
```

## 🔄 Processing Workflow

1. **📁 Organize Documents**: Place documents in appropriate input directories
2. **⚙️ Process Documents**: Run processing scripts for your document types
3. **📊 Review Results**: Check output directories for processed JSON files
4. **🔗 Integrate**: Use processed documents with IP Assist Lite or other systems

## ⚙️ Configuration

### Environment Variables
```bash
# API Configuration
API_KEY=your-secret-key
UMLS_API_KEY=your-umls-key
NCBI_API_KEY=your-ncbi-key

# Processing Settings
MAX_UPLOAD_MB=40
ENABLE_UMLS_LINKING=true
ENABLE_SEMANTIC_FILTERING=true
```

### Document Type Settings
```yaml
document_types:
  article:
    chunk_size: 500
    extract_abstract: true
    focus_terms: ["diagnosis", "treatment"]
  textbook:
    chunk_size: 1000
    extract_chapters: true
    focus_terms: ["anatomy", "physiology"]
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific tests
pytest tests/test_umls_linker.py

# Run with coverage
pytest --cov=medparse --cov-report=html
```

## 🚀 Deployment

### Docker
```bash
docker build -t medparse-api .
docker run -p 8099:8099 medparse-api
```

### Production
```bash
gunicorn api.main:app --bind 0.0.0.0:8099 --workers 4
```

## 🔗 Integration

### With IP Assist Lite
```bash
# Process documents with medparse
./scripts/process_all_documents.sh

# Copy to IP Assist Lite
cp output/*/*.json ../IP_assist_lite/data/processed/
```

### API Integration
```python
import requests

response = requests.post(
    "http://localhost:8099/link",
    headers={"X-API-Key": "your-key"},
    json={"text": "Patient has pneumonia"}
)
concepts = response.json()["umls_links"]
```

## 📖 Documentation

- **[Technical Documentation](TECHNICAL_DOCUMENTATION.md)**: Detailed technical reference
- **[User Guide](USER_GUIDE.md)**: Step-by-step usage instructions
- **[API Reference](http://localhost:8099/docs)**: Interactive API documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/medparse/issues)
- **Documentation**: See documentation files in the repository
- **Email**: support@your-org.com

## 🔄 Changelog

### Latest Version
- ✅ Structured input directories by document type
- ✅ Document-specific processing scripts
- ✅ Enhanced UMLS concept linking
- ✅ Improved semantic filtering
- ✅ Comprehensive documentation

---

**Ready to process your medical documents with advanced NLP and medical concept linking!** 🏥📄✨