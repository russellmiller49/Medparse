# Medparse API

A FastAPI service that exposes the Medparse document extraction pipeline.

## Quick start

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8099
```

OpenAPI docs live at http://localhost:8099/docs while the server is running.

## Docker

```bash
docker build -t medparse-api:latest .
docker run --rm -p 8099:8099 --env-file .env medparse-api:latest
```

## Endpoints

- `GET /healthz` – simple health check
- `GET /version` – build metadata
- `POST /extract` – multipart upload (`pdf`, `doc_id`)
- `POST /link` – JSON body (`{"text": "..."}`)

## Environment variables

See `.env.example` for the full list. At minimum you must configure `UMLS_API_KEY`, `NCBI_API_KEY`, and `GROBID_URL` for production workloads. Set `ENABLE_PIPELINE=false` to disable heavy processing during local smoke tests.
