# Phase 1 Auth Rollout Plan From `docs/INTERNAL_USE_FUTURE_INTEGRATION_PLAN.md`

## Summary
This starts with a repo-grounded gap audit, then implements Phase 1 auth/session end-to-end, while preparing ownership fields for future Phase 2 isolation (without enforcing isolation yet).

## Current Gap Snapshot (Grounded in Code)
1. Phase 0 LAN baseline is partially ready: CORS/env wiring and health endpoint exist in `api/main.py:48` and `api/main.py:59`, API base URL env is used in `frontend/src/lib/api.ts:13`, and Docker backend bind is LAN-ready in `Dockerfile:16`.
2. Phase 1 auth/session is not implemented: no `/api/auth/*` routes, no `users/sessions` DB tables, no cookie-based auth guard.
3. Phase 2 isolation is not implemented: no ownership columns in core domain tables.
4. Phase 3 per-user Gemini key is not implemented: LLM key usage is global env-based in `src/llm/client.py:155`.
5. Phase 4 reliability is partial: concurrency env exists in `api/services/processing_service.py:549`, but WAL/busy_timeout and request throttling are missing.

## Public API / Interface Changes
1. Add `POST /api/auth/login` with body `{ username, password }`; response returns authenticated user summary and sets HTTP-only session cookie.
2. Add `POST /api/auth/logout`; revokes session and clears cookie.
3. Add `GET /api/auth/me`; returns current authenticated user.
4. Add `GET /api/auth/users` (admin only); list users.
5. Add `POST /api/auth/users` (admin only); create user.
6. Add `POST /api/auth/users/{user_id}/reset-password` (admin only); rotate password.
7. All existing API routes require authentication except `/health` and `/api/auth/*`.
8. Frontend API client will send cookies for all requests (`credentials: "include"`), including direct fetches in `frontend/src/lib/api.ts`.

## Data Model and Migration Plan
1. Update `src/utils/db/base.py` with `users` table: `id`, `username UNIQUE`, `display_name`, `password_hash`, `role`, `is_active`, `created_date`, `modified_date`, `last_login_at`.
2. Update `src/utils/db/base.py` with `sessions` table: `id`, `user_id`, `token_hash UNIQUE`, `created_at`, `expires_at`, `last_seen_at`, `revoked_at`, `ip_address`, `user_agent`.
3. Update `src/utils/db/base.py` with `auth_audit_events` table: `id`, `user_id`, `event_type`, `metadata_json`, `ip_address`, `user_agent`, `occurred_at`.
4. Add nullable `owner_user_id` to `clients` and `projects`, plus indexes, for future isolation prep.
5. One-time backfill rule: assign existing `clients.owner_user_id` and `projects.owner_user_id` to bootstrap admin user.
6. Keep shared visibility behavior for now: no owner-based filtering in Phase 1.

## Backend Implementation Plan
1. Create `src/utils/db/auth.py` for user/session/audit persistence (create/find user, create/revoke session, list/create/reset users, audit writes, backfill ownership).
2. Export auth DB functions from `src/utils/db/__init__.py`.
3. Add security helpers in `api/services/auth_service.py` for password hashing (Argon2id), token generation, token hashing, cookie config, session TTL handling.
4. Add request dependencies in `api/dependencies/auth.py`: `get_current_user`, `require_authenticated_user`, `require_admin_user`.
5. Add `api/routers/auth.py` implementing login/logout/me/users/reset-password.
6. Register auth router in `api/main.py` as public; apply `Depends(require_authenticated_user)` to all other routers at include time.
7. Extend lifespan in `api/main.py` to run bootstrap-admin initialization after `init_db()`.
8. Bootstrap policy: if no users exist, require `AUTH_BOOTSTRAP_ADMIN_PASSWORD`; create admin user from env, else fail startup with clear error.
9. Ownership propagation updates:
10. Add optional `owner_user_id` handling in `src/utils/db/clients.py` for inserts.
11. Add optional `owner_user_id` handling in `src/utils/db/projects.py` for `create_project()` and `ensure_project_for_quote()`.
12. Pass current user id from router layer into quote/project creation flows (`api/routers/quotes.py`, `api/services/processing_service.py`, `api/routers/pm_dashboard.py`).
13. Add auth schemas in `api/models/schemas.py` for login/me/user-admin endpoints.
14. Add dependency `argon2-cffi` to `pyproject.toml` and `requirements.txt`.

