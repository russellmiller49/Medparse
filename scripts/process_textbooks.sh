#!/bin/bash

# Medparse Document Processor - Textbooks
# Optimized for processing medical textbooks and comprehensive references

set -e

echo "📚 Medparse - Textbook Processor"
echo "================================="

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

# Check for textbooks
echo "📚 Checking for textbooks..."
pdf_count=$(find input/textbooks/pdf -name "*.pdf" 2>/dev/null | wc -l)
text_count=$(find input/textbooks/text -name "*.txt" 2>/dev/null | wc -l)

if [ $pdf_count -eq 0 ] && [ $text_count -eq 0 ]; then
    echo "⚠️  No textbooks found in input/textbooks/"
    echo "   Please add your textbook PDFs to input/textbooks/pdf/"
    echo "   Or add text files to input/textbooks/text/"
    echo "   Then run this script again."
    exit 1
fi

echo "📊 Found $pdf_count textbook PDFs and $text_count text files"

# Process PDF textbooks
if [ $pdf_count -gt 0 ]; then
    echo "📚 Processing textbook PDFs..."
    
    for pdf_file in input/textbooks/pdf/*.pdf; do
        if [ -f "$pdf_file" ]; then
            filename=$(basename "$pdf_file" .pdf)
            echo "📚 Processing textbook: $filename"
            
            # Extract text and concepts with textbook-specific settings
            curl -X POST "http://127.0.0.1:8099/extract" \
              -H "Content-Type: multipart/form-data" \
              -H "X-API-Key: my-secret-medparse-key-123" \
              -F "file=@$pdf_file" \
              -F "document_type=textbook" \
              -F "extract_chapters=true" \
              -F "extract_figures=true" \
              -F "extract_tables=true" \
              -F "extract_index=true" \
              -o "output/textbooks/${filename}_extracted.json"
            
            # Link UMLS concepts for textbooks
            if [ -f "output/textbooks/${filename}_extracted.json" ]; then
                echo "🔗 Linking UMLS concepts for textbook: $filename"
                python scripts/link_document.py \
                  "output/textbooks/${filename}_extracted.json" \
                  "output/textbooks/${filename}_linked.json" \
                  --document_type=textbook \
                  --focus_terms="anatomy,physiology,pathology,treatment,diagnosis,procedures"
            fi
        fi
    done
fi

# Process text textbooks
if [ $text_count -gt 0 ]; then
    echo "📝 Processing text textbooks..."
    
    for text_file in input/textbooks/text/*.txt; do
        if [ -f "$text_file" ]; then
            filename=$(basename "$text_file" .txt)
            echo "📝 Processing text textbook: $filename"
            
            # Process text directly
            python scripts/process_text.py \
              "$text_file" \
              "output/textbooks/${filename}_processed.json" \
              --document_type=textbook
        fi
    done
fi

echo ""
echo "✅ Textbook processing completed!"
echo ""
echo "📊 Processed files are in the output/textbooks/ directory"
echo "🔍 To view results:"
echo "   ls -la output/textbooks/"
echo ""
echo "📈 Textbook-specific features processed:"
echo "   • Chapter structure and organization"
echo "   • Figure and table extraction"
echo "   • Comprehensive terminology coverage"
echo "   • Educational content highlighting"
echo "   • Cross-references and indexing"
