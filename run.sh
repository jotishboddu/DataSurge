#!/usr/bin/env bash
# Start datasurge: FastAPI backend (port 8000) + Vite dev server (port 5173).
#   ./run.sh          dev mode (hot reload)  -> http://localhost:5173
#   ./run.sh prod     build frontend, serve everything from the backend -> http://localhost:8000
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$ROOT/backend/.venv" ]; then
  python3 -m venv "$ROOT/backend/.venv"
  "$ROOT/backend/.venv/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
fi
[ -d "$ROOT/frontend/node_modules" ] || (cd "$ROOT/frontend" && npm install)

if [ "${1:-dev}" = "prod" ]; then
  (cd "$ROOT/frontend" && npm run build)
  cd "$ROOT/backend" && exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

# Fail visibly rather than connecting the frontend to an older backend.
if command -v lsof >/dev/null && lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null; then
  echo "Port 8000 is already in use. Stop the existing backend before restarting."
  lsof -nP -iTCP:8000 -sTCP:LISTEN
  exit 1
fi

# exec makes BACK the server supervisor, so cleanup reaches the actual backend.
(cd "$ROOT/backend" && exec .venv/bin/uvicorn app.main:app --port 8000 --reload) &
BACK=$!
cleanup() {
  kill "$BACK" 2>/dev/null || true
  wait "$BACK" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
cd "$ROOT/frontend" && npm run dev
