#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export APP_ENV=demo DEMO_MODE=true EMBED_WORKER=true
export TELEGRAM_ADAPTER=demo LLM_ADAPTER=demo AUTH_ADAPTER=demo
export PYTHONPATH="$ROOT/backend"
if [[ -z "${DATABASE_URL:-}" ]]; then
  mkdir -p "$ROOT/data"
  export DATABASE_URL="sqlite+pysqlite:///$ROOT/data/education_sales_demo.db"
  echo "Docker no es necesario para esta demo. Usando SQLite."
fi
cd "$ROOT/backend"
python -m uvicorn app.main:app --timeout-graceful-shutdown 3 --port 8000
