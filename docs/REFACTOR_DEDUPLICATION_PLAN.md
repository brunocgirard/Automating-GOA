# Refactor & Deduplication Plan

> Generated: 2026-03-01
> Branch: `refactor/deduplication` (create from `development`)
> Strategy: Extract shared code into utility modules, update imports, verify tests pass after each phase.

---

## Phase 1: API Router Shared Utilities ✅ COMPLETE

**Target**: `api/routers/_helpers.py` (created)
**Estimated lines saved**: ~250
**Status**: Implemented. All 7 business routers refactored, plus `auth.py` cleanup completed.

### Task 1.1 — Extract `_scope_kwargs()` ✅

- [x] Create `api/routers/_helpers.py`
- [x] Move `_scope_kwargs(current_user)` into `_helpers.py` as `scope_kwargs()`
- [x] Remove the local `_scope_kwargs` definition from all 7 files
- [x] Add `from api.routers._helpers import scope_kwargs` to each file
- [x] Find-replace all call sites: `_scope_kwargs(current_user)` -> `scope_kwargs(current_user)`

### Task 1.2 — Extract `load_quote_or_404()`

- [x] Add to `api/routers/_helpers.py`:
  ```python
  from fastapi import HTTPException, status
  from src.utils.db import get_client_by_id

  def load_quote_or_404(quote_id: int, current_user: dict) -> dict:
      return require(get_client_by_id(quote_id, **scope_kwargs(current_user)), "Quote not found.")
  ```
- [x] Remove local `_load_quote_or_404` from shipping.py and cor.py
- [x] Update imports and call sites in both files

### Task 1.3 — Extract generic `require()` (404 guard) ✅

- [x] Added `require()` to `_helpers.py`
- [x] Refactored 404 guard sites across all 7 routers

### Task 1.4 — Extract PDF upload validation ✅

- [x] Added `validate_pdf_upload()` to `_helpers.py`
- [x] Replaced inline validation in quotes.py and pm_dashboard.py

### Task 1.5 — Extract document generation error handler ✅

- [x] Added `handle_doc_generation()` to `_helpers.py`
- [x] Replaced try/except blocks in shipping.py and cor.py

### Task 1.6 — Extract PM task auto-advance wrapper ✅

- [x] Added `try_advance_pm_task()` to `_helpers.py`
- [x] Replaced inline try/except in shipping.py, cor.py, and processing.py

### Task 1.7 — Extract user ID helper ✅

- [x] Added `user_id()` to `_helpers.py`
- [x] Replaced in 7 business routers
- [x] Replaced the remaining 5x `int(current_user["id"])` usages in `api/routers/auth.py`

### Risks / Notes — Phase 1

- ~~`_helpers.py` must not import router modules to avoid circular imports.~~ Confirmed safe.
- ~~The `require()` helper changes return semantics slightly~~ Confirmed working.
- **Stale reference fixed**: Plan originally referenced `find_quote_by_id` — actual function is `get_client_by_id`. Corrected.

---

## Phase 2: DB Layer Shared Utilities ✅ CORE HELPER PASS COMPLETE

**Target**: `src/utils/db/base.py` (extend existing), `src/utils/db/_helpers.py` (new file)
**Estimated lines saved**: ~180
**Status**: Implemented in `base.py`. The planned `src/utils/db/_helpers.py` file was not needed.

### Task 2.1 — Migrate remaining files to a safe connection context helper ✅

- [x] Added `connection_context()` to `src/utils/db/base.py` as a non-breaking context manager wrapper around `get_connection()`
- [x] Kept `get_connection()` as a plain connection factory for backward compatibility
- [x] Replaced `conn = None; try: conn = sqlite3.connect(db_path); ... finally: if conn: conn.close()` with `with connection_context(db_path) as conn:` in:
  - `src/utils/db/documents.py`
  - `src/utils/db/items.py`
  - `src/utils/db/templates.py`
  - `src/utils/db/modifications.py`
  - `src/utils/db/few_shot.py`
- [x] Added `from src.utils.db.base import connection_context` to each migrated file
- [x] **Adaptation**: did not convert `get_connection()` itself into a context manager, because existing callers depend on it returning a `sqlite3.Connection`
- [x] Original proposed implementation was replaced with:
  ```python
  @contextmanager
  def connection_context(db_path: str = DB_PATH):
      conn = get_connection(db_path)
      try:
          yield conn
      finally:
          conn.close()
  ```

### Task 2.2 — Consolidate `_timestamp()` into `base.py` ✅

