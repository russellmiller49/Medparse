# Hardened JSON Schema Documentation

## Overview
Each hardened JSON file contains a fully enriched representation of a scientific article with metadata, structured content, extracted entities, and provenance tracking.

## Top-Level Structure

```json
{
  "metadata": {...},      // Bibliographic metadata
  "structure": {...},     // Document structure and content  
  "provenance": {...},    // Change tracking and data sources
  "grobid": {...},       // GROBID extraction results
  "umls_links": [...],   // Medical concept links
  "drugs": [...],        // Extracted drug mentions
  "trial_ids": [...],    // Clinical trial identifiers
  "assets": {...},       // Tables and figures
  "statistics": [...],   // Statistical findings
  "validation": {...}    // Quality checks and completeness
}
```

## Detailed Field Descriptions

### 1. metadata
Core bibliographic information about the article.

```json
{
  "title": "string",           // Article title
  "year": integer,             // Publication year (e.g., 2018)
  "year_norm": "string",       // Normalized year string
  "authors": [                 // Author list
    {
      "given": "string",       // First/given name(s)
      "family": "string",      // Last/family name
      "suffix": "string|null", // Name suffix (Jr., III, etc.)
      "degrees": [],           // Academic degrees
      "display": "string",     // Full display name
      "group": boolean         // Is group/consortium author
    }
  ],
  "doi": "string",             // Digital Object Identifier (e.g., "10.1016/j.chest.2018.01.048")
  "journal": "string",         // Journal name (abbreviated)
  "journal_full": "string",    // Full journal name
  "volume": "string",          // Volume number
  "issue": "string",           // Issue number  
  "pages": "string",           // Page range (e.g., "1201-1212")
  "issn": "string",            // ISSN number
  "url": "string",             // Article URL
  "abstract": "string",        // Article abstract
  "published": {
    "print": "string|null",    // Print publication date
    "online": "string"         // Online publication date
  },
  "references_text": [],       // Raw reference strings
  "references_raw": [],        // Unprocessed references
  "references_struct": [],     // Structured reference objects
  "references_enriched": [],   // References with added metadata
  "references_source": "string" // Source of references (e.g., "grobid")
}
```

### 2. structure
Document organization and content.

```json
{
  "sections": [                // Document sections
    {
      "title": "string",       // Section heading
      "paragraphs": ["..."],   // Section text content
      "category": "string"     // Section type (e.g., "methods", "results")
    }
  ],
  "tables": [...],             // Extracted tables with data
  "figures": [...],            // Figure references and captions
  "citations": [...],          // In-text citation markers
  "n_sections": integer,       // Count of sections
  "n_tables": integer,         // Count of tables
  "n_figures": integer,        // Count of figures
  "n_citations": integer       // Count of citations
}
```

### 3. provenance
Tracking of all metadata changes and sources.

```json
{
  "patches": [                 // All metadata modifications
    {
      "path": "string",        // JSON path of changed field
      "op": "string",          // Operation (add/replace)
      "from": "any",           // Original value
      "to": "any",             // New value
      "source": "string",      // Data source (e.g., "crossref", "hardening", "zotero")
      "confidence": float      // Confidence score (0-1)
    }
  ],
  "orig_pdf_filename": "string", // Original PDF filename
  "zotero": {                   // Zotero integration details
    "id": "string",
    "source": "string",
    "exported_at": "string",
    "match_method": "string",    // How match was made (doi/title/author-year)
    "match_confidence": float
  }
}
```

### 4. umls_links
Medical concept linking to UMLS (Unified Medical Language System).

```json
[
  {
    "text": "string",          // Original text
    "cui": "string",           // UMLS Concept Unique Identifier
    "preferred_name": "string", // UMLS preferred term
    "semantic_types": ["..."]  // UMLS semantic type codes
  }
]
```

### 5. drugs
Extracted drug/medication mentions.

```json
[
  {
    "name": "string",          // Drug name
    "context": "string",       // Surrounding text
    "section": "string"        // Section where found
  }
]
```

### 6. trial_ids
Clinical trial identifiers found in text.

```json
[
  {
    "id": "string",            // Trial ID (e.g., "NCT01234567")
    "registry": "string",      // Registry name (e.g., "ClinicalTrials.gov")
    "context": "string"        // Surrounding text
  }
]
```

### 7. assets
Tables and figures with structured content.

```json
{
  "tables": [
    {
      "type": "table",
      "content": {...},        // Structured table data
      "captions": [...],       // Table captions
      "footnotes": [...]       // Table footnotes
    }
  ],
  "figures": [
    {
      "type": "figure", 
      "content": {...},        // Figure metadata
      "captions": [...],       // Figure captions
      "footnotes": [...]       // Figure notes
    }
  ]
}
```

### 8. statistics
Statistical findings extracted from text.

```json
[
  {
    "type": "string",          // Statistic type (p-value, CI, etc.)
    "value": "string",         // Statistical value
    "context": "string",       // Surrounding text
    "section": "string"        // Section where found
  }
]
```

### 9. validation
Quality checks and completeness metrics.

```json
{
  "checks": {                  // Individual quality checks
    "has_title": boolean,
    "has_authors": boolean,
    "authors_are_valid": boolean,
    "has_sections": boolean,
    "sections_have_content": boolean,
    "has_tables": boolean,
    "tables_have_captions": boolean,
    "tables_have_data": boolean,
    "has_figures": boolean,
    "figures_have_captions": boolean,
    "figures_have_images": boolean,
    "has_entities": boolean,
    "has_statistics": boolean,
    "has_references": boolean,
    "refs_structured": boolean,
    "refs_enriched_some": boolean,
    "references_enriched": boolean,
    "has_references_csv": boolean,
    "has_cross_refs": boolean,
    "umls_links": boolean
  },
  "completeness_score": integer, // Overall quality score (0-100)
  "is_valid": boolean,           // Passes minimum requirements
  "issues": [],                  // List of problems found
  "warnings": [],                // Non-critical issues
  "quality_level": "string",     // Quality tier (high/medium/low)
  "hardening": {                 // Hardening fixes applied
    "fixes": [
      {
        "field": "string",
        "action": "string",
        "old": "any",
        "new": "any"
      }
    ]
  }
}
```

## Key Metadata Fields for RAG

For a RAG system, the most important metadata fields are:

1. **Identification**
   - `metadata.doi` - Unique article identifier
   - `metadata.title` - Article title
   - `metadata.year` - Publication year

2. **Attribution**
   - `metadata.authors` - Author list
   - `metadata.journal` - Journal name
   - `metadata.volume`, `metadata.issue`, `metadata.pages` - Location details

3. **Content**
   - `metadata.abstract` - Article summary
   - `structure.sections` - Full text organized by section
   - `structure.tables` - Extracted table data
   - `structure.figures` - Figure information

4. **Medical Concepts**
   - `umls_links` - UMLS medical terminology
   - `drugs` - Medication mentions
   - `trial_ids` - Clinical trial references

5. **References**
   - `metadata.references_enriched` - Bibliography with DOIs
   - `structure.citations` - In-text citation markers

6. **Quality/Trust**
   - `validation.completeness_score` - Data quality metric
   - `provenance.patches` - Data source tracking