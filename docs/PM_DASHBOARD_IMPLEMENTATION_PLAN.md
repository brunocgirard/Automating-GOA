# PM Dashboard & GOA Processing — Implementation Plan

> Detailed task list for implementing the minimalist PM Dashboard and restructuring the GOA Processing tab in the GOA_LLM application (Next.js 16 + FastAPI + SQLite).

---

## Two Deliverables

1. **PM Dashboard** — Minimalist Kanban + slide-over with AI insights
2. **GOA Processing tab** — Rename "Processing" to "GOA Processing", add quote list with edit option

---

# Part A: PM Dashboard (Minimalist)

## Architecture Overview

```
                     PM Dashboard
               ┌──────────────────────┐
               │  Alert Strip (1)     │  ← only shows if projects at risk
               ├──────────────────────┤
               │  Kanban Board (5col) │ ─► Click card ─► Slide-over panel
               │  [lean cards]        │                  ├ AI Insights (top)
               └──────────────────────┘                  ├ 2 key stats
                                                         ├ Quick links
                                                         ├ Phase progress (5 blocks)
                                                         ├ Task checklist (collapsed)
                                                         └ Gantt detail (collapsed)
```

**Design principles (from team analysis):**
- Only ~10 elements visible at first glance, not ~20
- Every element must answer: "What's on fire?", "What needs my action?", or "Is everything OK?"
- AI insights at top of detail panel (highest value, not buried at bottom)
- Days-in-phase is the killer metric (not progress bars)
- Phase-level progress (5 blocks) replaces 26-dot milestone bar
- Task checklist and Gantt collapsed by default

**Non-linear workflow model:**
- Tasks are an **independent checklist**, not a sequential pipeline
- Any task can be completed at any time in any order (e.g., GOA created before Intro Letter)
- Phase grouping is for **display organization only**, not enforced gates
- `task_order` is a suggested/typical order, not a dependency chain
- Kanban column = earliest phase that still has incomplete tasks

**Connecting to existing app:**
- Projects link to quotes via `quote_ref` (FK to `clients` table)
- Quick links in panel navigate to existing pages (Client Info, GOA Processing, Shipping, COR)
- Reuses `Sheet` component for slide-over panel
- Follows the same page/router/db module conventions throughout

---

## Phase A1: Data Model & Backend

### Task A1.1 — Create DB tables

**File:** `src/utils/db/base.py`
**Action:** Add to `init_db()`, after `cor_documents` table.

```sql
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    quote_ref TEXT,
    machine_summary TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    risk_level TEXT NOT NULL DEFAULT 'on_track',
    start_date TEXT,
    target_end_date TEXT,
    actual_end_date TEXT,
    gantt_data_json TEXT,
    created_date TEXT NOT NULL,
    modified_date TEXT NOT NULL,
    FOREIGN KEY (quote_ref) REFERENCES clients (quote_ref) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS project_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    task_name TEXT NOT NULL,
    task_order INTEGER NOT NULL,
    phase TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    planned_date TEXT,
    actual_date TEXT,
    notes TEXT,
    modified_date TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_task_id INTEGER NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    transitioned_at TEXT NOT NULL,
    FOREIGN KEY (project_task_id) REFERENCES project_tasks (id) ON DELETE CASCADE
);
```

**Notes:**
- `gantt_data_json` stores parsed Gantt PDF as JSON blob (same pattern as `shipping_data_json`)
- `project_tasks.status`: `pending`, `in_progress`, `done`, `skipped`
- `project_tasks.phase`: `sales_onboarding`, `engineering_prep`, `design_approval`, `production`, `delivery`
- `projects.risk_level`: `on_track`, `at_risk`, `overdue`
- **No dependency enforcement** — `task_order` is display order, not a constraint

**Default 26 tasks seeded per project:**

