#!/bin/bash
echo "=== Processing Status ==="
echo "PDFs in input: $(ls input/*.pdf 2>/dev/null | wc -l)"
echo "UMLS outputs: $(ls out/json_umls/*.json 2>/dev/null | wc -l)"
echo "scispaCy outputs: $(ls out/json_scispacy/*.json 2>/dev/null | wc -l)"
echo "QuickUMLS outputs: $(ls out/json_quickumls/*.json 2>/dev/null | wc -l)"
echo "Figure crops: $(ls out/figures/*.jpg 2>/dev/null | wc -l)"
echo "Reference CSVs: $(ls out/references/*.csv 2>/dev/null | wc -l)"
echo "QA reports: $(ls out/qa/*.json 2>/dev/null | wc -l)"