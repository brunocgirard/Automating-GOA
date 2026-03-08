#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  GOA Server - Starting..."
echo "============================================"

# --- Check setup was run ---
if [ ! -d .venv ]; then
    echo "[ERROR] Run ./setup.sh first!"
    exit 1
fi
if [ ! -f .env ]; then
    echo "[ERROR] No .env file found. Run ./setup.sh first!"
    exit 1
fi

# --- Detect LAN IP ---
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "unknown")

# --- PID file for cleanup ---
PID_FILE="$SCRIPT_DIR/.server_pids"
rm -f "$PID_FILE"

# --- Start Backend ---
echo "[1/2] Starting backend server..."
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "$BACKEND_PID" >> "$PID_FILE"

# --- Start Frontend ---
echo "[2/2] Starting frontend server..."
cd frontend
npm run start -- -H 0.0.0.0 -p 3000 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" >> "$PID_FILE"
cd ..

# --- Wait for servers to start, then open browser ---
echo ""
echo "Waiting for servers to start..."
sleep 8

# Open browser (macOS)
if command -v open &> /dev/null; then
    open http://localhost:3000
fi

echo ""
echo "============================================"
echo "  Server is running!"
echo ""
echo "  Local:   http://localhost:3000"
echo "  Network: http://$LAN_IP:3000"
echo ""
echo "  Press Ctrl+C or run ./stop.sh to stop."
echo "============================================"

# --- Trap Ctrl+C to cleanup ---
cleanup() {
    echo ""
    echo "Stopping servers..."
    kill "$BACKEND_PID" 2>/dev/null
    kill "$FRONTEND_PID" 2>/dev/null
    rm -f "$PID_FILE"
    echo "Servers stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for background processes
wait
