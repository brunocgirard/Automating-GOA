# Plan: One-Click Production Deployment Package

## Context

The multi-user deployment (Phases 1-2) is fully implemented, including auth (users, sessions, audit), ownership model, and per-user Gemini key encryption. This plan creates a minimal, self-contained folder that you ZIP and send to someone. They extract it, run `./prereqs.sh` if on a fresh Mac (installs Homebrew, Python, Node, pango), then `./setup.sh` once, then `./start.sh` to launch the full app with browser auto-open.

## Why Shell Scripts (Not Docker, Not EXE)

We evaluated four approaches:

| Approach | One-Click? | Code Protection | Build Effort | Recipient Setup |
|---|---|---|---|---|
| **Shell scripts** | Yes | None (raw .py) | Low (half day) | Python + Node install |
| **Docker Compose** | No | None (layers readable) | Medium | Docker Desktop |
| **PyInstaller** | Partial | Low (.pyc decompilable) | Very High | Node install |
| **Nuitka compiled** | Partial | Medium-High | Extremely High | Node install |

**Shell scripts win because:**
- Docker provides zero code protection and requires Docker Desktop install + potential licensing issues ($5-24/user/month for companies >250 employees)
- PyInstaller/Nuitka are near-impossible with our dep stack (LangChain + ChromaDB + WeasyPrint + Playwright + Pydantic dynamic imports). Expect weeks of debugging `.spec` files.
- Shell scripts: simple, reliable, debuggable. Recipient installs Python + Node (both have polished macOS installers or use Homebrew), runs `./setup.sh`, done.

## What We'll Create

A **build script** (`build_deploy.py`) that assembles a `deploy/GOA_Server/` folder from the current repo, plus **one-click shell scripts** for the recipient.

### Output Structure

```
GOA_Server/
├── prereqs.sh                    # Fresh Mac only: installs Homebrew, Python, Node, pango
├── start.sh                      # Run: starts backend + frontend + opens browser
├── stop.sh                       # Run: kills both processes
├── setup.sh                      # One-time: creates venv, installs deps, builds frontend
├── .env.template                 # Copy to .env and fill in (Gemini key, admin password)
├── README.txt                    # 5-step plain-text instructions
├── requirements.txt              # Production deps only (no pytest/dev/streamlit)
├── pyproject.toml                # For pip install -e . (src package importable)
├── QUOTE_LIBRARY.txt             # Machine specs catalog (145KB, improves extraction)
├── api/                          # FastAPI backend
│   ├── main.py                   # App entry, CORS, router registration
│   ├── models/
│   ├── routers/                  # auth, quotes, machines, processing, reports, shipping, cor, pm_dashboard
│   ├── services/
│   └── dependencies/
├── src/                          # Core business logic
│   ├── llm/                      # LLM extraction, confidence, validation
│   ├── utils/                    # PDF, templates, DB, quote library
│   ├── generators/
│   └── workflows/
├── templates/                    # Runtime templates (docx, dotm, html, xlsx)
├── frontend/                     # Next.js app (source only)
│   ├── package.json
│   ├── package-lock.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── postcss.config.mjs
│   ├── components.json
│   ├── public/
│   └── src/
└── data/                         # Empty dir — DB + generated/ created at runtime
```

**NOT shipped:** `.git/`, `tests/`, `docs/`, `__pycache__/`, `.venv/`, `node_modules/`, `.next/`, `*.pyc`, `output/`, `Dockerfile`, `.dockerignore`, `.github/`

## Files to Create

### 1. `build_deploy.py` (repo root)

Python script that:
- Wipes and re-creates `deploy/GOA_Server/`
- Copies production folders: `api/`, `src/`, `templates/`, `frontend/src/`, `frontend/public/`
- Copies production files: `pyproject.toml`, `QUOTE_LIBRARY.txt`, frontend config files (`package.json`, `package-lock.json`, `next.config.ts`, `tsconfig.json`, `postcss.config.mjs`, `components.json`)
- Generates production `requirements.txt` — strips: `pytest`, `streamlit`, `pandas`, `PyPDF2` (unused in production), all `[dev]` and `[test]` optional deps
- Generates `.env.template` with all required vars + comments
- Generates `README.txt` with plain-text setup instructions
- Generates `prereqs.sh`, `setup.sh`, `start.sh`, `stop.sh` inline
- Makes all `.sh` files executable (`chmod +x`)
- Creates empty `data/` and `data/generated/` directories
- Prints summary of files copied and total size

### 2. `prereqs.sh` — Fresh Mac Prerequisites Installer

Run this **only once** on a Mac that has nothing installed. It installs Homebrew, Python 3, Node.js, and pango. If any of these are already present, it skips them.

