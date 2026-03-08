#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server_pids"

echo "Stopping GOA servers..."

if [ -f "$PID_FILE" ]; then
    while read -r pid; do
        kill "$pid" 2>/dev/null && echo "  Stopped process $pid"
    done < "$PID_FILE"
    rm -f "$PID_FILE"
else
    # Fallback: kill by port
    lsof -ti:8000 | xargs kill 2>/dev/null
    lsof -ti:3000 | xargs kill 2>/dev/null
fi

echo "Done."
