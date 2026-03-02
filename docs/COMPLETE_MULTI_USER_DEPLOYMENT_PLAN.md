# Complete Multi-User Deployment Plan

Created: 2026-02-23
Scope: Deploy QuoteFlow on one host machine, enable PM access over LAN with individual logins and per-user Gemini API keys.

---

## Overview

This document consolidates all implementation phases needed to run QuoteFlow as a multi-user internal tool. One host PC runs the backend and frontend; other PMs connect via browser. Each PM has their own login and their own Gemini API key.

**Phases:**

| Phase | What | Status |
|-------|------|--------|
| 0 | LAN Hosting Baseline | Not started |
| 1 | Authentication + Sessions | Not started |
| 2 | Per-User Gemini API Keys (BYOK) | Not started |
| 3 | Ownership Columns + Data Prep | Not started |
| 4 | Concurrency & Reliability Hardening | Not started |

---

## Phase 0: LAN Hosting Baseline

**Goal:** Other PMs can open `http://<HOST_IP>:3000` in their browser and use the app.

### Host Machine Setup

1. **Backend** — Run FastAPI bound to all interfaces:
   ```bash
   uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```

2. **Frontend** — Build and run Next.js in production mode:
   ```bash
   cd frontend
   npm run build
   npm start -- -H 0.0.0.0 -p 3000
   ```

3. **Environment variables** on host `.env`:
   ```
   NEXT_PUBLIC_API_URL=http://<HOST_IP>:8000
   CORS_ORIGINS=http://<HOST_IP>:3000,http://localhost:3000,http://127.0.0.1:3000
   ```

   > **Important:** `NEXT_PUBLIC_API_URL` must use the LAN IP (e.g., `192.168.1.50`), not `localhost`. This env var gets baked into the browser-side JavaScript at build time. If it says `localhost`, other PMs' browsers will try to call their own machine instead of the host.

4. **Windows Firewall** — Open inbound TCP rules for ports 3000 and 8000:
   ```
   Windows Defender Firewall > Advanced Settings > Inbound Rules > New Rule
   - Rule type: Port
   - TCP, Specific local ports: 3000, 8000
   - Action: Allow the connection
   - Profile: Private (or Domain, depending on network)
   ```

5. **Peer launcher** — Create a `.bat` file for other PMs:
   ```bat
   @echo off
   start http://<HOST_IP>:3000
   ```

### What Other PMs Need

Nothing. Just a browser.

### Acceptance Criteria

- [ ] Multiple PMs can open the UI from their browsers.
- [ ] PMs can upload PDFs, run extraction, and generate documents.
- [ ] `/health` endpoint responds from peer machines.

---

## Phase 1: Authentication + Sessions

**Goal:** Each PM logs in with their own account. Unauthenticated requests are rejected.

### 1.1 Database Schema Changes

Add three new tables and ownership columns to `src/utils/db/base.py`:

**`users` table:**
```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'standard',  -- 'admin' or 'standard'
    is_active INTEGER NOT NULL DEFAULT 1,
    gemini_api_key_encrypted TEXT,          -- Phase 2: per-user key
    created_date TEXT NOT NULL,
    modified_date TEXT NOT NULL,
    last_login_at TEXT
);
```

**`sessions` table:**
```sql
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT,
    revoked_at TEXT,
    ip_address TEXT,
    user_agent TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
```

**`auth_audit_events` table:**
```sql
CREATE TABLE IF NOT EXISTS auth_audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    event_type TEXT NOT NULL,  -- 'login', 'logout', 'login_failed', 'password_reset', 'key_updated'
    metadata_json TEXT,
    ip_address TEXT,
    user_agent TEXT,
    occurred_at TEXT NOT NULL
);
```

**Ownership columns** (for future data isolation prep):
```sql
ALTER TABLE clients ADD COLUMN owner_user_id INTEGER;
ALTER TABLE projects ADD COLUMN owner_user_id INTEGER;
```

### 1.2 Backend: Auth Database Layer

**New file: `src/utils/db/auth.py`**

