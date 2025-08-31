#!/bin/bash
# Quick test script to process 5 random articles with UMLS

echo "=========================================="
echo "Testing 5 Random Articles with UMLS Linker"
echo "=========================================="

# Use a fixed seed for reproducible testing (remove --seed for true random)
python scripts/test_random_batch.py \
    --input input \
    --output out/test_batch_umls \
    --n 5 \
    --seed 42

echo ""
echo "Test complete. Check out/test_batch_umls/ for results."
echo "View detailed report: out/test_batch_umls/test_report.json"