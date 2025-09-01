# Batch Processing Instructions

## Quick Start

To process all 414 PDFs and automatically push to GitHub:

```bash
./START_BATCH_PROCESSING.sh
```

Choose option 2 to run in background (recommended for 414 PDFs).

## What It Does

1. **Processes all PDFs** in `input/` folder
2. **Saves results** to `out/batch_processed/`
3. **Commits every 10 PDFs** to avoid data loss
4. **Automatically pushes to GitHub** when complete
5. **Resumes if interrupted** (skips already processed files)

## Time Estimate

- ~1 minute per PDF
- 414 PDFs ≈ 7 hours total
- Runs in background, survives logout

## Monitor Progress

Check status anytime:
```bash
./check_batch_status.sh
```

Watch live logs:
```bash
tail -f batch_process.log
```

## Output Structure

```
out/batch_processed/
├── paper1.json         # Extracted data
├── paper2.json
├── ...
└── processing_report.json  # Summary statistics
```

## Features Applied

Each PDF gets:
- ✅ Abstract extraction (fallback from structure)
- ✅ Author extraction (fallback from front matter)  
- ✅ References (fallback to GROBID XML)
- ✅ Statistics extraction (context-aware)
- ✅ Caption-figure/table association
- ✅ Clean text (no "Odds ratio (or)" pollution)
- ✅ UMLS linking (precision-focused)

## If Something Goes Wrong

1. Check logs: `cat batch_process.log`
2. Resume: Just run `./START_BATCH_PROCESSING.sh` again (skips completed)
3. Manual push: `git push origin fix/extraction-hardening`

## Expected Quality Improvement

- Before: ~67% average quality score
- After: ~80% average quality score
- Most "✗ Authors/Abstract/References" → ✓