Functions to implement:
- `create_user(username, display_name, password_hash, role)` -> user row
- `find_user_by_username(username)` -> user row or None
- `find_user_by_id(user_id)` -> user row or None
- `list_users()` -> all users
- `update_user_password(user_id, new_password_hash)`
- `deactivate_user(user_id)`
- `create_session(user_id, token_hash, expires_at, ip_address, user_agent)` -> session row
- `find_session_by_token_hash(token_hash)` -> session + user or None
- `revoke_session(session_id)`
- `revoke_all_user_sessions(user_id)`
- `touch_session(session_id)` -> update `last_seen_at`
- `write_audit_event(user_id, event_type, metadata, ip, user_agent)`
- `backfill_ownership(admin_user_id)` -> set `owner_user_id` on existing clients/projects
- `update_user_gemini_key(user_id, encrypted_key)` (Phase 2 prep)
- `get_user_gemini_key(user_id)` -> encrypted key or None (Phase 2 prep)

Export from `src/utils/db/__init__.py`.

### 1.3 Backend: Auth Service

**New file: `api/services/auth_service.py`**

- Password hashing: `argon2-cffi` (Argon2id)
  - `hash_password(plain)` -> hash string
  - `verify_password(plain, hash)` -> bool
- Session token: `secrets.token_urlsafe(32)`
- Token hashing: `hashlib.sha256(token).hexdigest()` (store hash, not raw token)
- Cookie config helper:
  ```python
  COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "goa_session")
  COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
  SESSION_TTL_HOURS = int(os.getenv("AUTH_SESSION_TTL_HOURS", "12"))
  ```
- Session pepper (optional): `AUTH_SESSION_PEPPER` env var mixed into token hash

### 1.4 Backend: Auth Dependencies

**New file: `api/dependencies/auth.py`**

```python
async def get_current_user(request: Request) -> Optional[UserRow]:
    """Extract session cookie, look up session, return user or None."""

async def require_authenticated_user(user = Depends(get_current_user)) -> UserRow:
    """Raise HTTPException(401) if no valid session."""

async def require_admin_user(user = Depends(require_authenticated_user)) -> UserRow:
    """Raise HTTPException(403) if user.role != 'admin'."""
```

### 1.5 Backend: Auth Router

**New file: `api/routers/auth.py`**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/login` | POST | Public | Validate credentials, create session, set cookie |
| `/api/auth/logout` | POST | Authenticated | Revoke session, clear cookie |
| `/api/auth/me` | GET | Authenticated | Return current user info |
| `/api/auth/users` | GET | Admin | List all users |
| `/api/auth/users` | POST | Admin | Create new user |
| `/api/auth/users/{user_id}/reset-password` | POST | Admin | Reset user password |

### 1.6 Backend: App Registration

Update `api/main.py`:

1. Register auth router as **public** (no auth dependency):
   ```python
   app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
   ```

2. Apply `Depends(require_authenticated_user)` to all other routers:
   ```python
   app.include_router(quotes_router, prefix="/quotes", dependencies=[Depends(require_authenticated_user)])
   # ... same for all other routers
   ```

3. Extend lifespan to bootstrap admin user:
   ```python
   async def lifespan(app):
       init_db()
       bootstrap_admin_user()  # Create admin if no users exist
       yield
   ```

4. Bootstrap policy:
   - If zero users exist in DB, read `AUTH_BOOTSTRAP_ADMIN_USERNAME` and `AUTH_BOOTSTRAP_ADMIN_PASSWORD` from env.
   - If password env is empty/missing, **fail startup** with clear error message.
   - Create the admin user with role `admin`.

5. Add `allow_credentials=True` to CORS middleware (required for cookies):
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=origins,
       allow_credentials=True,  # ADD THIS
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

### 1.7 Backend: Auth Schemas

Add to `api/models/schemas.py`:

```python
class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str]
    role: str
    is_active: bool
    has_gemini_key: bool  # Phase 2: True if user has set their key

class CreateUserRequest(BaseModel):
    username: str
    display_name: Optional[str]
    password: str
    role: str = "standard"

class ResetPasswordRequest(BaseModel):
    new_password: str
