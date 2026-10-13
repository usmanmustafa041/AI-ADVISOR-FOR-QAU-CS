#!/usr/bin/env bash
# Starts the whole portal for local use:
#   portal API (legacy) :8001   chatbot engine :8010   portal UI (the familiar interface) :5173
# Open http://127.0.0.1:5173 — the chat inside it is answered by the chatbot engine.
# Stop everything with Ctrl-C.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
PY="$BACKEND/.venv/bin/python"
PORTAL_PORT="${PORTAL_PORT:-8001}" ADVISOR_PORT="${ADVISOR_PORT:-8010}" UI_PORT="${UI_PORT:-5173}"

pids=()
cleanup() { trap - INT TERM EXIT; for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup INT TERM EXIT

busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
for p in "$PORTAL_PORT" "$ADVISOR_PORT" "$UI_PORT"; do
  if busy "$p"; then echo "Port $p is already in use — stop that process (or set PORTAL_PORT / ADVISOR_PORT / UI_PORT) and retry."; exit 1; fi
done

echo "▶ portal API on :$PORTAL_PORT"
(cd "$BACKEND" && exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORTAL_PORT") &
pids+=($!)

echo "▶ chatbot engine on :$ADVISOR_PORT (signed-in students and admins are verified by the portal API)"
(cd "$BACKEND" && ADVISOR_TRUST_PROXY_HEADERS=true \
  ADVISOR_AUTH_VERIFY_URL="http://127.0.0.1:$PORTAL_PORT/api/v1/auth/me" \
  exec "$PY" -m advisor.cli serve --host 127.0.0.1 --port "$ADVISOR_PORT") &
pids+=($!)

echo "▶ portal interface on :$UI_PORT"
(cd "$ROOT/frontend" && VITE_API_PROXY="http://127.0.0.1:$PORTAL_PORT" VITE_ADVISOR_PROXY="http://127.0.0.1:$ADVISOR_PORT" \
  exec npm run dev -- --host 127.0.0.1 --port "$UI_PORT") &
pids+=($!)

echo "Open http://127.0.0.1:$UI_PORT   (Ctrl-C to stop)"
wait