- [x] Added `timestamp()` to `src/utils/db/base.py`
- [x] Removed local `_timestamp()` from:
  - `src/utils/db/projects.py`
  - `src/utils/db/shipping.py`
  - `src/utils/db/cor.py`
- [x] Updated call sites to use `timestamp()`
- [x] Re-export from `src/utils/db/__init__.py` was not required
- [x] Implemented as:
  ```python
  def timestamp() -> str:
      return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  ```

### Task 2.3 — Consolidate `_owner_scope_clause()` into `base.py` ✅

- [x] Added `owner_scope_clause()` to `src/utils/db/base.py`
- [x] Removed local copies from:
  - `src/utils/db/clients.py`
  - `src/utils/db/machines.py`
  - `src/utils/db/projects.py` (`_project_scope_clause`)
- [x] Updated imports and call sites in all three files
- [x] Implemented as:
  ```python
  def owner_scope_clause(
      owner_user_id: int | None = None,
      include_all_for_admin: bool = False,
      table_alias: str = "",
  ) -> tuple[str, list]:
      """Return (SQL WHERE fragment, params list) for ownership filtering."""
      prefix = f"{table_alias}." if table_alias else ""
      if include_all_for_admin or not owner_user_id:
          return "", []
      return f"AND {prefix}owner_user_id = ?", [owner_user_id]
  ```

### Task 2.4 — Add `row_to_dict()` and `rows_to_dicts()` to `base.py` ✅

- [x] Added `row_to_dict()` and `rows_to_dicts()` to `src/utils/db/base.py`
- [x] Replaced `dict(row)` / `[dict(row) ...]` patterns across the DB modules touched in Phase 2
- [x] Implemented as:
  ```python
  def row_to_dict(row) -> dict | None:
      return dict(row) if row else None

  def rows_to_dicts(rows) -> list[dict]:
      return [dict(r) for r in rows]
  ```

### Task 2.5 — Extract `safe_json_loads()` into `base.py` ✅

- [x] Added `safe_json_loads()` to `src/utils/db/base.py`
- [x] Replaced inline JSON parse-with-fallback across:
  - `src/utils/db/cor.py`
  - `src/utils/db/shipping.py`
  - `src/utils/db/templates.py`
  - `src/utils/db/projects.py`
  - `src/utils/db/modifications.py`
  - `src/utils/db/machines.py`
- [x] Kept explicit `json.loads()` where failure should remain hard-fail or where direct serialization logic is clearer
- [x] Implemented as:
  ```python
  import json

  def safe_json_loads(value, default=None):
      if not value:
          return default
      try:
          return json.loads(value)
      except (json.JSONDecodeError, TypeError):
          return default
  ```

### Task 2.6 — Consolidate `_to_text()` / `_as_text()` ✅

- [x] Added `to_text()` to `src/utils/db/base.py`
- [x] Removed from:
  - `src/utils/db/few_shot.py`
  - `src/utils/db/cor.py`
- [x] Updated call sites
- [x] Implemented as:
  ```python
  def to_text(value) -> str:
      return str(value).strip() if value else ""
  ```

### Risks / Notes — Phase 2

- **Validated adaptation**: `get_connection()` was intentionally left backward-compatible; `connection_context()` handles the close-on-exit behavior.
- Row-to-dict replacement is mechanical; additional low-value cleanups remain in untouched modules like `src/utils/db/auth.py`.
- `safe_json_loads` defaults were inspected per call site in the touched files.

---

## Phase 3: Service Layer Shared Utilities ✅ COMPLETE

**Target**: `api/services/_doc_helpers.py` (new file), `api/services/_env_helpers.py` (new file)
**Estimated lines saved**: ~200
**Status**: Implemented. Shared document and env helpers added, and all 5 target service modules were refactored.

### Task 3.1 — Extract text/number converters ✅

- [x] Created `api/services/_doc_helpers.py`
- [x] Added `to_text()`, `to_float()`, `slugify()`, and `current_date()`
- [x] Removed local copies from:
  - `api/services/cor_doc_service.py` (`_to_text`, `_to_float`, `_slugify`, `_current_date`)
  - `api/services/shipping_doc_service.py` (`_to_text`, `_to_float`, `_slugify`)
- [x] Updated imports in both files
- [x] **Adaptation**: `to_text()` keeps the current `is not None` behavior so values like `0` still serialize to `"0"`

### Task 3.2 — Extract token replacement logic ✅

