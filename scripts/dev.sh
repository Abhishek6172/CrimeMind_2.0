#!/usr/bin/env bash
# One-command local setup: DB + seed + API (8000) + frontend (5173). Requires PostgreSQL 16 running locally.
set -euo pipefail
cd "$(dirname "$0")/../backend"
export CM_JWT_SECRET="${CM_JWT_SECRET:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')}"
pip install -q --break-system-packages -r requirements.txt
python3 ../scripts/init_db.py --reset
python3 -m synth.seed
(cd ../frontend && npm install --no-audit --no-fund >/dev/null && npx vite --host 127.0.0.1 &) 
exec python3 -m uvicorn app.main:app --port 8000