```bash
#!/usr/bin/env bash
set -e

echo "============================================"
echo "  GOA Server - Prerequisites Installer"
echo "============================================"
echo ""
echo "This script installs everything needed to run"
echo "GOA Server on a fresh Mac. It will ask for your"
echo "password for system-level installs."
echo ""

# --- Xcode Command Line Tools (needed for Homebrew & compilation) ---
if ! xcode-select -p &> /dev/null; then
    echo "[1/5] Installing Xcode Command Line Tools..."
    echo "      A dialog may appear — click 'Install' and wait."
    xcode-select --install
    echo ""
    echo "Press ENTER after the Xcode tools installation finishes..."
    read -r
else
    echo "[1/5] Xcode Command Line Tools -- already installed"
fi

# --- Homebrew ---
if ! command -v brew &> /dev/null; then
    echo "[2/5] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for Apple Silicon Macs (M1/M2/M3/M4)
    if [ -f /opt/homebrew/bin/brew ]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "[2/5] Homebrew -- already installed"
fi

# --- Python 3 ---
if ! command -v python3 &> /dev/null; then
    echo "[3/5] Installing Python 3.11..."
    brew install python@3.11
else
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "[3/5] Python -- already installed (v$PY_VERSION)"
fi

# --- Node.js ---
if ! command -v node &> /dev/null; then
    echo "[4/5] Installing Node.js 20 (LTS)..."
    brew install node@20
    brew link node@20
else
    NODE_VERSION=$(node --version 2>&1)
    echo "[4/5] Node.js -- already installed ($NODE_VERSION)"
fi

# --- pango (required by WeasyPrint for PDF generation) ---
if ! brew list pango &> /dev/null 2>&1; then
    echo "[5/5] Installing pango (needed for PDF generation)..."
    brew install pango
else
    echo "[5/5] pango -- already installed"
fi

echo ""
echo "============================================"
echo "  All prerequisites installed!"
echo ""
echo "  Next step: run ./setup.sh"
echo "============================================"
```

### 3. `setup.sh` — One-Time First Run

```bash
#!/usr/bin/env bash
set -e

echo "============================================"
echo "  GOA Server - First Time Setup"
echo "============================================"
echo ""

# --- Check prerequisites ---
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found."
    echo "        Install via: brew install python3"
    echo "        Or download from https://python.org"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js not found."
    echo "        Install via: brew install node"
    echo "        Or download from https://nodejs.org"
    exit 1
fi

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
python3 -m venv .venv
source .venv/bin/activate

echo "[2/4] Installing Python dependencies (this may take a few minutes)..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
pip install -e .

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
```

### 4. `start.sh` — One-Click Launch + Browser Open

```bash
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
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "unknown")

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
```

### 5. `stop.sh` — Kill Both Servers

```bash
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
```

### 6. `.env.template`

```bash
# ============================================
# GOA Server Configuration
# ============================================
# Copy this file to .env and fill in the values below.

# --- REQUIRED ---

# Gemini API key (get from https://aistudio.google.com/apikey)
GEMINI_API_KEY=

# Admin account (created on first startup)
AUTH_BOOTSTRAP_ADMIN_USERNAME=admin
AUTH_BOOTSTRAP_ADMIN_PASSWORD=

# Security secrets (use any random strings, e.g., mash your keyboard)
AUTH_SESSION_PEPPER=
GEMINI_KEY_ENCRYPTION_SECRET=

# --- OPTIONAL (defaults shown) ---

# LLM model
GOA_LLM_MODEL=gemini-2.5-flash-lite
GOA_LLM_MODEL_DRAFT=gemini-2.5-flash-lite
GOA_LLM_MODEL_DEEP=gemini-2.5-flash

# Database
DATABASE_PATH=data/crm_data.db

# CORS (add your LAN IP if accessing from other Macs/PCs)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
NEXT_PUBLIC_API_URL=http://localhost:8000

# Auth settings
AUTH_SESSION_TTL_HOURS=12
AUTH_COOKIE_NAME=goa_session
AUTH_COOKIE_SECURE=false
```

### 7. `README.txt`

```
============================================
  GOA Server - Quick Start Guide (macOS)
============================================

FRESH MAC? (nothing installed):
  1. Extract this folder to any location (e.g., ~/GOA_Server)
  2. Open Terminal (Cmd+Space, type "Terminal", press Enter)
  3. Type: cd ~/GOA_Server  (or wherever you extracted it)
  4. Type: chmod +x *.sh
  5. Type: ./prereqs.sh
  6. This installs Homebrew, Python, Node.js, and pango automatically
  7. Then continue with SETUP below

ALREADY HAVE Python 3.11+ and Node.js 20+?
  Skip prereqs.sh, go straight to SETUP.

SETUP (one-time):
  1. Open Terminal, cd into the folder
  2. Run: chmod +x *.sh  (if not already done)
  3. Run: ./setup.sh
  4. When your editor opens .env, fill in your Gemini API key and admin password
  5. Save and close, press ENTER in Terminal to continue
  6. Wait for setup to complete (~5 minutes)

DAILY USE:
  - Open Terminal, cd to the folder, run: ./start.sh
  - Browser opens automatically
  - Login with admin / your chosen password
  - To stop: press Ctrl+C in Terminal, or run ./stop.sh

NETWORK ACCESS:
  - Other devices on your network can access http://<your-ip>:3000
  - Your IP is shown when start.sh runs
  - Add their origin to CORS_ORIGINS in .env if needed

TROUBLESHOOTING:
  - "Python not found"  --> brew install python3 or reinstall from python.org
  - "Node not found"    --> brew install node or reinstall from nodejs.org
  - Blank page          --> wait 10 seconds, refresh browser
  - Login fails         --> check AUTH_BOOTSTRAP_ADMIN_PASSWORD in .env
  - WeasyPrint errors   --> brew install pango (required C dependency)
```