```

### 1.8 Frontend: Auth Integration

**Update `frontend/src/lib/api.ts`:**
- Add `credentials: "include"` to `fetchJson()` and all direct `fetch()` calls.
- Add auth API functions: `login()`, `logout()`, `fetchCurrentUser()`, `listUsers()`, `createUser()`, `resetUserPassword()`.

**Update `frontend/src/lib/types.ts`:**
- Add `User`, `LoginRequest`, `CreateUserRequest` interfaces.

**New file: `frontend/src/app/login/page.tsx`:**
- Username/password form.
- On submit, call `POST /api/auth/login`.
- On success, redirect to `/` (or `?next=` param).
- On error, show inline error message.

**Update `frontend/src/components/layout/header.tsx`:**
- Show current user display name.
- Add logout button that calls `POST /api/auth/logout` then redirects to `/login`.

**Auth guard (app shell level):**
- On protected routes, call `GET /api/auth/me`.
- If 401, redirect to `/login?next=<current_path>`.
- Bypass auth check on `/login` route.

### 1.9 Dependencies

Add to `requirements.txt`:
```
argon2-cffi>=23.1.0
```

### 1.10 Environment Variables

Add to `.env.example`:
```bash
# Auth (Phase 1)
AUTH_BOOTSTRAP_ADMIN_USERNAME=admin
AUTH_BOOTSTRAP_ADMIN_PASSWORD=           # REQUIRED on first run
AUTH_SESSION_TTL_HOURS=12
AUTH_COOKIE_NAME=goa_session
AUTH_COOKIE_SECURE=false                 # Set true if using HTTPS
AUTH_SESSION_PEPPER=                     # Optional extra entropy for token hashing
```

### Phase 1 Acceptance Criteria

- [ ] Admin user is created on first startup from env vars.
- [ ] PMs can log in with username/password.
- [ ] Each PM has an independent session cookie.
- [ ] Protected endpoints return 401 without valid session.
- [ ] `/health` and `/api/auth/*` remain public.
- [ ] Frontend redirects to login page when unauthenticated.
- [ ] Existing workflows work unchanged after login.

---

## Phase 2: Per-User Gemini API Keys (BYOK)

**Goal:** Each PM enters their own Gemini API key. The app uses that key for their extraction/generation requests.

### 2.1 Key Storage

The `users.gemini_api_key_encrypted` column (added in Phase 1 schema) stores the key encrypted at rest.

**Encryption approach:**
- Server-side symmetric encryption using `cryptography.fernet`.
- Encryption key from env: `GEMINI_KEY_ENCRYPTION_SECRET`.
- `encrypt_gemini_key(plain_key)` -> encrypted string.
- `decrypt_gemini_key(encrypted_key)` -> plain key.

Add to `api/services/auth_service.py` (or new `api/services/key_service.py`).

### 2.2 Key Management API

Add endpoints to `api/routers/auth.py`:

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/me/gemini-key` | PUT | Authenticated | Set/replace Gemini key |
| `/api/auth/me/gemini-key` | DELETE | Authenticated | Remove Gemini key |
| `/api/auth/me/gemini-key/test` | POST | Authenticated | Test key validity (make a lightweight Gemini API call) |

**Schemas:**
```python
class SetGeminiKeyRequest(BaseModel):
    api_key: str

class GeminiKeyTestResponse(BaseModel):
    valid: bool
    error: Optional[str]
```

**Key validation test:** Call `genai.GenerativeModel("gemini-2.5-flash-lite").count_tokens("test")` with the user's key. If it succeeds, the key is valid.

### 2.3 LLM Client Refactor

**Current state** (`src/llm/client.py:154-160`):
```python
def _create_model(model_name):
    api_key = os.getenv("GOOGLE_API_KEY")  # Single global key
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)
```

**New approach** — Per-request key resolution:

```python
import google.generativeai as genai

# Cache: user_id -> configured client (cleared on key change)
_user_clients: dict[int, genai.GenerativeModel] = {}

def get_model_for_user(user_id: int, model_name: str) -> genai.GenerativeModel:
    """
    Resolve Gemini client for a specific user.
    1. Look up user's encrypted key from DB.
    2. Decrypt it.
    3. Create/cache a model instance configured with that key.
    """
    # If user has no key, raise clear error
    # If key is cached and unchanged, return cached model
    # Otherwise create new model with user's key

def invalidate_user_client_cache(user_id: int):
    """Call when user updates/removes their key."""
    _user_clients.pop(user_id, None)
```

**No fallback to org key.** If a PM hasn't set their key, extraction/generation requests return a clear error: "Please set your Gemini API key in settings before processing."

### 2.4 Threading the User Through Extraction

The extraction pipeline needs to know *which user* is making the request so it can resolve the right Gemini key.

**Call chain:**
```
POST /processing/extract (request + current_user from auth dependency)
  -> processing_service.run_extraction(machine_id, user_id=current_user.id)
    -> configure_gemini_client(user_id=user_id)  # resolve per-user key
      -> src/llm/client.get_model_for_user(user_id, model_name)
```

Files to update:
- `api/routers/processing.py` — Pass `current_user.id` to service calls.
- `api/services/processing_service.py` — Accept `user_id` parameter, pass to LLM client.
- `src/llm/client.py` — Accept `user_id`, resolve key from DB.
- `src/llm/extraction.py` — Accept model instance or user_id for LangChain chain setup.

### 2.5 Frontend: Key Settings UI

**New component: Settings section in header dropdown or dedicated settings page.**

Simple UI:
- Text input for Gemini API key (masked, like a password field).
- "Save Key" button -> `PUT /api/auth/me/gemini-key`.
- "Test Key" button -> `POST /api/auth/me/gemini-key/test` -> show success/error.
- "Remove Key" button -> `DELETE /api/auth/me/gemini-key`.
- Status indicator: "Key set" / "No key configured".

**UX guard:** If a PM tries to run extraction without a key set, show a clear message directing them to settings.

### 2.6 Security Constraints

- Keys are **never** returned in API responses (only `has_gemini_key: bool`).
- Keys are **never** logged.
- Client cache is per-user; no cross-user key leakage.
- Audit event logged when key is set/removed/changed.

### 2.7 Dependencies

Add to `requirements.txt`:
```
cryptography>=42.0.0
```

### 2.8 Environment Variables

Add to `.env.example`:
```bash
# Per-user Gemini key encryption (Phase 2)
GEMINI_KEY_ENCRYPTION_SECRET=            # REQUIRED - Fernet key, generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Phase 2 Acceptance Criteria

- [ ] Each PM can set their own Gemini API key via the UI.
- [ ] Key test endpoint validates the key against Gemini API.
- [ ] Extraction/generation uses the requesting PM's key.
- [ ] PMs without a key get a clear error, not a crash.
- [ ] Keys are encrypted at rest and never exposed in API responses or logs.
- [ ] Changing/removing a key invalidates the cached client.

---

## Phase 3: Ownership Columns + Data Prep

**Goal:** Tag data with the user who created it. Shared visibility for now; isolation enforcement deferred.

### 3.1 Schema

Ownership columns added in Phase 1 (`clients.owner_user_id`, `projects.owner_user_id`).

### 3.2 Ownership Propagation

- When a PM uploads a quote -> set `clients.owner_user_id = current_user.id`.
- When a PM creates a project -> set `projects.owner_user_id = current_user.id`.
- Backfill existing rows to bootstrap admin user ID on first migration.

### 3.3 Visibility Policy

**Phase 3 policy: Shared.** All PMs see all data regardless of owner. The `owner_user_id` is stored for auditing and future isolation if needed.

### Phase 3 Acceptance Criteria

- [ ] New quotes/projects are tagged with the creating user's ID.
- [ ] Existing rows are backfilled to admin user.
- [ ] All PMs still see all data (no filtering by owner).

---

## Phase 4: Concurrency & Reliability Hardening

**Goal:** Stable behavior with multiple PMs running extraction/generation simultaneously.

### 4.1 SQLite Tuning

Add to `get_connection()` in `src/utils/db/base.py`:
```python
conn = sqlite3.connect(normalized_path)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
```

WAL mode allows concurrent reads while one writer proceeds. `busy_timeout` prevents immediate `SQLITE_BUSY` errors.

### 4.2 Output File Collision Prevention

Current risk: Two PMs generating documents for different quotes could collide on filenames.

Fix: Include `user_id` or UUID in generated file paths:
```
output/GOA_{quote_ref}_{user_id}_{timestamp}.html
```

Files to update:
- `src/utils/html_doc_filler.py`
- `src/utils/doc_filler.py`
- `api/services/processing_service.py` (output path construction)

### 4.3 Per-User Concurrency Awareness

Current: `LLM_EXTRACTION_MAX_CONCURRENCY=3` is global.

With multiple PMs, the global semaphore still applies (total concurrent LLM calls across all users = 3). This is acceptable for initial deployment. If needed later, implement per-user queuing.

### 4.4 Graceful Error Messages

When a PM's extraction is queued behind others:
- Return a clear status message: "Processing queued, other extractions in progress."
- Frontend shows a waiting indicator instead of a timeout error.

### Phase 4 Acceptance Criteria

- [ ] SQLite uses WAL mode and busy_timeout.
- [ ] Two PMs can run extractions simultaneously without DB errors.
- [ ] Generated files never collide.
- [ ] PMs see clear status when their request is queued.

---

## Implementation Order

```
Phase 0: LAN Hosting Baseline
    ↓
Phase 1: Authentication + Sessions
    ↓
Phase 2: Per-User Gemini API Keys
    ↓
Phase 3: Ownership Columns + Data Prep
    ↓
Phase 4: Concurrency Hardening
```

Phase 0 can be tested immediately with the current codebase (no code changes, just deployment config). Phases 1-2 are the core development work. Phases 3-4 are lower effort and can be done alongside Phase 2.

---

## New Files Summary

| File | Phase | Purpose |
|------|-------|---------|
| `src/utils/db/auth.py` | 1 | User/session/audit DB operations |
| `api/services/auth_service.py` | 1 | Password hashing, token generation, cookie config |
| `api/dependencies/auth.py` | 1 | FastAPI auth dependencies (get_current_user, etc.) |
| `api/routers/auth.py` | 1 | Auth endpoints (login, logout, me, users, keys) |
| `frontend/src/app/login/page.tsx` | 1 | Login page |

## Modified Files Summary

| File | Phase | Changes |
|------|-------|---------|
| `src/utils/db/base.py` | 1 | Add users, sessions, auth_audit_events tables + ownership columns |
| `src/utils/db/__init__.py` | 1 | Export auth functions |
| `api/main.py` | 1 | Register auth router, apply auth deps, bootstrap admin, CORS credentials |
| `api/models/schemas.py` | 1-2 | Auth request/response schemas |
| `frontend/src/lib/api.ts` | 1-2 | credentials: "include", auth API functions |
| `frontend/src/lib/types.ts` | 1 | Auth type interfaces |
| `frontend/src/components/layout/header.tsx` | 1-2 | User display, logout, key settings |
| `.env.example` | 1-2 | Auth + encryption env vars |
| `requirements.txt` | 1-2 | argon2-cffi, cryptography |
| `src/llm/client.py` | 2 | Per-user key resolution |
| `api/services/processing_service.py` | 2 | Accept user_id, pass to LLM client |
| `api/routers/processing.py` | 2 | Pass current_user to service |
| `src/utils/db/base.py` | 4 | WAL mode, busy_timeout |

---

## Environment Variables (Complete)

```bash
# === Existing ===
GEMINI_API_KEY=                          # Still used as fallback for admin/bootstrap only
GOOGLE_API_KEY=
GOA_LLM_MODEL=gemini-2.5-flash-lite
DATABASE_PATH=data/crm_data.db
CORS_ORIGINS=http://<HOST_IP>:3000,http://localhost:3000
NEXT_PUBLIC_API_URL=http://<HOST_IP>:8000

# === Phase 1: Auth ===
AUTH_BOOTSTRAP_ADMIN_USERNAME=admin
AUTH_BOOTSTRAP_ADMIN_PASSWORD=           # REQUIRED on first run
AUTH_SESSION_TTL_HOURS=12
AUTH_COOKIE_NAME=goa_session
AUTH_COOKIE_SECURE=false
AUTH_SESSION_PEPPER=

# === Phase 2: Per-User Keys ===
GEMINI_KEY_ENCRYPTION_SECRET=            # REQUIRED - Fernet key
```

---

## Test Plan

### Phase 1 Tests
- `tests/test_database/test_auth.py` — User/session CRUD, token hash lookup, revoke logic, ownership backfill.
- `tests/test_auth_router.py` — Login sets cookie, invalid password returns 401, `/me` works with/without cookie, logout revokes session, admin create/reset user, standard user gets 403 on admin endpoints.
- `tests/test_auth_protection.py` — Existing endpoints return 401 unauthenticated, 200 authenticated.
- Update existing API tests to include auth cookie fixture.

### Phase 2 Tests
- `tests/test_gemini_key.py` — Set/get/delete key, encryption round-trip, key test endpoint, extraction uses correct user key.

### Manual / Integration Tests
- Login redirect works from any page.
- Session persists on browser refresh.
- Logout redirects to login.
- PM without Gemini key sees clear error on extraction.
- PM with valid key can extract successfully.
- Two PMs extracting simultaneously don't interfere.
