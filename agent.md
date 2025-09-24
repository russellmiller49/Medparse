# Medparse ↔ IP_Assist_Lite Integration Guide

## Purpose
This document describes how the Medparse sidecar API integrates with IP_Assist_Lite. It covers responsibilities, runtime requirements, environment variables, request contracts, and operational workflows so either service – or any QA agent – can reason about the end-to-end system quickly.

---

## High-Level Architecture
- **Medparse (FastAPI sidecar, Python 3.11)**
  - Extracts medical PDFs into structured JSON (metadata, sections, figures, statistics).
  - Performs concept linking via UMLS (remote API) and/or QuickUMLS (local index).
  - Exposes `GET /healthz`, `GET /version`, `POST /link`, and `POST /extract`.
- **IP_Assist_Lite (Python 3.12 app)**
  - Calls Medparse over HTTP for concept linking and full-document enrichment.
  - Uses data returned by Medparse to populate graph stores (Neo4j, Qdrant) and the UI.
  - Remains on Python 3.12 while Medparse is pinned to Python 3.11.

The two repos communicate strictly through HTTP, so they can evolve independently and run on different Python versions or hosts.

---

## Medparse Service Responsibilities
1. **PDF Processing (`POST /extract`)**
   - Accepts multipart form data with `pdf` (file) and `doc_id` (string).
   - Runs Docling + GROBID + enrichment pipeline in a temp workspace.
   - Returns JSON containing:
     - `metadata`: title, authors, abstract, references, trial IDs, etc.
     - `umls_links`: curated UMLS API matches (when API key is present).
     - `umls_links_local`: QuickUMLS / scispaCy fallbacks, filtered for clinical TUIs.
     - `statistics`, `figures`, `tables`, `validation` flags.
2. **Text Linking (`POST /link`)**
   - Accepts JSON `{ "text": str, "top_k": int = 20 }`.
   - Tries UMLS API first when `UMLS_API_KEY` is set.
   - Falls back to QuickUMLS when the key is missing or network fails.
   - Deduplicates results and enforces `top_k` to keep responses consistent.
3. **Health & Metadata**
   - `GET /healthz` for liveness probes, returns `{ "ok": true }`.
   - `GET /version` returns `{ "title": ..., "version": ... }` from env config.

---

## Runtime Requirements (Medparse Sidecar)
- **Python**: 3.11 only (QuickUMLS imports the deprecated `imp` module and fails on 3.12+).
- **Virtual Environment**: `conda env create -f environment.py311.yml && conda activate medparse-py311`.
- **Dependencies**: `pip install -r requirements.txt` + optional `pytesseract`.
- **External services**:
  - GROBID (optional but recommended): `docker run -d -p 8070:8070 lfoppiano/grobid:0.8.0`.
  - QuickUMLS index (local): build once from UMLS 2025AA release.
- **Configuration file**: `.env` (copy from `.env.example`).

### Required `.env` keys
| Variable | Description |
| --- | --- |
| `QUICKUMLS_PATH` | Local index path, e.g. `/home/rjm/projects/ip_knowledge/quickumls_data/2025AA_ENG` |
| `GROBID_URL` | e.g. `http://localhost:8070` or docker hostname |
| `API_TITLE`, `API_VERSION` | Shown on `/version` |
| `ALLOWED_ORIGINS` | CORS whitelist for IP_Assist_Lite UI |
| `MAX_UPLOAD_MB` | Upload size limits |
| `ENABLE_PIPELINE` | Toggle to disable heavy PDF processing in dev |
| `API_KEY` | Optional header guard for `/link` & `/extract` |

### Optional `.env` keys
| Variable | Purpose |
| --- | --- |
| `UMLS_API_KEY` | Enables remote UMLS linking (rate limited, slow) |
| `NCBI_API_KEY`, `NCBI_EMAIL` | Enables PubMed enrichment of references |

---

## QuickUMLS Index Build (One Time)
```bash
QUICKUMLS_OUT=/home/rjm/projects/ip_knowledge/quickumls_data
mkdir -p "$QUICKUMLS_OUT"
quickumls_install \
  --umls /mnt/c/UMLS/2025AA/META \
  --language ENG \
  --output_path "$QUICKUMLS_OUT"

# Resulting path to use in .env:
# /home/rjm/projects/ip_knowledge/quickumls_data/2025AA_ENG
```
- Ensure the build runs from the Python 3.11 environment.
- The availability probe now accepts both `cui-semtypes.db` and `cui_semtypes.db` naming variants.
- `/link` uses this path automatically if `UMLS_API_KEY` is empty.

---

