# Plan: Create Self-Contained Production Deployment Folder

## Context
The multi-user deployment (Phases 1-2) is fully implemented. This plan creates a minimal, self-contained folder to copy to the server PC and run. No .git, no tests, no docs — just production code + start scripts.

## What We'll Create

A **build script** (`build_deploy.py`) that assembles a `deploy/GOA_Server/` folder from the current repo, plus **start/stop batch files** for the server PC.

### Output Structure
```
GOA_Server/
├── start_server.bat          # Double-click to start both backend + frontend
├── stop_server.bat           # Kill both processes
├── setup.bat                 # One-time: create venv, install deps, build frontend
├── .env.template             # Copy to .env and fill in
├── requirements.txt          # Production deps only (no pytest/dev)
├── api/                      # FastAPI backend (all files)
├── src/                      # Core business logic
├── templates/                # Runtime templates (docx, html, xlsx)
├── QUOTE_LIBRARY.txt         # Machine specs (optional but included)
├── frontend/                 # Next.js app
│   ├── package.json
│   ├── package-lock.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── postcss.config.mjs
│   ├── tailwind.config.ts (if exists)
│   ├── components.json
│   ├── public/
│   └── src/
├── data/                     # Empty dir, DB created at runtime
└── pyproject.toml            # For pip install -e . (src package)
```

Note: `frontend/.next/` and `frontend/node_modules/` are NOT shipped — `setup.bat` builds them on the target machine. This keeps the folder small and avoids platform-specific binaries.

## Files to Create

### 1. `build_deploy.py` (repo root)
Python script that:
- Creates `deploy/GOA_Server/` directory
- Copies required folders: `api/`, `src/`, `templates/`, `frontend/src/`, `frontend/public/`
- Copies required files: `requirements.txt`, `pyproject.toml`, `QUOTE_LIBRARY.txt`, frontend config files
- Generates production `requirements.txt` (strips pytest, dev deps)
- Generates `.env.template` with LAN IP placeholder and all required vars
- Copies/generates `start_server.bat`, `stop_server.bat`, `setup.bat`
- Creates empty `data/` directory
- Excludes: `.git/`, `tests/`, `docs/`, `__pycache__/`, `.venv/`, `node_modules/`, `.next/`, `*.pyc`, legacy folders

### 2. `deploy/GOA_Server/setup.bat`
One-time setup script:
```
1. python -m venv .venv
2. .venv\Scripts\pip install -r requirements.txt
3. cd frontend && npm install && npm run build
4. Prompt user to copy .env.template -> .env and fill in values
```

### 3. `deploy/GOA_Server/start_server.bat`
```
1. Detect LAN IP automatically (ipconfig parsing)
2. Start uvicorn in background: .venv\Scripts\python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
3. Start Next.js: cd frontend && npm start -- -H 0.0.0.0 -p 3000
4. Print "Server running at http://<LAN_IP>:3000"
```

### 4. `deploy/GOA_Server/stop_server.bat`
Kill uvicorn and node processes.

### 5. `deploy/GOA_Server/.env.template`
Pre-filled with all required vars, comments, and LAN IP placeholders.

## Key Decisions
- **No pre-built frontend**: Ship source, build on target. Avoids shipping 200MB+ of node_modules/.next and platform issues.
- **No pre-built venv**: Ship requirements.txt, create venv on target. Python venvs aren't portable across machines.
- **Include QUOTE_LIBRARY.txt**: It's 145KB and improves extraction quality.
- **Include all templates/**: The xlsx, docx, and html templates are all needed at runtime.
- **pyproject.toml included**: Needed for `pip install -e .` so `src/` package is importable.

## Prerequisites on Server PC
- Python 3.11+ installed and on PATH
- Node.js 18+ installed and on PATH
- Internet access (for pip install + npm install on first setup)

## Verification
1. Run `python build_deploy.py` — produces `deploy/GOA_Server/`
2. Copy `GOA_Server/` to another machine
3. Run `setup.bat` — installs deps, builds frontend
4. Configure `.env` with real values
5. Run `start_server.bat` — both servers start
6. Open `http://<server-ip>:3000` from another PC on LAN
7. Login with admin credentials, upload a PDF, run extraction
