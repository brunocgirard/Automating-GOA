#!/usr/bin/env bash
set -e

echo "============================================"
echo "  GOA Server - First Time Setup"
echo "============================================"
echo ""

# --- Check prerequisites ---
PYTHON_BIN=""
if command -v python3.11 &> /dev/null; then
    PYTHON_BIN="python3.11"
elif command -v python3 &> /dev/null; then
    PYTHON_BIN="python3"
else
    echo "[ERROR] Python 3 not found."
    echo "        Install via: brew install python@3.11"
    echo "        Or download from https://python.org"
    exit 1
fi

if ! "$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
    DETECTED_VERSION=$("$PYTHON_BIN" --version 2>&1 | awk '{print $2}')
    echo "[ERROR] Python 3.10+ required. Detected: $DETECTED_VERSION"
    echo "        Install via: brew install python@3.11"
    exit 1
fi

PY_VERSION=$("$PYTHON_BIN" --version 2>&1 | awk '{print $2}')
echo "[SETUP] Using Python $PY_VERSION ($PYTHON_BIN)"

if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js not found."
    echo "        Install via: brew install node"
    echo "        Or download from https://nodejs.org"
    exit 1
fi

if command -v brew &> /dev/null; then
    if ! brew list pango &> /dev/null 2>&1; then
        echo "[WARNING] WeasyPrint requires pango. Install via: brew install pango"
    fi
fi

# --- Ensure Finder launchers are executable ---
chmod +x ./*.command 2>/dev/null || true

# --- Create .env from template if missing ---
if [ ! -f .env ]; then
    echo ""
    echo "[SETUP] Creating .env from template..."
    cp .env.template .env
    echo ""
    echo "*** IMPORTANT: Open .env and fill in: ***"
    echo "  - GEMINI_API_KEY (get from https://aistudio.google.com/apikey)"
    echo "  - AUTH_BOOTSTRAP_ADMIN_PASSWORD (choose a password)"
    echo "  - AUTH_SESSION_PEPPER (any random string)"
    echo "  - GEMINI_KEY_ENCRYPTION_SECRET (any random string)"
    echo ""
    # Open .env in default text editor
    if command -v open &> /dev/null; then
        open -t .env
    elif command -v nano &> /dev/null; then
        nano .env
    fi
    echo "Press ENTER after saving .env..."
    read -r
fi

# --- Python virtual environment ---
echo ""
echo "[1/4] Creating Python virtual environment..."
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate

echo "[2/4] Installing Python dependencies (this may take a few minutes)..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt

echo "[3/4] Installing Playwright browser..."
playwright install chromium

# --- Frontend ---
echo "[4/4] Installing frontend dependencies and building..."
cd frontend
npm install
npm run build
cd ..

echo ""
echo "============================================"
echo "  Setup Complete!"
echo "  Run ./start.sh to launch the server."
echo "============================================"
