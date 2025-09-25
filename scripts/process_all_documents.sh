#!/bin/bash

# Medparse Master Document Processor
# Processes all document types with appropriate settings

set -e

echo "🏥 Medparse - Master Document Processor"
echo "======================================="

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

# Function to process documents by type
process_documents() {
    local doc_type=$1
    local input_dir="input/$doc_type"
    local output_dir="output/$doc_type"
    
    echo ""
    echo "📁 Processing $doc_type documents..."
    
    # Count documents
    pdf_count=$(find "$input_dir/pdf" -name "*.pdf" 2>/dev/null | wc -l)
    text_count=$(find "$input_dir/text" -name "*.txt" 2>/dev/null | wc -l)
    
    if [ $pdf_count -eq 0 ] && [ $text_count -eq 0 ]; then
        echo "⚠️  No $doc_type documents found in $input_dir/"
        return 0
    fi
    
    echo "📊 Found $pdf_count PDFs and $text_count text files"
    
    # Process PDFs
    if [ $pdf_count -gt 0 ]; then
        echo "📄 Processing $doc_type PDFs..."
        
        for pdf_file in "$input_dir/pdf"/*.pdf; do
            if [ -f "$pdf_file" ]; then
                filename=$(basename "$pdf_file" .pdf)
                echo "📄 Processing: $filename"
                
                # Extract with document-specific settings
                curl -X POST "http://127.0.0.1:8099/extract" \
                  -H "Content-Type: multipart/form-data" \
                  -H "X-API-Key: my-secret-medparse-key-123" \
                  -F "file=@$pdf_file" \
                  -F "document_type=$doc_type" \
                  -o "$output_dir/${filename}_extracted.json"
                
                # Link UMLS concepts
                if [ -f "$output_dir/${filename}_extracted.json" ]; then
                    echo "🔗 Linking UMLS concepts for: $filename"
                    python scripts/link_document.py \
                      "$output_dir/${filename}_extracted.json" \
                      "$output_dir/${filename}_linked.json" \
                      --document_type="$doc_type"
                fi
            fi
        done
    fi
    
    # Process text files
    if [ $text_count -gt 0 ]; then
        echo "📝 Processing $doc_type text files..."
        
        for text_file in "$input_dir/text"/*.txt; do
            if [ -f "$text_file" ]; then
                filename=$(basename "$text_file" .txt)
                echo "📝 Processing: $filename"
                
                python scripts/process_text.py \
                  "$text_file" \
                  "$output_dir/${filename}_processed.json" \
                  --document_type="$doc_type"
            fi
        done
    fi
    
    echo "✅ $doc_type processing completed!"
}

# Process all document types
process_documents "articles"
process_documents "textbooks"
process_documents "guidelines"
process_documents "manuals"

echo ""
echo "🎉 All document processing completed!"
echo ""
echo "📊 Summary of processed documents:"
echo "   Articles: $(find output/articles -name "*.json" 2>/dev/null | wc -l) files"
echo "   Textbooks: $(find output/textbooks -name "*.json" 2>/dev/null | wc -l) files"
echo "   Guidelines: $(find output/guidelines -name "*.json" 2>/dev/null | wc -l) files"
echo "   Manuals: $(find output/manuals -name "*.json" 2>/dev/null | wc -l) files"
echo ""
echo "🔍 To view results:"
echo "   ls -la output/*/"
echo ""
echo "🧪 To test the API:"
echo "   curl -X POST 'http://127.0.0.1:8099/link' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -H 'X-API-Key: my-secret-medparse-key-123' \\"
echo "     -d '{\"text\": \"Patient has pneumonia and requires treatment\"}'"