- [x] Added `TOKEN_PATTERN`, `DOUBLE_BRACE_TOKEN_PATTERN`, `replace_tokens_in_paragraph()`, `replace_tokens_in_cell()`, and `replace_tokens_in_container()` to `api/services/_doc_helpers.py`
- [x] Removed local copies from:
  - `api/services/cor_doc_service.py` (token regexes, `_replace_tokens_in_paragraph`, `_replace_tokens_in_container`)
  - `api/services/shipping_doc_service.py` (token regexes, `_replace_tokens_in_paragraph`, `_replace_tokens_in_cell`, `_replace_tokens_in_container`)
- [x] Updated imports in both files
- [x] **Adaptation**: unified helper uses `preprocess_text` / `postprocess_text` callbacks and a `recurse_nested_tables` flag
- [x] COR now passes initiator-pair preprocessing, OR-phrase cleanup, and `recurse_nested_tables=False` to preserve its original behavior
- [x] Shipping now passes `postprocess_text=_normalize_token_whitespace` to preserve its whitespace cleanup behavior

### Task 3.3 — Extract temp-file handling ✅

- [x] Added `write_temp_file()` to `api/services/_doc_helpers.py`
- [x] Implemented it with `tempfile.mkstemp()` and `os.fdopen(..., "wb")` for explicit close-on-write
- [x] Replaced inline temp-file blocks in:
  - `api/services/processing_service.py`
  - `api/services/profile_service.py`

### Task 3.4 — Extract env-config helpers ✅

- [x] Created `api/services/_env_helpers.py`
- [x] Added `env_flag()`, `env_positive_int()`, and `env_csv()`
- [x] Removed local env helpers from `api/services/processing_service.py`
- [x] Removed the duplicate `_env_positive_int()` from `api/services/extraction_concurrency.py`
- [x] Updated imports in all affected files
- [x] **Adaptation**: `env_flag()` keeps support for `"on"`, `env_positive_int()` keeps the `min_value` parameter, and `env_csv()` accepts an optional default list so current fallback behavior stays unchanged

### Risks / Notes — Phase 3

- **Validated merge**: token replacement differences were preserved with callback hooks rather than flattened away.
- `_doc_helpers.py` and `_env_helpers.py` stay independent from router and DB layers.
- Validation: `python -m py_compile api/services/_doc_helpers.py api/services/_env_helpers.py api/services/cor_doc_service.py api/services/shipping_doc_service.py api/services/processing_service.py api/services/profile_service.py api/services/extraction_concurrency.py`

---

## Phase 4: Test Helpers & Fixtures ✅ COMPLETE (ADAPTED)

**Target**: `tests/helpers.py` (new file), `tests/conftest.py` (extend)
**Estimated lines saved**: ~150
**Status**: Implemented with one decision-based adaptation. Shared helpers were added and the targeted login/unique/stub/capture refactors were applied. The Gemini fixture task was completed as an audit decision rather than a merge.

### Task 4.1 — Extract shared `login()` helper ✅

- [x] Created `tests/helpers.py`
- [x] Added `login(client, username="admin", password="test-admin-password")`
- [x] Removed local `_login()` from:
  - `tests/test_api_processing_extract.py`
  - `tests/test_auth_protection.py`
  - `tests/test_auth_router.py`
  - `tests/test_cor_workflow.py`
  - `tests/test_shipping_prefill.py`
  - `tests/test_workspace_isolation.py`
- [x] Updated call sites to use the shared helper directly or the new `auth_client` fixture
- [x] **Adaptation**: default password was updated from the stale plan value (`admin123`) to the current test bootstrap password (`test-admin-password`)

### Task 4.2 — Extract `auth_client` fixture into `conftest.py` ✅ COMPLETE (ADAPTED)

- [x] Added a shared `auth_client` fixture to `tests/conftest.py`
- [x] **Adaptation**: the fixture creates its own `TestClient(app)` and authenticates via the existing session login flow
- [x] Did not use the original token-header approach because the tests do not have a shared `client` fixture and the current app behavior already supports session-based auth
- [x] Replaced the straightforward admin-login setup in:
  - `tests/test_api_processing_extract.py`
  - `tests/test_auth_protection.py`
  - `tests/test_cor_workflow.py`
  - `tests/test_shipping_prefill.py`
- [x] Multi-user and custom-credential tests intentionally still use explicit `TestClient(...)` instances where that makes the test setup clearer

### Task 4.3 — Extract unique-ID generators ✅

- [x] Added `unique_username()` to `tests/helpers.py`
- [x] Added `unique_name()` as a small adaptation for non-username identifiers (quote refs, project names)
- [x] Removed local generators from:
  - `tests/test_auth_router.py`
  - `tests/test_workspace_isolation.py`

