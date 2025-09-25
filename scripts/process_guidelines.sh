#!/bin/bash

# Medparse Document Processor - Guidelines
# Optimized for processing clinical practice guidelines

set -e

echo "📋 Medparse - Guidelines Processor"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: Please run this script from the medparse-docling root directory"
    exit 1
fi

# Check if API is running
echo "🔍 Checking medparse API..."
if curl -s http://127.0.0.1:8099/healthz > /dev/null; then
    echo "✅ Medparse API is running"
else
    echo "❌ Medparse API is not running. Please start it first:"
    echo "   uvicorn api.main:app --reload --port 8099"
    exit 1
fi

# Check for guidelines
echo "📋 Checking for guidelines..."
pdf_count=$(find input/guidelines/pdf -name "*.pdf" 2>/dev/null | wc -l)
text_count=$(find input/guidelines/text -name "*.txt" 2>/dev/null | wc -l)

if [ $pdf_count -eq 0 ] && [ $text_count -eq 0 ]; then
    echo "⚠️  No guidelines found in input/guidelines/"
    echo "   Please add your guideline PDFs to input/guidelines/pdf/"
    echo "   Or add text files to input/guidelines/text/"
    echo "   Then run this script again."
    exit 1
fi

echo "📊 Found $pdf_count guideline PDFs and $text_count text files"

# Process PDF guidelines
if [ $pdf_count -gt 0 ]; then
    echo "📋 Processing guideline PDFs..."
    
    for pdf_file in input/guidelines/pdf/*.pdf; do
        if [ -f "$pdf_file" ]; then
            filename=$(basename "$pdf_file" .pdf)
            echo "📋 Processing guideline: $filename"
            
            # Extract text and concepts with guideline-specific settings
            curl -X POST "http://127.0.0.1:8099/extract" \
              -H "Content-Type: multipart/form-data" \
              -H "X-API-Key: my-secret-medparse-key-123" \
              -F "file=@$pdf_file" \
              -F "document_type=guideline" \
              -F "extract_recommendations=true" \
              -F "extract_evidence_levels=true" \
              -F "extract_algorithms=true" \
              -o "output/guidelines/${filename}_extracted.json"
            
            # Link UMLS concepts for guidelines
            if [ -f "output/guidelines/${filename}_extracted.json" ]; then
                echo "🔗 Linking UMLS concepts for guideline: $filename"
                python scripts/link_document.py \
                  "output/guidelines/${filename}_extracted.json" \
                  "output/guidelines/${filename}_linked.json" \
                  --document_type=guideline \
                  --focus_terms="recommendations,evidence,algorithms,protocols,standards"
            fi
        fi
    done
fi

# Process text guidelines
if [ $text_count -gt 0 ]; then
    echo "📝 Processing text guidelines..."
    
    for text_file in input/guidelines/text/*.txt; do
        if [ -f "$text_file" ]; then
            filename=$(basename "$text_file" .txt)
            echo "📝 Processing text guideline: $filename"
            
            # Process text directly
            python scripts/process_text.py \
              "$text_file" \
              "output/guidelines/${filename}_processed.json" \
              --document_type=guideline
        fi
    done
fi

echo ""
echo "✅ Guidelines processing completed!"
echo ""
echo "📊 Processed files are in the output/guidelines/ directory"
echo "🔍 To view results:"
echo "   ls -la output/guidelines/"
echo ""
echo "📈 Guideline-specific features processed:"
echo "   • Recommendation extraction and grading"
echo "   • Evidence level identification"
echo "   • Clinical algorithms and decision trees"
echo "   • Protocol and standard extraction"
echo "   • Quality indicators and metrics"
