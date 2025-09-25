# Medparse Input Structure

This directory contains organized input folders for different types of medical documents.

## Directory Structure

```
input/
├── articles/           # Medical journal articles
│   ├── pdf/           # PDF articles
│   └── text/          # Text articles
├── textbooks/         # Medical textbooks and references
│   ├── pdf/           # PDF textbooks
│   └── text/          # Text textbooks
├── guidelines/        # Clinical practice guidelines
│   ├── pdf/           # PDF guidelines
│   └── text/          # Text guidelines
└── manuals/           # Procedural manuals and technical docs
    ├── pdf/           # PDF manuals
    └── text/          # Text manuals
```

## Document Types

### Articles (`input/articles/`)
- **Purpose**: Medical journal articles, research papers, case studies
- **Processing**: Focus on abstracts, references, clinical terminology
- **Script**: `scripts/process_articles.sh`
- **Features**: 
  - Abstract extraction
  - Reference linking
  - Evidence-based content highlighting
  - Clinical terminology focus

### Textbooks (`input/textbooks/`)
- **Purpose**: Medical textbooks, comprehensive references, educational materials
- **Processing**: Focus on chapters, figures, comprehensive terminology
- **Script**: `scripts/process_textbooks.sh`
- **Features**:
  - Chapter structure extraction
  - Figure and table extraction
  - Comprehensive terminology coverage
  - Cross-references and indexing

### Guidelines (`input/guidelines/`)
- **Purpose**: Clinical practice guidelines, protocols, standards
- **Processing**: Focus on recommendations, evidence levels, algorithms
- **Script**: `scripts/process_guidelines.sh`
- **Features**:
  - Recommendation extraction and grading
  - Evidence level identification
  - Clinical algorithms and decision trees
  - Protocol and standard extraction

### Manuals (`input/manuals/`)
- **Purpose**: Procedural manuals, technical documentation, equipment guides
- **Processing**: Focus on procedures, steps, safety warnings
- **Script**: `scripts/process_manuals.sh`
- **Features**:
  - Step-by-step procedure extraction
  - Safety warnings and precautions
  - Troubleshooting guides
  - Equipment and technique details

## Usage

### Process All Documents
```bash
./scripts/process_all_documents.sh
```

### Process Specific Document Types
```bash
# Process only articles
./scripts/process_articles.sh

# Process only textbooks
./scripts/process_textbooks.sh

# Process only guidelines
./scripts/process_guidelines.sh

# Process only manuals
./scripts/process_manuals.sh
```

## Output Structure

Processed documents are saved to corresponding output directories:

```
output/
├── articles/          # Processed articles
├── textbooks/         # Processed textbooks
├── guidelines/        # Processed guidelines
└── manuals/          # Processed manuals
```

## File Naming Conventions

- **PDFs**: `filename.pdf` → `filename_extracted.json` → `filename_linked.json`
- **Text**: `filename.txt` → `filename_processed.json`

## Tips

1. **Organize by Type**: Place documents in the appropriate folder based on their content type
2. **Use Descriptive Names**: Use clear, descriptive filenames for easier identification
3. **Check API Status**: Ensure the medparse API is running before processing
4. **Monitor Output**: Check the output directories for processed results
5. **Review Results**: Examine the JSON output to ensure proper processing

## Integration with IP Assist Lite

Processed documents can be integrated with IP Assist Lite for building knowledge bases:

1. **Process Documents**: Use the appropriate processing script
2. **Export to IP Assist Lite**: Copy processed JSON files to IP Assist Lite's data directory
3. **Build Knowledge Base**: Use IP Assist Lite's knowledge base builder
4. **Deploy**: Deploy the complete system with your custom knowledge base
