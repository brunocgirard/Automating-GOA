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
