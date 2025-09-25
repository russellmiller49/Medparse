#!/bin/bash

# Medparse Document Processor
# This script helps process documents through the medparse API

set -e

echo "🏥 Medparse - Document Processor"
echo "================================"

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: Please run this script from the medparse-docling root directory"
    exit 1
fi

# Create necessary directories
echo "📁 Creating directory structure..."
mkdir -p input
mkdir -p output
mkdir -p processed

# Check if API is running
echo "🔍 Checking medparse API..."
if curl -s http://127.0.0.1:8099/healthz > /dev/null; then
    echo "✅ Medparse API is running"
else
    echo "❌ Medparse API is not running. Please start it first:"
    echo "   uvicorn api.main:app --reload --port 8099"
    exit 1
fi

# Check for documents
echo "📄 Checking for documents..."
pdf_count=$(find input -name "*.pdf" 2>/dev/null | wc -l)

if [ $pdf_count -eq 0 ]; then
    echo "⚠️  No PDF documents found in input/"
    echo "   Please add your PDF documents to the input/ directory"
    echo "   Then run this script again."
    exit 1
fi

echo "📊 Found $pdf_count PDF files"

# Process documents
echo "🔄 Processing documents..."

for pdf_file in input/*.pdf; do
    if [ -f "$pdf_file" ]; then
        filename=$(basename "$pdf_file" .pdf)
        echo "📄 Processing: $filename"
        
        # Extract text and concepts
        curl -X POST "http://127.0.0.1:8099/extract" \
          -H "Content-Type: multipart/form-data" \
          -H "X-API-Key: my-secret-medparse-key-123" \
          -F "file=@$pdf_file" \
          -o "output/${filename}_extracted.json"
        
        # Link UMLS concepts
        if [ -f "output/${filename}_extracted.json" ]; then
            echo "🔗 Linking UMLS concepts for: $filename"
            python scripts/link_document.py "output/${filename}_extracted.json" "output/${filename}_linked.json"
        fi
    fi
done

echo ""
echo "✅ Document processing completed!"
echo ""
echo "📊 Processed files are in the output/ directory"
echo "🔍 To view results:"
echo "   ls -la output/"
echo ""
echo "🧪 To test the API:"
echo "   curl -X POST 'http://127.0.0.1:8099/link' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -H 'X-API-Key: my-secret-medparse-key-123' \\"
echo "     -d '{\"text\": \"Patient has pneumonia and requires treatment\"}'"
