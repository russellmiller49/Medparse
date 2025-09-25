#!/bin/bash

# Medparse Document Processor - Articles
# Optimized for processing medical journal articles

set -e

echo "📄 Medparse - Article Processor"
echo "==============================="

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

# Check for articles
echo "📄 Checking for articles..."
pdf_count=$(find input/articles/pdf -name "*.pdf" 2>/dev/null | wc -l)
text_count=$(find input/articles/text -name "*.txt" 2>/dev/null | wc -l)

if [ $pdf_count -eq 0 ] && [ $text_count -eq 0 ]; then
    echo "⚠️  No articles found in input/articles/"
    echo "   Please add your article PDFs to input/articles/pdf/"
    echo "   Or add text files to input/articles/text/"
    echo "   Then run this script again."
    exit 1
fi

echo "📊 Found $pdf_count article PDFs and $text_count text files"

# Process PDF articles
if [ $pdf_count -gt 0 ]; then
    echo "📄 Processing article PDFs..."
    
    for pdf_file in input/articles/pdf/*.pdf; do
        if [ -f "$pdf_file" ]; then
            filename=$(basename "$pdf_file" .pdf)
            echo "📄 Processing article: $filename"
            
            # Extract text and concepts with article-specific settings
            curl -X POST "http://127.0.0.1:8099/extract" \
              -H "Content-Type: multipart/form-data" \
              -H "X-API-Key: my-secret-medparse-key-123" \
              -F "file=@$pdf_file" \
              -F "document_type=article" \
              -F "extract_abstract=true" \
              -F "extract_references=true" \
              -o "output/articles/${filename}_extracted.json"
            
            # Link UMLS concepts for articles
            if [ -f "output/articles/${filename}_extracted.json" ]; then
                echo "🔗 Linking UMLS concepts for article: $filename"
                python scripts/link_document.py \
                  "output/articles/${filename}_extracted.json" \
                  "output/articles/${filename}_linked.json" \
                  --document_type=article \
                  --focus_terms="diagnosis,treatment,outcomes,complications"
            fi
        fi
    done
fi

# Process text articles
if [ $text_count -gt 0 ]; then
    echo "📝 Processing text articles..."
    
    for text_file in input/articles/text/*.txt; do
        if [ -f "$text_file" ]; then
            filename=$(basename "$text_file" .txt)
            echo "📝 Processing text article: $filename"
            
            # Process text directly
            python scripts/process_text.py \
              "$text_file" \
              "output/articles/${filename}_processed.json" \
              --document_type=article
        fi
    done
fi

echo ""
echo "✅ Article processing completed!"
echo ""
echo "📊 Processed files are in the output/articles/ directory"
echo "🔍 To view results:"
echo "   ls -la output/articles/"
echo ""
echo "📈 Article-specific features processed:"
echo "   • Abstracts and structured summaries"
echo "   • Reference extraction and linking"
echo "   • Clinical terminology focus"
echo "   • Evidence-based content highlighting"
