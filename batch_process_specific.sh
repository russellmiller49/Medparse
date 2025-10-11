#!/bin/bash

# Batch Process Specific Documents
# Processes the specific PDFs you mentioned with quickumls linker

set -e

echo "🏥 Medparse - Batch Processing Specific Documents"
echo "================================================"

# Check if we're in the right directory
if [ ! -f "scripts/process_one.py" ]; then
    echo "❌ Error: Please run this script from the medparse-docling root directory"
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p output

# Array of commands to execute
declare -a commands=(
    "python scripts/process_one.py --pdf 'input/guidelines/pdf/Guideline ATS diagnostic yield.pdf' --out 'output/ATS diagnostic yield.pdf.json' --linker quickumls"
    "python scripts/process_one.py --pdf 'input/guidelines/pdf/Combined EBUS  EUS for the diagnosis and staging of lung cancer ESGE, ERS, ESTS Guideline.pdf' --out output/ebus_eus_guideline_enhanced.json --linker quickumls"
    "python scripts/process_one.py --pdf 'input/articles/pdf/Robotic Cyrobiopsy 2022.pdf' --out output/Robotic_Cyrobiopsy_2022.json --linker quickumls"
    "python scripts/process_one.py --pdf 'input/manuals/pdf/Ion Endoluminal System, Instruments, and Accessories User Manual(553990-11).pdf' --out 'output/Ion_Endoluminal_System_IFU.json' --linker quickumls"
    "python scripts/process_one.py --pdf 'input/textbooks/pdf/Treatment of Airway-Esophageal Fistulas.pdf' --out 'output/Airway-Esophageal Fistulas_Chapter.json' --linker quickumls"
)

# Counter for tracking progress
total=${#commands[@]}
current=0

echo "📊 Processing $total documents..."
echo ""

# Execute each command
for cmd in "${commands[@]}"; do
    current=$((current + 1))
    echo "🔄 [$current/$total] Processing document..."
    echo "📄 Command: $cmd"
    
    # Execute the command
    if eval "$cmd"; then
        echo "✅ Successfully processed document $current/$total"
    else
        echo "❌ Failed to process document $current/$total"
        echo "⚠️  Continuing with remaining documents..."
    fi
    
    echo ""
done

echo "🎉 Batch processing completed!"
echo ""
echo "📊 Summary:"
echo "   Total documents: $total"
echo "   Output directory: output/"
echo ""
echo "🔍 To view results:"
echo "   ls -la output/*.json"
echo ""
echo "📝 Processed files:"
for file in output/*.json; do
    if [ -f "$file" ]; then
        echo "   ✅ $(basename "$file")"
    fi
done