| Order | Task Name | Phase |
|-------|-----------|-------|
| 1 | Down Payment Received | sales_onboarding |
| 2 | Introduction Letter | sales_onboarding |
| 3 | Binder | sales_onboarding |
| 4 | Transfer File - From Sales Dept | sales_onboarding |
| 5 | Engineering Samples Received | engineering_prep |
| 6 | Product Matrix Sent to Client | engineering_prep |
| 7 | Product Matrix Confirmed by Client | engineering_prep |
| 8 | Layout Issued for Approval | design_approval |
| 9 | Layout Approved (Signed) | design_approval |
| 10 | Layout Approval Confirmation Paid | design_approval |
| 11 | GOA(s) | design_approval |
| 12 | Pre-Kick Off | design_approval |
| 13 | Timeline Published - Gantt to Customer | production |
| 14 | Bulk Samples Requested | production |
| 15 | Bulk Samples Received | production |
| 16 | Samples Sent for Feeders | production |
| 17 | Engineering Kick Off | production |
| 18 | Project Released from Design | production |
| 19 | Third Party Equipment Ordered | production |
| 20 | Third Party Equipment Received | production |
| 21 | Revised FAT Published | delivery |
| 22 | Actual FAT | delivery |
| 23 | COR Completion | delivery |
| 24 | Crating | delivery |
| 25 | Pre-Ship Payments | delivery |
| 26 | Shipment | delivery |

---

### Task A1.2 — Create DB module `src/utils/db/projects.py`

Follow the pattern of `src/utils/db/shipping.py` and `src/utils/db/cor.py`.

```python
# ── Projects CRUD ──
def create_project(data: dict) -> dict
    # INSERT project + INSERT 26 default project_tasks
    # Returns created project with tasks

def load_all_projects() -> list[dict]
    # SELECT all projects with: current_phase, current_task, days_in_phase, progress_pct
    # current_phase = earliest phase with incomplete tasks
    # days_in_phase = days since first task in current_phase became in_progress

def load_project(project_id: int) -> dict | None
    # SELECT project + all tasks + parsed gantt_data_json

def update_project(project_id: int, data: dict) -> dict | None

def delete_project(project_id: int) -> bool

# ── Task operations (non-linear — no dependency checks) ──
def update_task_status(task_id: int, new_status: str, notes: str | None = None) -> dict
    # UPDATE task status + actual_date (if done) + modified_date
    # INSERT into task_transitions
    # Recalculate project risk_level

# ── Gantt PDF data ──
def save_gantt_data(project_id: int, gantt_data: dict) -> dict

# ── Metrics & Insights ──
def get_at_risk_summary() -> dict
    # Returns: { count, projects: [{ name, task, phase, days_stalled }] }
    # Only metric shown on dashboard surface

def detect_stalls(threshold_days: int = 7) -> list[dict]
    # Only flags tasks marked 'in_progress' for > threshold days
    # Does NOT flag out-of-order completion as a problem
```

---

### Task A1.3 — Update `src/utils/db/__init__.py`

Add exports for the new module.

---

### Task A1.4 — Add Pydantic models in `api/models/schemas.py`

```python
class ProjectTaskResponse(BaseModel):
    id: int
    task_name: str
    task_order: int
    phase: str
    status: str
    planned_date: str | None = None
    actual_date: str | None = None
    notes: str | None = None

class ProjectListResponse(BaseModel):
    id: int
    project_name: str
    customer_name: str
    quote_ref: str | None = None
    machine_summary: str | None = None
    status: str
    risk_level: str
    current_phase: str | None = None
    current_task: str | None = None
    days_in_phase: int | None = None
    progress_pct: int = 0

class ProjectDetailResponse(BaseModel):
    # Same as above + tasks list + gantt_data
    tasks: list[ProjectTaskResponse] = []
    gantt_data: dict | None = None
    start_date: str | None = None
    target_end_date: str | None = None

class ProjectCreateRequest(BaseModel):
    project_name: str
    customer_name: str
    quote_ref: str | None = None
    machine_summary: str | None = None
    start_date: str | None = None
    target_end_date: str | None = None

class TaskStatusUpdateRequest(BaseModel):
    status: str
    notes: str | None = None

class AtRiskSummaryResponse(BaseModel):
    count: int
    projects: list[dict] = []

class StallAlertResponse(BaseModel):
    project_id: int
    project_name: str
    task_id: int
    task_name: str
    phase: str
    days_stalled: int
```

---

### Task A1.5 — Create API router `api/routers/pm_dashboard.py`

