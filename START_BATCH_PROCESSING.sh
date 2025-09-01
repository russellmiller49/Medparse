#!/bin/bash
# Easy launcher for batch processing all PDFs

clear
echo "=========================================="
echo "     MEDPARSE BATCH PROCESSOR"
echo "=========================================="
echo ""
echo "This will process all PDFs and auto-push to GitHub"
echo ""

# Count PDFs
TOTAL_PDFS=$(ls input/*.pdf 2>/dev/null | wc -l)
PROCESSED=$(ls out/batch_processed/*.json 2>/dev/null | grep -v processing_report | wc -l)

echo "📊 Status:"
echo "   Total PDFs: $TOTAL_PDFS"
echo "   Already processed: $PROCESSED"
echo "   To process: $((TOTAL_PDFS - PROCESSED))"
echo ""

# Estimate time (assuming ~1 minute per PDF)
MINUTES=$((TOTAL_PDFS - PROCESSED))
HOURS=$((MINUTES / 60))
echo "⏱️  Estimated time: ~$HOURS hours ($MINUTES minutes)"
echo ""

echo "📍 Options:"
echo "   1) Run in foreground (you can watch progress)"
echo "   2) Run in background (continues after logout)"
echo "   3) Cancel"
echo ""
read -p "Choose [1/2/3]: " choice

case $choice in
    1)
        echo ""
        echo "Starting in foreground..."
        echo "Press Ctrl+C to stop"
        echo ""
        python batch_process_all.py
        ;;
    2)
        echo ""
        echo "Starting in background..."
        ./run_batch_background.sh
        echo ""
        echo "✅ Process started! It will run even if you disconnect."
        echo ""
        echo "To check status later, run: ./check_batch_status.sh"
        ;;
    *)
        echo "Cancelled."
        ;;
esac