### Task 4.4 — Extract shared monkeypatch lambdas ✅

- [x] Added `stub_get_client_by_id()` to `tests/helpers.py`
- [x] **Adaptation**: helper accepts `expected_id=` so the tests can preserve their existing `quote_id` matching behavior
- [x] Replaced the duplicated `get_client_by_id` monkeypatch lambdas in:
  - `tests/test_cor_workflow.py`
  - `tests/test_shipping_prefill.py`

### Task 4.5 — Extract `fake_save()` capture pattern ✅

- [x] Added `DocCapture` to `tests/helpers.py`
- [x] **Adaptation**: helper supports either `return_value` or `return_factory` so the saved-row payload can still be tailored per test
- [x] Replaced the `fake_save()` closures in:
  - `tests/test_cor_workflow.py`
  - `tests/test_shipping_prefill.py`

### Task 4.6 — Consolidate PDF skip guard ✅

- [x] Added `skip_unless_pdf()` to `tests/helpers.py`
- [x] Applied it to the shared `sample_pdf_cqc` / `sample_pdf_ume` fixtures in `tests/conftest.py`
- [x] Replaced the repeated inline `pytest.skip(...)` checks in `tests/test_pdf_utils.py` with `skip_unless_pdf(...)`

### Task 4.7 — Consolidate mock Gemini setup ✅ COMPLETE (DECISION)

- [x] Reviewed `tests/conftest.py` and `tests/test_llm/test_client.py`
- [x] No merge applied: `tests/test_llm/test_client.py` defines a mocked `genai` compatibility namespace, while `tests/conftest.py` provides a different mock Gemini client shape
- [x] Decision: leave them separate unless the two tests are deliberately redesigned to target the same abstraction

### Risks / Notes — Phase 4

- Test helpers must not import application code at module level to avoid import-order issues; use lazy imports inside functions where needed.
- `login()` signatures vary slightly across files. Inspect each to confirm the normalised signature works.
- `auth_client` now uses lazy imports and session-based auth to match the current app behavior.
- Validation: `python -m py_compile tests/helpers.py tests/conftest.py tests/test_api_processing_extract.py tests/test_auth_protection.py tests/test_auth_router.py tests/test_cor_workflow.py tests/test_shipping_prefill.py tests/test_workspace_isolation.py tests/test_pdf_utils.py`
- Full `pytest` still remains the right next validation step after dependencies are available.

---

## Phase 5: Frontend Shared Utilities ✅ COMPLETE (ADAPTED)

**Target**: `frontend/src/lib/doc-utils.ts` (new file), `frontend/src/hooks/use-fetch.ts` (new file), `frontend/src/components/shared/` (new directory)
**Estimated lines saved**: ~200
**Status**: Implemented with two scoped adaptations. Shared frontend document utilities, the fetch hook, the set-toggle helper, and a shared file-upload picker are in place. Complex fetch flows intentionally keep local effects where the hook would add coupling or obscure behavior.

### Task 5.1 — Extract `line()`, `toNumber()` ✅

- [x] Created `frontend/src/lib/doc-utils.ts`
- [x] Added shared `line()` and `toNumber()` helpers
- [x] Removed local `line()` from:
  - `frontend/src/components/shipping/certificate-origin-preview.tsx`
  - `frontend/src/components/shipping/packing-slip-preview.tsx`
  - `frontend/src/components/shipping/commercial-invoice-preview.tsx`
- [x] Removed local `toNumber()` from:
  - `frontend/src/components/shipping/packing-slip-preview.tsx`
  - `frontend/src/components/shipping/commercial-invoice-preview.tsx`
- [x] Added `import { line, toNumber } from "@/lib/doc-utils"` to the affected files
- [x] **Adaptation**: helper signatures were widened slightly (`string | null | undefined` / `string | number | null | undefined`) to fit the existing call sites safely

### Task 5.2 — Extract `uid()` ✅

- [x] Added `uid(prefix: string)` to `frontend/src/lib/doc-utils.ts`
- [x] Preserved the current browser-safe implementation, including `crypto.randomUUID()` when available
- [x] Removed the local helper from:
  - `frontend/src/components/pages/shipping-documents-page-client.tsx`
  - `frontend/src/components/pages/cor-documents-page-client.tsx`
- [x] Updated imports

### Task 5.3 — Extract `formatStatusTimestamp()` and `workflowQuoteBadgeConfig()` ✅

