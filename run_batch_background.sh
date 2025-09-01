#!/bin/bash
# Run batch processing in background and auto-push to GitHub when done

echo "Starting batch PDF processing in background..."
echo "This will:"
echo "  1. Process all PDFs in the input/ folder"
echo "  2. Save results to out/batch_processed/"
echo "  3. Automatically commit and push to GitHub when complete"
echo ""
echo "Logs will be saved to batch_process.log"
echo "You can monitor progress with: tail -f batch_process.log"
echo ""

# Make sure we're in the right directory
cd /home/rjm/projects/ip_knowledge/medparse/medparse-docling

# Run in background with nohup
nohup python batch_process_all.py > batch_process_stdout.log 2>&1 &

# Get the process ID
PID=$!
echo "Process started with PID: $PID"
echo "To check if it's still running: ps -p $PID"
echo "To stop it: kill $PID"
echo ""
echo "The process will continue running even if you disconnect."
echo "Results will be automatically pushed to GitHub when complete."