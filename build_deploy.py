#!/usr/bin/env python3
"""Build a Mac-ready lightweight deployment folder at deploy/GOA_Server."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEPLOY_DIR = ROOT / "deploy" / "GOA_Server"

EXCLUDED_REQUIREMENTS = {"pytest", "streamlit", "pandas", "pypdf2"}
BASE_EXCLUDE_PATTERNS = (
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "*.tsbuildinfo",
    ".DS_Store",
)


PREREQS_SH = """#!/usr/bin/env bash
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
    echo "      A dialog may appear - click 'Install' and wait."
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
    if python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
        echo "[3/5] Python -- already installed (v$PY_VERSION)"
    else
        echo "[3/5] Python version is $PY_VERSION (too old). Installing Python 3.11..."
        brew install python@3.11
    fi
fi

# --- Node.js ---
if ! command -v node &> /dev/null; then
    echo "[4/5] Installing Node.js 20 (LTS)..."
    brew install node@20
    if ! command -v node &> /dev/null; then
        brew link --overwrite --force node@20
    fi
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
"""


SETUP_SH = """#!/usr/bin/env bash
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
"""


START_SH = """#!/usr/bin/env bash
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
"""


STOP_SH = """#!/usr/bin/env bash

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
"""


START_COMMAND = """#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
./start.sh
"""


STOP_COMMAND = """#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
./stop.sh
"""


ENV_TEMPLATE = """# ============================================
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
"""


README_TXT = """============================================
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
  2. Run: chmod +x *.sh *.command  (if not already done)
  3. Run: ./setup.sh
  4. When your editor opens .env, fill in your Gemini API key and admin password
  5. Save and close, press ENTER in Terminal to continue
  6. Wait for setup to complete (~5 minutes)

DAILY USE:
  - Easiest: double-click "Start GOA Server.command" in Finder
  - Or in Terminal run: ./start.sh
  - Browser opens automatically
  - Login with admin / your chosen password
  - To stop: press Ctrl+C in Terminal, run ./stop.sh, or double-click "Stop GOA Server.command"

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
"""


def write_text_lf(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content.rstrip("\n") + "\n")


def copy_tree(src: Path, dst: Path, extra_excludes: tuple[str, ...] = ()) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Required directory not found: {src}")
    ignore = shutil.ignore_patterns(*(BASE_EXCLUDE_PATTERNS + extra_excludes))
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)


def copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Required file not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def requirement_name(line: str) -> str:
    stripped = line.strip()
    for idx, ch in enumerate(stripped):
        if ch in "<>=!~; [":
            return stripped[:idx].strip().lower()
    return stripped.lower()


def build_requirements(source: Path, target: Path) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name = requirement_name(stripped)
        if name in EXCLUDED_REQUIREMENTS:
            continue
        kept.append(stripped)
    write_text_lf(target, "\n".join(kept))


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def compute_stats(root: Path) -> tuple[int, int]:
    file_count = 0
    total_size = 0
    for entry in root.rglob("*"):
        if entry.is_file():
            file_count += 1
            total_size += entry.stat().st_size
    return file_count, total_size


def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def main() -> None:
    if DEPLOY_DIR.exists():
        shutil.rmtree(DEPLOY_DIR)
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)

    # Core runtime directories
    copy_tree(ROOT / "api", DEPLOY_DIR / "api")
    copy_tree(ROOT / "src", DEPLOY_DIR / "src", extra_excludes=("cache",))
    copy_tree(ROOT / "templates", DEPLOY_DIR / "templates")
    copy_tree(ROOT / "frontend" / "src", DEPLOY_DIR / "frontend" / "src")
    copy_tree(ROOT / "frontend" / "public", DEPLOY_DIR / "frontend" / "public")

    # Root/runtime files
    copy_file(ROOT / "pyproject.toml", DEPLOY_DIR / "pyproject.toml")
    copy_file(ROOT / "README.md", DEPLOY_DIR / "README.md")
    copy_file(ROOT / "QUOTE_LIBRARY.txt", DEPLOY_DIR / "QUOTE_LIBRARY.txt")

    # Frontend config files
    frontend_files = [
        "package.json",
        "package-lock.json",
        "next.config.ts",
        "tsconfig.json",
        "postcss.config.mjs",
        "components.json",
    ]
    for name in frontend_files:
        copy_file(ROOT / "frontend" / name, DEPLOY_DIR / "frontend" / name)

    # Generated runtime files
    build_requirements(ROOT / "requirements.txt", DEPLOY_DIR / "requirements.txt")
    write_text_lf(DEPLOY_DIR / ".env.template", ENV_TEMPLATE)
    write_text_lf(DEPLOY_DIR / "README.txt", README_TXT)
    write_text_lf(DEPLOY_DIR / "prereqs.sh", PREREQS_SH)
    write_text_lf(DEPLOY_DIR / "setup.sh", SETUP_SH)
    write_text_lf(DEPLOY_DIR / "start.sh", START_SH)
    write_text_lf(DEPLOY_DIR / "stop.sh", STOP_SH)
    write_text_lf(DEPLOY_DIR / "Start GOA Server.command", START_COMMAND)
    write_text_lf(DEPLOY_DIR / "Stop GOA Server.command", STOP_COMMAND)

    # Runtime data directories
    (DEPLOY_DIR / "data").mkdir(parents=True, exist_ok=True)
    (DEPLOY_DIR / "data" / "generated").mkdir(parents=True, exist_ok=True)

    for executable_name in (
        "prereqs.sh",
        "setup.sh",
        "start.sh",
        "stop.sh",
        "Start GOA Server.command",
        "Stop GOA Server.command",
    ):
        make_executable(DEPLOY_DIR / executable_name)

    file_count, total_size = compute_stats(DEPLOY_DIR)
    print("Deployment package built:")
    print(f"  Path: {DEPLOY_DIR}")
    print(f"  Files: {file_count}")
    print(f"  Size: {human_size(total_size)}")


if __name__ == "__main__":
    main()