- [x] Added `formatStatusTimestamp()` and `workflowQuoteBadgeConfig()` to `frontend/src/lib/doc-utils.ts`
- [x] Removed the local copies from:
  - `frontend/src/components/pages/client-info-page-client.tsx`
  - `frontend/src/components/pages/quote-client-info-page-client.tsx`
- [x] Updated imports
- [x] **Adaptation**: the shared helper keeps the current `{ label, className }` return shape rather than the stale plan’s `variant` field

### Task 5.4 — Extract `useFetch()` custom hook ✅ COMPLETE (LOW-RISK PASS)

- [x] Created `frontend/src/hooks/use-fetch.ts`
- [x] Added a shared `useFetch<T>()` hook with `data`, `loading`, `error`, and `reload()`
- [x] Refactored the initial data load in:
  - `frontend/src/components/pages/reports-page-client.tsx`
- [x] Refactored the initial data load in:
  - `frontend/src/components/pages/dashboard-page-client.tsx`
- [x] Refactored the single-fetch detail load in:
  - `frontend/src/components/pages/quote-edit-page-client.tsx`
- [x] Refactored the quote-detail portion of the chained preview load in:
  - `frontend/src/components/pages/quote-preview-page-client.tsx`
- [x] Refactored the sidebar client list load in:
  - `frontend/src/components/layout/sidebar.tsx`
- [x] **Adaptation**: rollout is intentionally incremental; selection-specific report fetching in `reports-page-client.tsx` still uses its local effect
- [x] **Adaptation**: `quote-preview-page-client.tsx` keeps the report fetch local and preserves its combined loading state across quote + report loading
- [x] Decision: the remaining fetch-heavy components keep local effects because they combine loading, redirects, staged workflows, or manual state seeding in ways that a shared hook would not simplify safely

### Task 5.5 — Unify upload dialog components ✅ COMPLETE (RE-SCOPED)

- [x] Audited:
  - `frontend/src/components/dashboard/upload-dialog.tsx`
  - `frontend/src/components/pm-dashboard/gantt-upload-dialog.tsx`
- [x] No full dialog merge applied: the dashboard upload dialog is a multi-step quote-ingestion workflow, while the gantt dialog is a small single-file PDF uploader
- [x] Re-scoped the task to extract a narrower shared primitive instead
- [x] Created `frontend/src/components/shared/file-upload-picker.tsx`
- [x] Replaced the duplicated file-picker shell in:
  - `frontend/src/components/dashboard/upload-dialog.tsx`
  - `frontend/src/components/pm-dashboard/gantt-upload-dialog.tsx`

### Task 5.6 — Extract set-toggle utility ✅

- [x] Added `toggleSetItem()` to `frontend/src/lib/utils.ts`
- [x] Replaced inline toggle logic in:
  - `frontend/src/components/processing/machine-selector.tsx`
  - `frontend/src/components/processing/options-selector.tsx`

### Risks / Notes — Phase 5

- Frontend changes are harder to test automatically. Verify each component visually after refactoring.
- `useFetch()` must handle dependency arrays correctly to avoid infinite re-render loops. Lint with `eslint-plugin-react-hooks`.
- The full upload-dialog merge was intentionally avoided; only the shared file-picker shell was extracted.
- Validation: `npm exec -- tsc --noEmit -p tsconfig.json` (run in `frontend/`)

---

## Execution Order & Dependencies

```
Phase 1 (API Routers)       -- no dependencies, start here
Phase 2 (DB Layer)           -- no dependencies, can run in parallel with Phase 1
Phase 3 (Services)           -- no dependencies, can run in parallel
Phase 4 (Tests)              -- run after Phases 1-3 (tests import app code)
Phase 5 (Frontend)           -- independent, can run any time
```

## Summary

| Phase | Area | New Files | Files Modified | Est. Lines Saved |
|-------|------|-----------|----------------|------------------|
| 1 | API Routers | 1 | 7 | ~250 |
| 2 | DB Layer | 0-1 | 10+ | ~180 |
| 3 | Services | 2 | 4 | ~200 |
| 4 | Tests | 1 | 8+ | ~150 |
| 5 | Frontend | 2 | 12+ | ~200 |
| **Total** | | **6-7** | **~41** | **~980** |

## Verification Checklist (per phase)

- [ ] All existing tests pass (`pytest` / `npm test`)
- [ ] No circular imports introduced
- [ ] No unused imports left behind
- [ ] New helper modules have zero side effects at import time
- [ ] Git diff reviewed before committing