## Service Operation
```bash
# Activate environment
conda activate medparse-py311

# Start API (dev)
uvicorn api.main:app --reload --port 8099

# Health check
curl http://127.0.0.1:8099/healthz

# Quick smoke test for fallback (with empty UMLS_API_KEY)
curl -s -X POST http://127.0.0.1:8099/link \
  -H 'Content-Type: application/json' \
  -d '{"text": "massive hemoptysis"}' | jq
```
- Expect QuickUMLS results in the response when no API key is configured.
- For PDF tests, place a sample file in `input/` and run `python scripts/process_one.py --pdf input/AMPLE2.pdf --out out/test.json --linker quickumls`.

---

## Integration Points in IP_Assist_Lite
1. **Environment (`.env`)**
   - `MEDPARSE_URL=http://localhost:8099`
   - Maintain `GRAPH_ENABLED=true` and other graph flags when leveraging concept panels.
2. **Client Wrapper** (`src/external/medparse_client.py`)
   - Provides async methods `link(text, top_k)` and `extract(pdf_path, doc_id)`.
   - Calls `self.base_url = MEDPARSE_URL.rstrip('/')`.
3. **Graph Pipeline**
   - `src/graph/medparse_ingest.py` converts `/extract` output into Neo4j nodes/edges.
   - `src/retrieval/graph_bridge.py` orchestrates `/link` ➜ graph expansion ➜ Qdrant seeding.
   - Evidence panel uses counts of `statistics`, `figures`, `tables` returned by Medparse.
4. **UI**
   - Expect CORS to allow `http://localhost:7860` (default). Ensure `ALLOWED_ORIGINS` matches.
   - Concept panel shows `cui`, preferred names, and evidence metrics.

### Typical Query Flow
1. User asks a question in IP_Assist_Lite UI.
2. App calls `MedparseClient.link(text)`.
3. Response seeds graph expansion (Neo4j) → doc list → Qdrant hybrid retrieval.
4. Concept panel shows seed CUIs plus neighbours, with evidence counts derived from Medparse output.
5. If a PDF needs full ingestion, IP_Assist_Lite calls `MedparseClient.extract` and pushes the JSON to down-stream stores.

---

## Operational Checks Before Integration
- [ ] `uvicorn` running on port 8099 (or configured port) with Medparse.
- [ ] `.env` on Medparse side has `QUICKUMLS_PATH` pointing to 2025AA index.
- [ ] `.env` on IP_Assist_Lite side has `MEDPARSE_URL` pointing at the running service.
- [ ] QuickUMLS fallback verified via `/link` (no API key) returning non-empty list.
- [ ] Optional: run `pytest -q` in `medparse-docling` – includes QuickUMLS fallback regression test.
- [ ] Docker Compose scenario: update `docker/dev.compose.yml` (if used) so the `medparse-api` service mounts the QuickUMLS volume and declares port `8099`.

---

## Useful Commands
| Action | Command |
| --- | --- |
| Run docs-lint tests | `pytest -q` |
| Process one PDF (QuickUMLS) | `python scripts/process_one.py --pdf input/AMPLE2.pdf --out out/test_quick.json --linker quickumls` |
| Batch process | `python scripts/run_batch.py --linker quickumls` |
| Check QuickUMLS availability | `python -c "from scripts.linking.quickumls_fallback import is_quickumls_available; print(is_quickumls_available())"` |
| Rebuild env | `conda env remove -n medparse-py311 && conda env create -f environment.py311.yml` |

---

## Troubleshooting Tips
- **`ImportError: imp module`**: Ensure you are using Python 3.11 (QuickUMLS fails on >=3.12).
- **`QuickUMLS files missing`**: Confirm index path contains `cui-semtypes.db` and `umls-simstring.db` (hyphenated or underscored).
- **Empty `/link` response**: Check `QUICKUMLS_PATH`, confirm service can access the folder, and inspect logs for fallback warnings.
- **CORS errors in IP_Assist_Lite**: Update `ALLOWED_ORIGINS` in Medparse `.env` to include the UI origin.

---

## Change Log Highlights (recent)
- QuickUMLS fallback automatically activates when `UMLS_API_KEY` is absent.
- File naming tolerance for QuickUMLS indices (hyphen/underscore variants).
- Python package metadata updated to require `<3.12`; `environment.py311.yml` bootstraps the sidecar.
- Regression tests added for QuickUMLS fallback.

---

## Contact Points
- **Medparse maintainers**: TBD (consult repo README for latest contacts).
- **IP_Assist_Lite maintainers**: TBD (see IP_Assist_Lite README).

For any integration issues, start by verifying the Medparse sidecar locally, then move to the IP_Assist_Lite client layer. The HTTP boundary makes it easy to repro with `curl` before touching the chatbot stack.

