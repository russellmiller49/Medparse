# medparse-docling

High-fidelity medical PDF extraction with Docling → GROBID → UMLS (+ fallbacks) and A/B/C evaluation for entity linking (UMLS vs scispaCy vs QuickUMLS). Includes figure crops (EXIF captions), AMA references CSV, DOI→PMID PubMed enrichment, stats & trial IDs, section classification, cross-refs, validation, retries, caching, and QA.

## Setup
1) (Conda) `conda create -n medparse python=3.12 -y && conda activate medparse`
2) Install deps:
   ```bash
   pip install -r requirements.txt
   ```

3) Start GROBID:
   ```bash
   docker run -p 8070:8070 lfoppiano/grobid:0.8.0
   ```

4) (Optional) Local linkers:
   ```bash
   # scispaCy
   pip install scispacy spacy>=3.5
   python -m spacy download en_core_sci_md
   # QuickUMLS
   pip install quickumls
   # (Prepare QuickUMLS index and record its path)
   ```

5) Environment variables (.env supported):
   ```
   UMLS_API_KEY=...
   NCBI_API_KEY=...
   NCBI_EMAIL=you@example.mil
   GROBID_URL=http://localhost:8070
   QUICKUMLS_PATH=/path/to/quickumls/data
   ```

   We auto-load .env (python-dotenv).

## Run (single pipeline)

Put PDFs in `input/`, then:

```bash
python scripts/run_batch.py --linker umls
# or
python scripts/run_batch.py --linker scispacy
# or
python scripts/run_batch.py --linker quickumls
```

## Outputs per paper:
- `out/json_<linker>/<paper>.json` — merged structured JSON
- `out/figures/<paper>_fig_###.jpg` — crops with EXIF caption
- `out/references/<paper>.refs.csv` — AMA styled refs
- `out/qa/<paper>__<linker>.qa.json` — QA stats & validation

## Compare pipelines (A/B/C)
```bash
python scripts/compare_linkers.py --pdf_stems some_paper another_paper
```

Shows entity-linking counts, overlaps, and validation deltas across umls, scispacy, quickumls.

## Notes
- Authors now parsed strictly from TEI header analytic authors (no reference bleed).
- UMLS candidates use a stoplist + noun-ish extraction to avoid generic "text" concepts.
- Reference enrichment uses DOI→PMID first (AID), then Title+Year/Journal (robust).