## macOS-Specific Notes

### WeasyPrint Dependency
WeasyPrint requires system-level C libraries on macOS. The `setup.sh` should warn if `pango` is not installed:
```bash
if ! brew list pango &> /dev/null 2>&1; then
    echo "[WARNING] WeasyPrint requires pango. Install via: brew install pango"
fi
```
This check is included in `setup.sh`. If the user doesn't have Homebrew, they'll need to install pango via another method or install Homebrew first.

### Playwright on macOS
`playwright install chromium` works natively on macOS (both Intel and Apple Silicon). No special handling needed.

### File Permissions
The `build_deploy.py` script must set shell scripts as executable:
```python
import stat
for sh_file in ['prereqs.sh', 'setup.sh', 'start.sh', 'stop.sh']:
    path = deploy_dir / sh_file
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
```

### LAN IP Detection
macOS uses `ipconfig getifaddr en0` (Wi-Fi) instead of Windows `ipconfig`. Falls back to `"unknown"` if unavailable.

## Production requirements.txt

Strips from the current `requirements.txt`:
- `pytest` (test only)
- `streamlit` (legacy, not used by FastAPI)
- `pandas` (only used by streamlit)
- `PyPDF2` (superseded by pdfplumber)

```
pdfplumber
python-docx
google-genai
python-dotenv
itsdangerous
langchain>=0.1.0
langchain-google-genai>=0.0.6
langchain-community>=0.0.13
langchain-chroma>=0.1.0
langchain-core>=0.1.0
chromadb>=0.4.0
pydantic
fastapi
uvicorn
python-multipart
openpyxl
beautifulsoup4
weasyprint
playwright
argon2-cffi>=23.1.0
cryptography>=42.0.0
```

## Key Decisions

- **Shell scripts over Docker**: Docker adds install overhead, licensing risk, and provides zero code protection. Shell scripts are simpler and more reliable.
- **Shell scripts over EXE compilation**: Our dep stack (LangChain + ChromaDB + WeasyPrint + Playwright) is hostile to PyInstaller/Nuitka. Would take weeks to debug.
- **No pre-built frontend**: Ship source, build on target with `npm run build`. Avoids platform-specific `node_modules/`.
- **No pre-built venv**: Python venvs aren't portable across machines.
- **Include QUOTE_LIBRARY.txt**: 145KB, improves extraction quality.
- **Include all templates/**: xlsx, docx, dotm, and html templates are all needed at runtime.
- **Auto-open browser**: `start.sh` waits 8 seconds then opens `http://localhost:3000` via `open` command. True one-click experience.
- **PID-based process management**: `start.sh` writes PIDs to `.server_pids`, `stop.sh` reads them. Ctrl+C trap ensures cleanup.
- **Auth-aware .env.template**: Includes all Phase 1+2 auth vars with comments.

## Prerequisites on Recipient's Mac

- macOS 12+ (Monterey or later recommended)
- Internet access (first setup only, for installing prerequisites + `pip install` + `npm install`)
- **If fresh Mac**: Just run `./prereqs.sh` — it installs everything (Xcode CLI Tools, Homebrew, Python 3.11, Node.js 20, pango)
- **If tools already installed**: Python 3.11+, Node.js 20+, pango (`brew install pango`)

## Verification Checklist

1. Run `python build_deploy.py` -> produces `deploy/GOA_Server/`
2. ZIP `GOA_Server/` and copy to a Mac
3. Extract, open Terminal, `cd GOA_Server`, `chmod +x *.sh`
4. (Fresh Mac) Run `./prereqs.sh` -> installs Homebrew, Python, Node, pango
5. Run `./setup.sh` -> installs deps, builds frontend (~5 min)
6. Fill in `.env` when editor opens (Gemini key + admin password)
7. Run `./start.sh` -> both servers start, browser opens to login page
8. Login with admin credentials
9. Upload a PDF, run extraction
10. Access from another device on LAN via `http://<server-ip>:3000`
