# PM Dashboard Modification Plan

## Context
The PM dashboard currently has a Kanban board (5 project-phase columns) with a Gantt chart viewer inside the project detail sheet. The user needs:
1. **Remove/set aside** the Gantt chart (low priority, not needed now)
2. **Add a personal task board** above the Kanban — an Outlook-style task list where users can create tasks tagged by client (emails to send, follow-ups, etc.)
3. **Show completion date** on the existing Kanban task checklist when a task is checked off

---

## Changes Overview

### 1. New `user_tasks` DB Table + Migration
**File: `src/utils/db/base.py`**

Add a new `user_tasks` table:
```sql
CREATE TABLE IF NOT EXISTS user_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    client_tag TEXT,              -- customer_name from clients table (free text, not FK)
    priority TEXT NOT NULL DEFAULT 'normal',  -- low, normal, high, urgent
    status TEXT NOT NULL DEFAULT 'pending',   -- pending, done
    due_date TEXT,
    completed_at TEXT,            -- timestamp when marked done
    created_at TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users (id) ON DELETE CASCADE
)
```
Index: `idx_user_tasks_owner_status ON user_tasks (owner_user_id, status)`

### 2. New DB Functions
**New file: `src/utils/db/user_tasks.py`**

Functions:
- `create_user_task(owner_user_id, title, description, client_tag, priority, due_date)` → dict
- `list_user_tasks(owner_user_id, status_filter=None, client_tag_filter=None)` → list[dict]
- `update_user_task(task_id, owner_user_id, **fields)` → dict
- `toggle_user_task(task_id, owner_user_id)` → dict (pending↔done, sets `completed_at`)
- `delete_user_task(task_id, owner_user_id)` → bool
- `list_client_tags(owner_user_id)` → list[str] (distinct client_tag values for autocomplete)

### 3. New API Router
**New file: `api/routers/user_tasks.py`** — mounted at `/api/user-tasks`

Endpoints:
- `GET /api/user-tasks` — list tasks (query params: `status`, `client_tag`)
- `POST /api/user-tasks` — create task
- `PUT /api/user-tasks/{task_id}` — update task
- `PUT /api/user-tasks/{task_id}/toggle` — toggle done/pending
- `DELETE /api/user-tasks/{task_id}` — delete task
- `GET /api/user-tasks/tags` — list distinct client tags for autocomplete

All endpoints scoped to authenticated user via `require_authenticated_user`.

### 4. Pydantic Schemas
**File: `api/models/schemas.py`** (add to existing)

- `UserTaskCreateRequest(title, description?, client_tag?, priority?, due_date?)`
- `UserTaskUpdateRequest(title?, description?, client_tag?, priority?, status?, due_date?)`
- `UserTaskResponse(id, title, description, client_tag, priority, status, due_date, completed_at, created_at, modified_at)`

### 5. Register Router
**File: `api/main.py`** — add `user_tasks` router

### 6. Frontend Types
**File: `frontend/src/lib/types.ts`** — add:

```ts
export type UserTaskPriority = "low" | "normal" | "high" | "urgent";
export type UserTaskStatus = "pending" | "done";

export interface UserTask {
  id: number;
  title: string;
  description: string | null;
  client_tag: string | null;
  priority: UserTaskPriority;
  status: UserTaskStatus;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
  modified_at: string;
}
```

### 7. Frontend API Functions
**File: `frontend/src/lib/api.ts`** — add:

- `fetchUserTasks(status?, clientTag?)` → `UserTask[]`
- `createUserTask(data)` → `UserTask`
- `updateUserTask(id, data)` → `UserTask`
- `toggleUserTask(id)` → `UserTask`
- `deleteUserTask(id)` → void
- `fetchUserTaskTags()` → `string[]`

### 8. New Component: Personal Task Board
**New file: `frontend/src/components/pm-dashboard/personal-task-board.tsx`**

Features:
- Card-based layout with a header "My Tasks" and a "+ Add Task" button
- Inline add form: title input, client tag dropdown (autocomplete from existing clients), priority select, optional due date
- Task list grouped/filterable by client tag (colored badges, like Outlook categories)
- Each task row: checkbox, title, client tag badge, priority indicator, due date, edit/delete actions
- Checked tasks show `completed_at` date inline and move to a collapsible "Completed" section at bottom
- Filter bar: filter by client tag, show/hide completed

### 9. Wire Into Dashboard Page
**File: `frontend/src/components/pages/pm-dashboard-page-client.tsx`**

- Import and render `<PersonalTaskBoard />` **above** the `<KanbanBoard />`
- Component manages its own state internally (self-contained data fetching)

### 10. Completion Date on Kanban Task Checklist
**File: `frontend/src/components/pm-dashboard/task-checklist.tsx`**

- When `task.status === "done"` and `task.actual_date` exists, show an inline badge: `"Done {formatted_date}"`
- The backend already sets `actual_date` when status → done (in `update_task_status` in `projects.py`)
- Add a small `<Badge>` next to the status badge showing the completion date

### 11. Set Aside Gantt
**File: `frontend/src/components/pm-dashboard/project-detail-sheet.tsx`**

- Comment out / remove the `<GanttDetail>` import and rendering
- Keep the backend code and component files intact (not deleted, just not rendered)

---

## Files Modified (summary)

| File | Action |
|------|--------|
| `src/utils/db/base.py` | Add `user_tasks` table DDL |
| `src/utils/db/user_tasks.py` | **NEW** — CRUD functions |
| `src/utils/db/__init__.py` | Export new functions |
| `api/models/schemas.py` | Add UserTask request/response models |
| `api/routers/user_tasks.py` | **NEW** — API endpoints |
| `api/main.py` | Register user_tasks router |
| `frontend/src/lib/types.ts` | Add UserTask types |
| `frontend/src/lib/api.ts` | Add user task API functions |
| `frontend/src/components/pm-dashboard/personal-task-board.tsx` | **NEW** — main UI component |
| `frontend/src/components/pages/pm-dashboard-page-client.tsx` | Add PersonalTaskBoard above Kanban |
| `frontend/src/components/pm-dashboard/task-checklist.tsx` | Add completion date badge |
| `frontend/src/components/pm-dashboard/project-detail-sheet.tsx` | Remove GanttDetail rendering |

---

## Verification

1. **DB**: Run the app → verify `user_tasks` table created in `crm_data.db`
2. **API**: Test endpoints via curl/browser:
   - `POST /api/user-tasks` with `{"title": "Email client about layout", "client_tag": "SunPharma"}`
   - `GET /api/user-tasks` → see created task
   - `PUT /api/user-tasks/{id}/toggle` → verify `completed_at` populated
3. **Frontend**: Load PM Dashboard → verify:
   - Personal task board appears above Kanban
   - Can add tasks with client tags
   - Can check/uncheck tasks, completed_at date appears
   - Client tag filter works
   - Gantt section no longer shows in project detail sheet
4. **Kanban checklist**: Open a project → check a task → verify "Done {date}" badge appears inline
