#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
uvicorn api.main:app --host 0.0.0.0 --port 8099 --workers 1