## Frontend Implementation Plan
1. Add auth types and API contracts in `frontend/src/lib/types.ts`.
2. Update `fetchJson()` in `frontend/src/lib/api.ts` to always include `credentials: "include"`.
3. Update direct `fetch` calls in `frontend/src/lib/api.ts` (shipping/COR generation) to include credentials.
4. Add auth client functions in `frontend/src/lib/api.ts`: `login`, `logout`, `fetchCurrentUser`, `listUsers`, `createUser`, `resetUserPassword`.
5. Create login route `frontend/src/app/login/page.tsx` with a client component for username/password form and server error handling.
6. Update `frontend/src/components/layout/app-shell.tsx` with auth guard behavior:
7. Bypass shell chrome for `/login`.
8. On protected routes, call `/api/auth/me`; if 401, redirect to `/login?next=<path>`.
9. Update `frontend/src/components/layout/header.tsx` to show current user and logout action.
10. Do not add admin management UI in this phase; admin user management is API-only.

## Config and Docs Changes
1. Extend `.env.example` with:
2. `AUTH_BOOTSTRAP_ADMIN_USERNAME=admin`
3. `AUTH_BOOTSTRAP_ADMIN_PASSWORD=`
4. `AUTH_SESSION_TTL_HOURS=12`
5. `AUTH_COOKIE_NAME=goa_session`
6. `AUTH_COOKIE_SECURE=false`
7. `AUTH_SESSION_PEPPER=`
8. Update `README.md` with login/bootstrap steps and LAN cookie/CORS guidance.
9. Update `docs/INTERNAL_USE_FUTURE_INTEGRATION_PLAN.md` status notes to reflect completed PM dashboard baseline and new auth rollout details.

## Test Cases and Scenarios
1. Add `tests/test_database/test_auth.py` for user/session CRUD, token hash lookup, revoke logic, ownership backfill behavior.
2. Add `tests/test_auth_router.py` for:
3. Successful login sets cookie and returns user.
4. Invalid password returns 401.
5. `/api/auth/me` returns 200 with cookie and 401 without.
6. Logout revokes session and invalidates cookie.
7. Admin can create/reset users; standard user gets 403.
8. Add `tests/test_auth_protection.py` verifying representative existing endpoints return 401 when unauthenticated and 200 when authenticated.
9. Update current API endpoint tests using `TestClient(app)` to authenticate before requests (or fixture-injected auth cookie).
10. Add frontend integration checks (manual or test harness): login redirect, session persistence on refresh, logout redirect, 401 handling UX.

## Rollout and Acceptance Criteria
1. Local dry-run: migrate DB, bootstrap admin, verify login/logout/me, verify protected endpoint behavior.
2. Internal LAN staging: host frontend/backend on host IP, set `NEXT_PUBLIC_API_URL` and `CORS_ORIGINS` to host IP values, verify multi-user concurrent sessions.
3. Acceptance criteria:
4. Every authenticated user has an independent session cookie.
5. Protected endpoints reject unauthenticated access with 401.
6. Existing workflow pages work unchanged after login.
7. Existing rows are ownership-tagged to bootstrap admin; shared visibility remains intact.

## Assumptions and Defaults Locked
1. User provisioning model: bootstrap admin from env plus admin-managed user APIs.
2. Data strategy: prepare ownership columns now, enforce isolation later.
3. Session TTL default: 12 hours.
4. Role model: `admin` and `standard`.
5. Auth scope: all API routes except `/health` and `/api/auth/*`.
6. Admin UX in Phase 1: API-only, no new admin frontend page.
7. Ownership backfill for existing records: assign to bootstrap admin.
