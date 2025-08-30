#!/bin/bash
echo "Running UMLS pipeline..."
python scripts/run_batch.py --linker umls
echo "Running scispaCy pipeline..."
python scripts/run_batch.py --linker scispacy
echo "Running QuickUMLS pipeline..."
python scripts/run_batch.py --linker quickumls
echo "All pipelines complete!"