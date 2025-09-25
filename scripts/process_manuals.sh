#!/bin/bash

# Medparse Document Processor - Manuals
# Optimized for processing procedural manuals and technical documents

set -e

echo "📖 Medparse - Manuals Processor"
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

# Check for manuals
echo "📖 Checking for manuals..."
pdf_count=$(find input/manuals/pdf -name "*.pdf" 2>/dev/null | wc -l)
text_count=$(find input/manuals/text -name "*.txt" 2>/dev/null | wc -l)

if [ $pdf_count -eq 0 ] && [ $text_count -eq 0 ]; then
    echo "⚠️  No manuals found in input/manuals/"
    echo "   Please add your manual PDFs to input/manuals/pdf/"
    echo "   Or add text files to input/manuals/text/"
    echo "   Then run this script again."
    exit 1
fi

echo "📊 Found $pdf_count manual PDFs and $text_count text files"

# Process PDF manuals
if [ $pdf_count -gt 0 ]; then
    echo "📖 Processing manual PDFs..."
    
    for pdf_file in input/manuals/pdf/*.pdf; do
        if [ -f "$pdf_file" ]; then
            filename=$(basename "$pdf_file" .pdf)
            echo "📖 Processing manual: $filename"
            
            # Extract text and concepts with manual-specific settings
            curl -X POST "http://127.0.0.1:8099/extract" \
              -H "Content-Type: multipart/form-data" \
              -H "X-API-Key: my-secret-medparse-key-123" \
              -F "file=@$pdf_file" \
              -F "document_type=manual" \
              -F "extract_procedures=true" \
              -F "extract_steps=true" \
              -F "extract_warnings=true" \
              -F "extract_troubleshooting=true" \
              -o "output/manuals/${filename}_extracted.json"
            
            # Link UMLS concepts for manuals
            if [ -f "output/manuals/${filename}_extracted.json" ]; then
                echo "🔗 Linking UMLS concepts for manual: $filename"
                python scripts/link_document.py \
                  "output/manuals/${filename}_extracted.json" \
                  "output/manuals/${filename}_linked.json" \
                  --document_type=manual \
                  --focus_terms="procedures,steps,techniques,equipment,safety,warnings"
            fi
        fi
    done
fi

# Process text manuals
if [ $text_count -gt 0 ]; then
    echo "📝 Processing text manuals..."
    
    for text_file in input/manuals/text/*.txt; do
        if [ -f "$text_file" ]; then
            filename=$(basename "$text_file" .txt)
            echo "📝 Processing text manual: $filename"
            
            # Process text directly
            python scripts/process_text.py \
              "$text_file" \
              "output/manuals/${filename}_processed.json" \
              --document_type=manual
        fi
    done
fi

echo ""
echo "✅ Manuals processing completed!"
echo ""
echo "📊 Processed files are in the output/manuals/ directory"
echo "🔍 To view results:"
echo "   ls -la output/manuals/"
echo ""
echo "📈 Manual-specific features processed:"
echo "   • Step-by-step procedure extraction"
echo "   • Safety warnings and precautions"
echo "   • Troubleshooting guides"
echo "   • Equipment and technique details"
echo "   • Quality control procedures"
