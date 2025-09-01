#!/bin/bash
# Check the status of batch processing

echo "=== Batch Processing Status ==="
echo ""

# Check if process is running
if pgrep -f "batch_process_all.py" > /dev/null; then
    echo "✓ Batch processing is RUNNING"
    echo "  PID: $(pgrep -f batch_process_all.py)"
else
    echo "✗ Batch processing is NOT running"
fi

echo ""

# Check output directory
OUTPUT_DIR="out/batch_processed"
if [ -d "$OUTPUT_DIR" ]; then
    COUNT=$(ls -1 "$OUTPUT_DIR"/*.json 2>/dev/null | wc -l)
    echo "Processed files: $COUNT"
fi

# Check if report exists
if [ -f "$OUTPUT_DIR/processing_report.json" ]; then
    echo ""
    echo "Processing report found. Summary:"
    python -c "
import json
with open('$OUTPUT_DIR/processing_report.json') as f:
    r = json.load(f)
    print(f'  Total: {r.get(\"total_pdfs\", 0)}')
    print(f'  Success: {r.get(\"successful\", 0)}')
    print(f'  Failed: {r.get(\"failed\", 0)}')
    print(f'  Time: {r.get(\"timestamp\", \"N/A\")}')
" 2>/dev/null
fi

echo ""

# Show last few log lines
if [ -f "batch_process.log" ]; then
    echo "Recent log entries:"
    tail -5 batch_process.log
fi