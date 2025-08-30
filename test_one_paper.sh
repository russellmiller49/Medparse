#!/bin/bash
PAPER="$1"
if [ -z "$PAPER" ]; then
    echo "Usage: ./test_one_paper.sh 'paper_name.pdf'"
    exit 1
fi
STEM="${PAPER%.pdf}"

echo "Testing: $PAPER"
python scripts/process_one.py --pdf "input/$PAPER" --out "out/json_umls/${STEM}.json" --linker umls
python scripts/process_one.py --pdf "input/$PAPER" --out "out/json_scispacy/${STEM}.json" --linker scispacy  
python scripts/process_one.py --pdf "input/$PAPER" --out "out/json_quickumls/${STEM}.json" --linker quickumls
python scripts/compare_linkers.py --pdf_stems "$STEM"