```python
router = APIRouter(prefix="/api/pm", tags=["PM Dashboard"])

GET  /api/pm/at-risk              → get_at_risk_summary()
GET  /api/pm/stalls               → detect_stalls()
GET  /api/pm/projects             → load_all_projects()
POST /api/pm/projects             → create_project(payload)
GET  /api/pm/projects/{id}        → load_project(id)         # with tasks + gantt
PUT  /api/pm/projects/{id}        → update_project(id, payload)
DELETE /api/pm/projects/{id}      → delete_project(id)
PUT  /api/pm/tasks/{id}/status    → update_task_status(id, payload)
POST /api/pm/projects/{id}/gantt-upload  → parse PDF + save_gantt_data()
```

---

### Task A1.6 — Register router in `api/main.py`

```python
from api.routers.pm_dashboard import router as pm_dashboard_router
app.include_router(pm_dashboard_router)
```

---

## Phase A2: Frontend — Dashboard Surface

### Task A2.1 — Add TypeScript types in `frontend/src/lib/types.ts`

```typescript
export type ProjectPhase = "sales_onboarding" | "engineering_prep" | "design_approval" | "production" | "delivery";
export type TaskStatus = "pending" | "in_progress" | "done" | "skipped";
export type RiskLevel = "on_track" | "at_risk" | "overdue";

export interface ProjectTask {
  id: number;
  task_name: string;
  task_order: number;
  phase: ProjectPhase;
  status: TaskStatus;
  planned_date: string | null;
  actual_date: string | null;
  notes: string | null;
}

export interface ProjectListItem {
  id: number;
  project_name: string;
  customer_name: string;
  quote_ref: string | null;
  machine_summary: string | null;
  status: string;
  risk_level: RiskLevel;
  current_phase: ProjectPhase | null;
  current_task: string | null;
  days_in_phase: number | null;
  progress_pct: number;
}

export interface ProjectDetail extends ProjectListItem {
  tasks: ProjectTask[];
  gantt_data: Record<string, unknown> | null;
  start_date: string | null;
  target_end_date: string | null;
}

export interface AtRiskSummary {
  count: number;
  projects: Array<{ name: string; task: string; phase: string; days_stalled: number }>;
}

export interface StallAlert {
  project_id: number;
  project_name: string;
  task_id: number;
  task_name: string;
  phase: string;
  days_stalled: number;
}
```

---

### Task A2.2 — Add API functions in `frontend/src/lib/api.ts`

```typescript
// ── PM Dashboard ──
export async function fetchAtRiskSummary(): Promise<AtRiskSummary>
export async function fetchStallAlerts(): Promise<StallAlert[]>
export async function fetchProjects(): Promise<ProjectListItem[]>
export async function fetchProject(id: number): Promise<ProjectDetail | null>
export async function createProject(data: ProjectCreateRequest): Promise<ProjectDetail>
export async function updateTaskStatus(taskId: number, status: string, notes?: string): Promise<void>
export async function uploadGanttPdf(projectId: number, file: File): Promise<void>
```

---

### Task A2.3 — Update sidebar navigation

**File:** `frontend/src/components/layout/sidebar.tsx`

**Changes:**
1. Rename "Processing" to **"GOA Processing"**
2. Add **"PM Dashboard"** entry

```typescript
const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/client-info", label: "Client Info", icon: UserRound },
  { href: "/processing", label: "GOA Processing", icon: Cog },        // ← RENAMED
  { href: "/shipping-documents", label: "Shipping Docs", icon: Files },
  { href: "/cor-documents", label: "COR Docs", icon: Files },
  { href: "/pm-dashboard", label: "PM Dashboard", icon: Kanban },      // ← NEW
  { href: "/reports", label: "Reports", icon: FileText },
];
```

---

### Task A2.4 — Create page route `frontend/src/app/pm-dashboard/page.tsx`

```typescript
import PmDashboardPage from "@/components/pages/pm-dashboard-page-client";
export default function Page() { return <PmDashboardPage />; }
```

---

### Task A2.5 — Create `frontend/src/components/pages/pm-dashboard-page-client.tsx`

Main page orchestrator. Fetches `fetchProjects()` and `fetchAtRiskSummary()` on mount.

