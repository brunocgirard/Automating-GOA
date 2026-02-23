# Internal Use Future Integration Plan

Created: 2026-02-20
Scope: Internal multi-user deployment on one host machine, with optional per-user Gemini API keys.

## 1. Objectives

- Host the application on one internal machine and allow peer access over LAN.
- Add real user sessions (login/logout) instead of shared anonymous access.
- Support one of two data visibility models: shared data with separate login sessions, or isolated per-user dashboards/data.
- Optionally allow each user to bring their own Gemini API key.

## 2. Current State (Observed)

- Frontend and backend are deployed as separate services (Next.js + FastAPI).
- Backend CORS is configured through `CORS_ORIGINS`.
- Frontend API base URL is configured via `NEXT_PUBLIC_API_URL`.
- No authentication/session enforcement is currently in place.
- SQLite is the active data store.
- Gemini key is global from environment variables (`GOOGLE_API_KEY` / `GEMINI_API_KEY`).

## 3. Target Internal Architecture

- One host PC runs the FastAPI backend (LAN-accessible).
- One host PC runs the Next.js frontend (LAN-accessible).
- One host PC stores the SQLite DB on local disk (initially).
- Peer PCs use a launcher `.bat` file to open the frontend URL in browser.

Example peer launcher:

```bat
@echo off
start http://<HOST_IP>:3000
```

## 4. Implementation Phases

### Phase 0: LAN Hosting Baseline

- Run backend on host bind address (`0.0.0.0`) and fixed port.
- Run frontend in production mode on host bind address.
- Set `NEXT_PUBLIC_API_URL=http://<HOST_IP>:8000`.
- Set `CORS_ORIGINS=http://<HOST_IP>:3000,http://localhost:3000,http://127.0.0.1:3000`.
- Open Windows firewall inbound rules for frontend/backend ports.

Acceptance:

- Multiple peers can open UI from browser.
- Peers can perform upload/process/generate workflows.

### Phase 1: Authentication + Session Management

- Add `users` and `sessions` tables.
- Add `POST /api/auth/login`.
- Add `POST /api/auth/logout`.
- Add `GET /api/auth/me`.
- Use HTTP-only secure cookies for session tokens.
- Add FastAPI dependency/middleware to resolve current user and protect routes.
- Add frontend login page and route guard.

Acceptance:

- Each user has independent login session.
- Unauthenticated requests to protected endpoints are rejected.

### Phase 2: Dashboard/Data Isolation

Choose one policy:

- Option A (shared data): users are authenticated but see same dataset.
- Option B (isolated data): each user sees only owned data.

For Option B:

- Add ownership fields (`owner_user_id` or `team_id`) to domain tables.
- Backfill existing rows with migration rules.
- Scope all read/write queries to current user/team.

Acceptance:

- User A cannot see/edit User B records (unless explicitly team-shared).

### Phase 3: Per-User Gemini API Keys (Optional BYOK)

- Add encrypted key storage in user profile (server-side only).
- Add settings endpoints for key management (set/replace/remove/test).
- On extraction/generation requests, resolve model client by current user key.
- Keep fallback policy configurable: user key required, or user key preferred with org default fallback.
- Update model/client cache strategy to avoid cross-user key reuse.

Acceptance:

- Each user can run LLM calls with their own quota/billing key.
- Keys are never exposed in frontend code or logs.

### Phase 4: Concurrency and Reliability Hardening

- Avoid output filename collisions by adding unique IDs/timestamps.
- Apply SQLite concurrency tuning (`WAL`, `busy_timeout`).
- Keep/tune `LLM_EXTRACTION_MAX_CONCURRENCY` based on host capacity.
- Add request throttling and graceful error messages for rate limit events.
- Evaluate migration from SQLite to Postgres if concurrent writes increase.

Acceptance:

- Stable behavior with concurrent users performing extraction/generation.

## 5. Security Requirements

- Passwords hashed with strong KDF (Argon2id or bcrypt).
- Session cookies: `HttpOnly`, `SameSite`, `Secure` when TLS is enabled.
- API keys encrypted at rest with server-side encryption key.
- Audit trail for auth events and key updates.
- Least-privilege route protection by default.

## 6. Data Migration Notes

- Add migration scripts for auth tables.
- Add migration scripts for ownership columns.
- Add migration scripts for optional user settings/API key fields.
- Define one-time strategy for existing rows: assign to admin bootstrap user, or map by import batch.

## 7. Operational Runbook (Internal)

- Host machine startup sequence: start backend, start frontend, then run health checks (`/health` and frontend load test).
- Backup policy: daily DB backup and generated document archive retention.
- Incident fallback: disable per-user key mode and use org default key, then lower LLM concurrency when host is overloaded.

## 8. Recommended Rollout Order

1. Phase 0 (LAN baseline)
2. Phase 1 (auth sessions)
3. Phase 2 (data isolation policy)
4. Phase 4 hardening
5. Phase 3 (per-user Gemini keys)

Reasoning:

- Session/auth should precede per-user key support.
- Reliability hardening should happen before broad internal rollout.

## 9. Open Decisions

- Shared dashboard vs isolated dashboard (required decision).
- Per-user Gemini key mandatory or optional.
- Keep SQLite with WAL vs move directly to Postgres.
- Single organization role model vs multi-role RBAC.