**Renders:**
1. `<AlertStrip>` — single strip showing at-risk count + top project detail. Hidden when count = 0 (shows a green "All on track" strip instead).
2. `<KanbanBoard>` — 5 lean columns with project cards.
3. `<ProjectDetailSheet>` — slide-over opened on card click.

---

### Task A2.6 — Create `frontend/src/components/pm-dashboard/alert-strip.tsx`

**Single component replacing 4 KPI cards.**

- If `atRisk.count > 0`: Red background, shows count + worst offender name + stall reason
- If `atRisk.count === 0`: Green background, shows "All projects on track"

Reuses: `Card` from `ui/card.tsx`, Tailwind conditional classes.

---

### Task A2.7 — Create `frontend/src/components/pm-dashboard/kanban-board.tsx`

**5 columns, lean cards.**

Columns: Sales & Onboarding | Engineering Prep | Design & Approval | Production | Delivery

**Column assignment (non-linear):**
```
Place project in earliest phase that still has incomplete tasks.
If all tasks done → Delivery column.
```

No phase subtask labels (the PM already knows what's in each phase).

---

### Task A2.8 — Create `frontend/src/components/pm-dashboard/project-card.tsx`

**Lean card — only 4 elements:**
- Project name (bold) + risk dot (green/yellow/red)
- Customer name (muted)
- Current task badge (accent colored)
- Days in phase (muted mono; yellow if > avg; red if > 2x avg)

**No progress bar. No ref code. No machine count.**

Reuses: `Card`, `Badge` from `ui/`.

---

## Phase A3: Frontend — Detail Panel

### Task A3.1 — Create `frontend/src/components/pm-dashboard/project-detail-sheet.tsx`

Uses `Sheet` from `ui/sheet.tsx`. Width: `sm:max-w-2xl`.

**Content order (top to bottom):**

1. **Header** — Project name, customer, status tag
2. **AI Insights** (always visible, top of panel) — max 2 cards
3. **Key stats** — Only 2: "Days Elapsed (X / Y)" and "Est. Completion"
4. **Quick links** — Client Info, GOA Processing, Shipping, COR
5. **Phase progress** — 5 colored blocks (complete/active/pending) with done/total counts. Hover for detail tooltip.
6. **Task checklist** (collapsed by default) — 26 rows grouped by phase, any task clickable in any order, out-of-order badge shown when applicable
7. **Production Gantt** (collapsed by default) — machine progress bars from uploaded PDF

---

### Task A3.2 — Create `frontend/src/components/pm-dashboard/insights-panel.tsx`

Fetches `fetchStallAlerts()`. Renders max **2 insight cards** (highest severity first).

Types: critical (red), warning (yellow), info (blue).

Rule-based logic (no ML):
- Stall alerts from backend `detect_stalls()` endpoint
- Critical path: task's planned_date within 3 days and still pending
- Resource contention: 3+ projects in same phase simultaneously

---

### Task A3.3 — Create `frontend/src/components/pm-dashboard/phase-progress.tsx`

**5 phase blocks** (replaces 26-dot milestone bar):
- Green = all tasks in phase done
- Blue + pulse = has active tasks (some done, some not)
- Gray = no tasks started
- Shows `done/total` count inside each block
- Hover tooltip: phase name + breakdown

---

### Task A3.4 — Create `frontend/src/components/pm-dashboard/task-checklist.tsx`

Collapsible section, **collapsed by default**.

- 26 tasks grouped by phase headers
- **Any task clickable at any time** — no dependency gates
- Click: `pending → done` (single click, sets actual_date to today)
- Right-click or long-press: set `in_progress` or `skipped`
- Out-of-order badge: shown when a task is done but an earlier task in same phase isn't
- Calls `updateTaskStatus()` API on each change

Reuses: `Checkbox` from `ui/checkbox.tsx`.

---

### Task A3.5 — Create `frontend/src/components/pm-dashboard/gantt-detail.tsx`

Collapsible, collapsed by default. Shows per-machine progress bars from `gantt_data_json`.

If no Gantt uploaded: shows "No Gantt uploaded" with upload button.

---

## Phase A4: Gantt PDF Upload

### Task A4.1 — Create `src/utils/gantt_parser.py`

Uses `pdfplumber` (already in dependencies). Parses Gantt PDF table into structured JSON:
```python
def parse_gantt_pdf(pdf_path: str) -> dict:
    # Returns: { machines: [{ name, project_code, overall_pct, start_date, end_date, phases: [...] }], fat: {...} }
```

### Task A4.2 — Create `frontend/src/components/pm-dashboard/gantt-upload-dialog.tsx`

Reuses pattern from `upload-dialog.tsx`: Dialog + file input + upload state.

---

## Phase A5: AI Insights Backend

### Task A5.1 — Create `api/services/insights_service.py`

```python
def get_stall_alerts(threshold_days: int = 7) -> list[dict]
    # Only flags 'in_progress' tasks idle > threshold. Non-linear safe.

def get_critical_path_alerts() -> list[dict]
    # Tasks with planned_date approaching and still pending.

def get_all_insights(project_id: int | None = None) -> list[dict]
    # Aggregates, sorts by severity, caps at 2 per project.
```

### Task A5.2 — Add insights endpoint

```
GET /api/pm/insights
GET /api/pm/projects/{id}/insights
```

---

## Phase A6: Integration

### Task A6.1 — Quick links from panel

When `quote_ref` is set on a project, quick links navigate to:
- `/client-info?quote={quote_ref}`
- `/processing?quote={quote_ref}` (the new GOA Processing tab)
- `/shipping-documents?quote={quote_ref}`
- `/cor-documents?quote={quote_ref}`

### Task A6.2 — Auto-create project from quote upload (optional)

In `api/routers/quotes.py` → `POST /api/quotes/upload`, after successful upload:
```python
create_project({
    "project_name": f"{customer_name} - {machine_model}",
    "customer_name": customer_name,
    "quote_ref": quote_ref,
    "start_date": _timestamp()[:10],
})
```

### Task A6.3 — Auto-advance PM tasks from existing workflows (optional)

- GOA generated → mark "GOA(s)" task as done
- COR saved → mark "COR Completion" as done
- Shipping generated → mark "Crating" as done

---

# Part B: GOA Processing Tab Restructure

## Overview

**Current state:**
- Sidebar shows "Processing" → navigates to `/processing`
- Processing page: 3-step wizard (Load Quote → Select Machine → Process Machine)
- GOA editing lives at separate route `/goa/[machineTemplateId]`
- No quote list on the processing page

**Target state:**
- Sidebar shows **"GOA Processing"** → navigates to `/processing`
- Processing page has **2 sections**:
  1. **Quote list** (top) — table of all quotes with status, customer, machine, and action buttons including "Edit GOA"
  2. **Processing workflow** (bottom or tab) — the existing 3-step wizard

The GOA form (`/goa/[machineTemplateId]`) route remains as-is but is now reachable directly from the quote list via an "Edit GOA" button.

---

## Phase B1: Restructure Processing Page

### Task B1.1 — Update sidebar label

**File:** `frontend/src/components/layout/sidebar.tsx`

Change the label in `navItems`:
```typescript
{ href: "/processing", label: "GOA Processing", icon: Cog },
```

---

### Task B1.2 — Redesign `frontend/src/components/pages/processing-page-client.tsx`

**Current:** Single-purpose 3-step wizard.

**New layout:** Two-section page with tabs or vertical split.

```
┌─────────────────────────────────────────────────────┐
│  GOA Processing                                     │
├──────────┬──────────────────────────────────────────┤
│ Quotes   │  Process New  │                          │
│ (active) │  (tab)        │                          │
├──────────┴──────────────────────────────────────────┤
│                                                     │
│  [Tab: Quotes]                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ Quote Ref │ Customer │ Machine │ Status │ Actions│
│  │ Q-001     │ Xeolas   │ CF-2P   │ Ready  │ Edit  │ │
│  │ Q-002     │ Pharma   │ Jolly   │ Draft  │ Process│
│  │ ...       │          │         │        │       │ │
│  └────────────────────────────────────────────────┘ │
│                                                     │
│  [Tab: Process New]                                 │
│  (existing 3-step wizard, unchanged)                │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Implementation:**

1. Add `Tabs` component (from `ui/tabs.tsx`) wrapping two tab panels
2. **Tab "Quotes"** (default active): New `<QuoteGoaList />` component showing all quotes with GOA status
3. **Tab "Process New"**: The existing processing wizard (move current content here, unchanged)

---

### Task B1.3 — Create `frontend/src/components/processing/quote-goa-list.tsx`

**New component** — a table of all quotes with GOA-related actions.

**Columns:**
| Column | Source |
|--------|--------|
| Quote Ref | `quote.quote_ref` |
| Customer | `quote.customer_name` |
| Machine | `quote.machine_model` (or machine name from machines list) |
| Status | Badge: draft / processed / ready |
| Actions | Buttons: "Edit GOA" / "Process" / "View Client" |

**Data source:** Reuses existing `fetchQuotes()` from `api.ts` — the same data the current Dashboard page uses.

**For each quote, fetch its machines** to show the GOA edit links:
- Call existing `fetchQuoteDetail(quoteId)` which returns machines with `machineTemplateId`
- If machines have templates: show "Edit GOA" button → navigates to `/goa/{machineTemplateId}`
- If no templates yet: show "Process" button → switches to "Process New" tab with quote pre-selected

**Action buttons:**
- **Edit GOA** → `router.push(/goa/${machineTemplateId})`
- **Process** → Switch to "Process New" tab + set `selectedQuote` via shared state or URL param
- **View Client** → `router.push(/client-info?quote=${quoteRef})`

**Reuses:**
- `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableCell` from `ui/table.tsx`
- `Badge` from `ui/badge.tsx` (same `statusConfig` pattern from `quote-table.tsx`)
- `Button` from `ui/button.tsx`
- `fetchQuotes()` and `getQuoteDetail()` from `api.ts`

---

### Task B1.4 — Wire up tab communication

When user clicks "Process" on a quote in the Quotes tab:
1. Set the quote ref in shared state (via `useState` in parent)
2. Switch to "Process New" tab
3. The existing wizard auto-selects that quote (use existing `quoteFromQuery` logic)

This reuses the existing URL parameter support: the wizard already handles `?quote=REF&machine=INDEX`.

---

### Task B1.5 — Handle multi-machine quotes

Some quotes have multiple machines (e.g., Xeolas has CF-2P, Mini-Jolly, Automation System, Turn Table).

In the quote list, show an **expandable row** for multi-machine quotes:

```
Q-001 │ Xeolas │ 4 machines │ Processed │ [Expand]
  └─ CF-2P (A3490)        │ Ready  │ [Edit GOA]
  └─ Mini-Jolly (A3492)   │ Ready  │ [Edit GOA]
  └─ Automation Sys (A3491)│ Draft  │ [Process]
  └─ Turn Table (A3493)   │ Draft  │ [Process]
```

For single-machine quotes, show the machine name directly (no expand needed).

---

## Phase B2: Keep GOA Form Route

### Task B2.1 — No changes to `/goa/[machineTemplateId]`

The GOA form page stays exactly as-is. It's already a standalone page that accepts a `machineTemplateId` and renders the form editor. The only change is that it's now reachable from the new Quotes tab via "Edit GOA" buttons, in addition to the existing navigation paths.

---

# File Summary

## New files to create:

| File | Purpose |
|------|---------|
| `src/utils/db/projects.py` | DB CRUD for projects, tasks, transitions |
| `src/utils/gantt_parser.py` | PDF → structured Gantt data |
| `api/routers/pm_dashboard.py` | PM dashboard API endpoints |
| `api/services/insights_service.py` | Rule-based AI insights |
| `frontend/src/app/pm-dashboard/page.tsx` | Next.js route |
| `frontend/src/components/pages/pm-dashboard-page-client.tsx` | Dashboard page |
| `frontend/src/components/pm-dashboard/alert-strip.tsx` | Single alert strip (replaces 4 KPIs) |
| `frontend/src/components/pm-dashboard/kanban-board.tsx` | 5-column Kanban |
| `frontend/src/components/pm-dashboard/project-card.tsx` | Lean project card |
| `frontend/src/components/pm-dashboard/project-detail-sheet.tsx` | Slide-over panel |
| `frontend/src/components/pm-dashboard/phase-progress.tsx` | 5 phase blocks |
| `frontend/src/components/pm-dashboard/insights-panel.tsx` | AI insights (max 2) |
| `frontend/src/components/pm-dashboard/task-checklist.tsx` | Non-linear task list |
| `frontend/src/components/pm-dashboard/gantt-detail.tsx` | Collapsible Gantt |
| `frontend/src/components/pm-dashboard/gantt-upload-dialog.tsx` | Gantt PDF upload |
| `frontend/src/components/processing/quote-goa-list.tsx` | Quote table with Edit GOA |

## Existing files to modify:

| File | Change |
|------|--------|
| `src/utils/db/base.py` | Add 3 new tables to `init_db()` |
| `src/utils/db/__init__.py` | Export new functions |
| `api/models/schemas.py` | Add PM dashboard Pydantic models |
| `api/main.py` | Register `pm_dashboard_router` |
| `frontend/src/lib/types.ts` | Add PM dashboard TypeScript types |
| `frontend/src/lib/api.ts` | Add PM dashboard API functions |
| `frontend/src/components/layout/sidebar.tsx` | Rename "Processing" → "GOA Processing", add PM Dashboard nav |
| `frontend/src/components/pages/processing-page-client.tsx` | Add Tabs: "Quotes" + "Process New" |
| `api/routers/quotes.py` | (Optional) Auto-create project on upload |
| `api/routers/processing.py` | (Optional) Auto-advance GOA task |
| `api/routers/cor.py` | (Optional) Auto-advance COR task |
| `api/routers/shipping.py` | (Optional) Auto-advance Shipping task |

---

# Implementation Order

| # | Task | Depends On |
|---|------|-----------|
| 1 | A1.1 — DB tables | — |
| 2 | A1.2 — DB module | 1 |
| 3 | A1.3 — DB exports | 2 |
| 4 | A1.4 — Pydantic models | — |
| 5 | A1.5 — API router | 2, 4 |
| 6 | A1.6 — Register router | 5 |
| 7 | A2.1 — TS types | — |
| 8 | A2.2 — API functions | 7 |
| 9 | **B1.1 — Rename sidebar to "GOA Processing"** | — |
| 10 | **B1.2 — Restructure processing page with Tabs** | — |
| 11 | **B1.3 — Create quote-goa-list component** | 10 |
| 12 | **B1.4 — Tab communication** | 10, 11 |
| 13 | **B1.5 — Multi-machine expandable rows** | 11 |
| 14 | A2.3 — Add PM Dashboard to sidebar | 9 |
| 15 | A2.4 — PM Dashboard page route | — |
| 16 | A2.5 — PM Dashboard page component | 8, 17, 18, 19 |
| 17 | A2.6 — Alert strip | 7 |
| 18 | A2.7 — Kanban board | 19 |
| 19 | A2.8 — Project card | 7 |
| 20 | A3.1 — Detail sheet | 21, 22, 23, 24 |
| 21 | A3.2 — Insights panel | 8 |
| 22 | A3.3 — Phase progress | 7 |
| 23 | A3.4 — Task checklist | 8 |
| 24 | A3.5 — Gantt detail | 7 |
| 25 | A4.1 — Gantt parser | — |
| 26 | A4.2 — Upload dialog | 25, 8 |
| 27 | A5.1 — Insights service | 2 |
| 28 | A5.2 — Insights endpoints | 27, 5 |
| 29 | A6.1 — Quick links | 16 |
| 30 | A6.2 — Auto-create project (optional) | 2 |
| 31 | A6.3 — Auto-advance tasks (optional) | 2 |

**Suggested parallel tracks:**
- **Track 1 (Backend):** Tasks 1-6, 25, 27-28
- **Track 2 (GOA Processing tab):** Tasks 9-13 (can start immediately, no backend dependency)
- **Track 3 (PM Dashboard frontend):** Tasks 7-8, 14-24, 26, 29 (starts after backend basics)
- **Track 4 (Integration):** Tasks 30-31 (after both tracks complete)
