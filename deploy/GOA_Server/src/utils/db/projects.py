"""Project management persistence utilities for the PM dashboard."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from .base import (
    DB_PATH,
    get_connection,
    owner_scope_clause,
    row_to_dict,
    rows_to_dicts,
    safe_json_loads,
    timestamp,
)

PROJECT_PHASES: tuple[str, ...] = (
    "sales_onboarding",
    "engineering_prep",
    "design_approval",
    "production",
    "delivery",
)
TASK_STATUSES: tuple[str, ...] = ("pending", "in_progress", "done", "skipped")
RISK_LEVELS: tuple[str, ...] = ("on_track", "at_risk", "overdue")
COMPLETE_TASK_STATUSES: set[str] = {"done", "skipped"}
DEFAULT_TASKS: tuple[tuple[int, str, str], ...] = (
    (1, "Down Payment Received", "sales_onboarding"),
    (2, "Introduction Letter", "sales_onboarding"),
    (3, "Binder", "sales_onboarding"),
    (4, "Transfer File - From Sales Dept", "sales_onboarding"),
    (5, "Engineering Samples Received", "engineering_prep"),
    (6, "Product Matrix Sent to Client", "engineering_prep"),
    (7, "Product Matrix Confirmed by Client", "engineering_prep"),
    (8, "Layout Issued for Approval", "design_approval"),
    (9, "Layout Approved (Signed)", "design_approval"),
    (10, "Layout Approval Confirmation Paid", "design_approval"),
    (11, "GOA(s)", "design_approval"),
    (12, "Pre-Kick Off", "design_approval"),
    (13, "Timeline Published - Gantt to Customer", "production"),
    (14, "Bulk Samples Requested", "production"),
    (15, "Bulk Samples Received", "production"),
    (16, "Samples Sent for Feeders", "production"),
    (17, "Engineering Kick Off", "production"),
    (18, "Project Released from Design", "production"),
    (19, "Third Party Equipment Ordered", "production"),
    (20, "Third Party Equipment Received", "production"),
    (21, "Revised FAT Published", "delivery"),
    (22, "Actual FAT", "delivery"),
    (23, "COR Completion", "delivery"),
    (24, "Crating", "delivery"),
    (25, "Pre-Ship Payments", "delivery"),
    (26, "Shipment", "delivery"),
)
def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    candidates = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _days_since(value: str | None) -> int | None:
    dt_value = _to_datetime(value)
    if not dt_value:
        return None
    days = (datetime.now().date() - dt_value.date()).days
    return max(days, 0)


def _is_complete(status: str | None) -> bool:
    return str(status or "").strip().lower() in COMPLETE_TASK_STATUSES


def _parse_json(value: str | None) -> dict[str, Any] | None:
    parsed = safe_json_loads(value)
    if isinstance(parsed, dict):
        return parsed
    return None


def _normalize_phase(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in PROJECT_PHASES:
        return normalized
    return None


def _normalize_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in TASK_STATUSES:
        return normalized
    return "pending"


def _normalize_risk(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in RISK_LEVELS:
        return normalized
    return "on_track"


def _normalize_project_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or "active"


def _phase_for_project(tasks: list[dict[str, Any]]) -> str | None:
    if not tasks:
        return None

    for phase in PROJECT_PHASES:
        phase_tasks = [task for task in tasks if task.get("phase") == phase]
        if not phase_tasks:
            continue
        if any(not _is_complete(task.get("status")) for task in phase_tasks):
            return phase

    return "delivery"


def _current_task_name(tasks: list[dict[str, Any]], phase: str | None) -> str | None:
    if not phase:
        return None

    phase_tasks = sorted(
        [task for task in tasks if task.get("phase") == phase],
        key=lambda row: int(row.get("task_order") or 0),
    )
    for task in phase_tasks:
        if not _is_complete(task.get("status")):
            return str(task.get("task_name") or "")
    return None


def _progress_pct(tasks: list[dict[str, Any]]) -> int:
    if not tasks:
        return 0
    complete_count = sum(1 for task in tasks if _is_complete(task.get("status")))
    return int(round((complete_count / len(tasks)) * 100))


def _days_in_phase(
    cursor: sqlite3.Cursor,
    project_id: int,
    phase: str | None,
    tasks: list[dict[str, Any]],
) -> int | None:
    if not phase:
        return None

    phase_task_ids = [int(task["id"]) for task in tasks if task.get("phase") == phase and task.get("id")]
    if not phase_task_ids:
        return None

    placeholders = ",".join("?" for _ in phase_task_ids)
    cursor.execute(
        f"""
        SELECT MIN(tt.transitioned_at)
        FROM task_transitions tt
        JOIN project_tasks pt ON pt.id = tt.project_task_id
        WHERE pt.project_id = ?
          AND pt.id IN ({placeholders})
          AND tt.to_status = 'in_progress'
        """,
        [project_id, *phase_task_ids],
    )
    row = cursor.fetchone()
    started_at = row[0] if row and row[0] else None

    if not started_at:
        candidate_dates: list[str] = []
        for task in tasks:
            if task.get("phase") != phase:
                continue
            status = _normalize_status(str(task.get("status") or ""))
            if status in {"in_progress", "done", "skipped"}:
                modified = task.get("modified_date")
                actual = task.get("actual_date")
                if isinstance(actual, str) and actual.strip():
                    candidate_dates.append(actual.strip())
                elif isinstance(modified, str) and modified.strip():
                    candidate_dates.append(modified.strip())
        started_at = min(candidate_dates) if candidate_dates else None

    return _days_since(started_at)


def _max_stalled_days(cursor: sqlite3.Cursor, project_id: int) -> int:
    cursor.execute(
        """
        SELECT id, status, modified_date
        FROM project_tasks
        WHERE project_id = ?
          AND status = 'in_progress'
        """,
        (project_id,),
    )
    rows = cursor.fetchall()
    max_days = 0
    for row in rows:
        task_id = int(row[0])
        fallback_timestamp = row[2] if len(row) > 2 else None
        cursor.execute(
            """
            SELECT transitioned_at
            FROM task_transitions
            WHERE project_task_id = ?
              AND to_status = 'in_progress'
            ORDER BY transitioned_at DESC, id DESC
            LIMIT 1
            """,
            (task_id,),
        )
        transition_row = cursor.fetchone()
        started_at = transition_row[0] if transition_row and transition_row[0] else fallback_timestamp
        stalled_days = _days_since(started_at) or 0
        if stalled_days > max_days:
            max_days = stalled_days
    return max_days


def _derive_risk_level(
    cursor: sqlite3.Cursor,
    project: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> str:
    if tasks and all(_is_complete(task.get("status")) for task in tasks):
        return "on_track"

    target_end = _to_datetime(str(project.get("target_end_date") or "").strip() or None)
    if target_end and datetime.now().date() > target_end.date():
        return "overdue"

    stalled_days = _max_stalled_days(cursor, int(project.get("id") or 0))
    if stalled_days >= 14:
        return "overdue"
    if stalled_days >= 7:
        return "at_risk"
    return "on_track"


def _load_project_tasks(cursor: sqlite3.Cursor, project_id: int) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, project_id, task_name, task_order, phase, status, planned_date, actual_date, notes, modified_date
        FROM project_tasks
        WHERE project_id = ?
        ORDER BY task_order ASC, id ASC
        """,
        (project_id,),
    )
    return rows_to_dicts(cursor.fetchall())


def _load_latest_project_for_quote_ref(
    cursor: sqlite3.Cursor,
    quote_ref: str,
    *,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> dict[str, Any] | None:
    scope_sql, scope_params = owner_scope_clause(
        owner_user_id,
        include_all_for_admin,
        table_alias="projects",
    )
    cursor.execute(
        f"""
        SELECT
            id,
            project_name,
            customer_name,
            quote_ref,
            machine_summary,
            status,
            risk_level,
            start_date,
            target_end_date,
            actual_end_date,
            gantt_data_json,
            created_date,
            modified_date
        FROM projects
        WHERE quote_ref = ?{scope_sql}
        ORDER BY modified_date DESC, id DESC
        LIMIT 1
        """,
        (quote_ref, *scope_params),
    )
    row = cursor.fetchone()
    return row_to_dict(row)


def _project_with_metrics(
    cursor: sqlite3.Cursor,
    project: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    current_phase = _phase_for_project(tasks)
    current_task = _current_task_name(tasks, current_phase)
    days_in_phase = _days_in_phase(cursor, int(project["id"]), current_phase, tasks)
    progress_pct = _progress_pct(tasks)
    computed_risk = _derive_risk_level(cursor, project, tasks)

    payload = dict(project)
    payload.update(
        {
            "current_phase": current_phase,
            "current_task": current_task,
            "days_in_phase": days_in_phase,
            "progress_pct": progress_pct,
            "risk_level": computed_risk,
        }
    )
    return payload


def _upsert_project_risk(cursor: sqlite3.Cursor, project_id: int, risk_level: str) -> None:
    cursor.execute(
        """
        UPDATE projects
        SET risk_level = ?, modified_date = ?
        WHERE id = ?
        """,
        (risk_level, timestamp(), project_id),
    )


def create_project(
    data: dict[str, Any],
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
) -> dict[str, Any] | None:
    """Create a project and seed default PM tasks."""
    project_name = str(data.get("project_name") or "").strip()
    customer_name = str(data.get("customer_name") or "").strip()
    if not project_name or not customer_name:
        print("Error: create_project requires project_name and customer_name.")
        return None

    quote_ref = str(data.get("quote_ref") or "").strip() or None
    machine_summary = str(data.get("machine_summary") or "").strip() or None
    status = _normalize_project_status(data.get("status"))
    risk_level = _normalize_risk(data.get("risk_level"))
    start_date = str(data.get("start_date") or "").strip() or None
    target_end_date = str(data.get("target_end_date") or "").strip() or None
    actual_end_date = str(data.get("actual_end_date") or "").strip() or None
    resolved_owner_user_id = (
        owner_user_id
        if isinstance(owner_user_id, int) and owner_user_id > 0
        else (
            int(data.get("owner_user_id"))
            if isinstance(data.get("owner_user_id"), int) and int(data.get("owner_user_id")) > 0
            else None
        )
    )
    gantt_data = data.get("gantt_data")
    if isinstance(gantt_data, dict):
        gantt_data_json = json.dumps(gantt_data)
    else:
        gantt_data_json = None

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        now = timestamp()
        cursor.execute(
            """
            INSERT INTO projects (
                project_name,
                customer_name,
                quote_ref,
                machine_summary,
                status,
                risk_level,
                start_date,
                target_end_date,
                actual_end_date,
                gantt_data_json,
                created_date,
                modified_date,
                owner_user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_name,
                customer_name,
                quote_ref,
                machine_summary,
                status,
                risk_level,
                start_date,
                target_end_date,
                actual_end_date,
                gantt_data_json,
                now,
                now,
                resolved_owner_user_id,
            ),
        )
        project_id = int(cursor.lastrowid)
        task_rows = [
            (
                project_id,
                task_name,
                task_order,
                phase,
                "pending",
                None,
                None,
                None,
                now,
            )
            for task_order, task_name, phase in DEFAULT_TASKS
        ]
        cursor.executemany(
            """
            INSERT INTO project_tasks (
                project_id,
                task_name,
                task_order,
                phase,
                status,
                planned_date,
                actual_date,
                notes,
                modified_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            task_rows,
        )
        conn.commit()
        return load_project(
            project_id,
            db_path=db_path,
            owner_user_id=resolved_owner_user_id,
            include_all_for_admin=False,
        )
    except Exception as exc:
        print(f"Error creating project: {exc}")
        return None
    finally:
        if conn:
            conn.close()


def load_project_by_quote_ref(
    quote_ref: str,
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> dict[str, Any] | None:
    """Load the most recently modified project for a quote reference."""
    normalized_quote_ref = str(quote_ref or "").strip()
    if not normalized_quote_ref:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        row = _load_latest_project_for_quote_ref(
            cursor,
            normalized_quote_ref,
            owner_user_id=owner_user_id,
            include_all_for_admin=include_all_for_admin,
        )
        if not row:
            return None
        tasks = _load_project_tasks(cursor, int(row["id"]))
        payload = _project_with_metrics(cursor, row, tasks)
        payload["tasks"] = tasks
        payload["gantt_data"] = _parse_json(row.get("gantt_data_json"))
        payload.pop("gantt_data_json", None)
        return payload
    except Exception as exc:
        print(f"Error loading project by quote_ref '{normalized_quote_ref}': {exc}")
        return None
    finally:
        if conn:
            conn.close()


def ensure_project_for_quote(
    quote_ref: str,
    *,
    customer_name: str,
    project_name: str | None = None,
    machine_summary: str | None = None,
    start_date: str | None = None,
    target_end_date: str | None = None,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
    db_path: str = DB_PATH,
) -> dict[str, Any] | None:
    """Create a project for the quote if one doesn't already exist."""
    normalized_quote_ref = str(quote_ref or "").strip()
    normalized_customer = str(customer_name or "").strip()
    if not normalized_quote_ref or not normalized_customer:
        return None

    existing = load_project_by_quote_ref(
        normalized_quote_ref,
        db_path=db_path,
        owner_user_id=owner_user_id,
        include_all_for_admin=include_all_for_admin,
    )
    if existing:
        return existing

    normalized_project_name = str(project_name or "").strip()
    if not normalized_project_name:
        if machine_summary and str(machine_summary).strip():
            normalized_project_name = f"{normalized_customer} - {str(machine_summary).strip()}"
        else:
            normalized_project_name = normalized_quote_ref

    return create_project(
        {
            "project_name": normalized_project_name,
            "customer_name": normalized_customer,
            "quote_ref": normalized_quote_ref,
            "machine_summary": str(machine_summary or "").strip() or None,
            "start_date": str(start_date or "").strip() or _today(),
            "target_end_date": str(target_end_date or "").strip() or None,
            "owner_user_id": owner_user_id if isinstance(owner_user_id, int) and owner_user_id > 0 else None,
        },
        db_path=db_path,
        owner_user_id=owner_user_id,
    )


def load_all_projects(
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> list[dict[str, Any]]:
    """Load project list with computed PM metrics."""
    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        scope_sql, scope_params = owner_scope_clause(
            owner_user_id,
            include_all_for_admin,
            table_alias="projects",
        )
        cursor.execute(
            f"""
            SELECT
                id,
                project_name,
                customer_name,
                quote_ref,
                machine_summary,
                status,
                risk_level,
                start_date,
                target_end_date,
                actual_end_date,
                gantt_data_json,
                created_date,
                modified_date
            FROM projects
            WHERE 1 = 1{scope_sql}
            ORDER BY modified_date DESC, id DESC
            """,
            tuple(scope_params),
        )
        rows = rows_to_dicts(cursor.fetchall())
        projects: list[dict[str, Any]] = []
        for row in rows:
            tasks = _load_project_tasks(cursor, int(row["id"]))
            payload = _project_with_metrics(cursor, row, tasks)
            payload.pop("gantt_data_json", None)
            projects.append(payload)

        for project in projects:
            current_risk = _normalize_risk(project.get("risk_level"))
            stored_risk = _normalize_risk(next((row.get("risk_level") for row in rows if row["id"] == project["id"]), ""))
            if current_risk != stored_risk:
                _upsert_project_risk(cursor, int(project["id"]), current_risk)
        conn.commit()

        return projects
    except Exception as exc:
        print(f"Error loading projects: {exc}")
        return []
    finally:
        if conn:
            conn.close()


def load_project(
    project_id: int,
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> dict[str, Any] | None:
    """Load a single project with tasks and parsed gantt payload."""
    if not isinstance(project_id, int) or project_id <= 0:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        scope_sql, scope_params = owner_scope_clause(
            owner_user_id,
            include_all_for_admin,
            table_alias="projects",
        )
        cursor.execute(
            f"""
            SELECT
                id,
                project_name,
                customer_name,
                quote_ref,
                machine_summary,
                status,
                risk_level,
                start_date,
                target_end_date,
                actual_end_date,
                gantt_data_json,
                created_date,
                modified_date
            FROM projects
            WHERE id = ?{scope_sql}
            LIMIT 1
            """,
            (project_id, *scope_params),
        )
        row = cursor.fetchone()
        if not row:
            return None
        project = row_to_dict(row) or {}
        tasks = _load_project_tasks(cursor, project_id)
        payload = _project_with_metrics(cursor, project, tasks)
        payload["tasks"] = tasks
        payload["gantt_data"] = _parse_json(project.get("gantt_data_json"))
        payload.pop("gantt_data_json", None)
        computed_risk = _normalize_risk(payload.get("risk_level"))
        stored_risk = _normalize_risk(project.get("risk_level"))
        if computed_risk != stored_risk:
            _upsert_project_risk(cursor, project_id, computed_risk)
            conn.commit()
        return payload
    except Exception as exc:
        print(f"Error loading project {project_id}: {exc}")
        return None
    finally:
        if conn:
            conn.close()


def update_project(
    project_id: int,
    data: dict[str, Any],
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> dict[str, Any] | None:
    """Update editable project fields and return refreshed payload."""
    if not isinstance(project_id, int) or project_id <= 0:
        return None

    allowed_fields = {
        "project_name",
        "customer_name",
        "quote_ref",
        "machine_summary",
        "status",
        "risk_level",
        "start_date",
        "target_end_date",
        "actual_end_date",
    }
    updates: list[str] = []
    params: list[Any] = []
    for key, value in (data or {}).items():
        if key not in allowed_fields:
            continue

        if key == "risk_level":
            normalized = _normalize_risk(str(value or ""))
            updates.append(f"{key} = ?")
            params.append(normalized)
            continue
        if key == "status":
            updates.append(f"{key} = ?")
            params.append(_normalize_project_status(str(value or "")))
            continue
        if key in {"quote_ref", "machine_summary", "start_date", "target_end_date", "actual_end_date"}:
            normalized_text = str(value or "").strip() or None
            updates.append(f"{key} = ?")
            params.append(normalized_text)
            continue

        updates.append(f"{key} = ?")
        params.append(str(value or "").strip())

    if "gantt_data" in data:
        gantt_data = data.get("gantt_data")
        if isinstance(gantt_data, dict):
            updates.append("gantt_data_json = ?")
            params.append(json.dumps(gantt_data))

    if not updates:
        return load_project(
            project_id,
            db_path=db_path,
            owner_user_id=owner_user_id,
            include_all_for_admin=include_all_for_admin,
        )

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        scope_sql, scope_params = owner_scope_clause(
            owner_user_id,
            include_all_for_admin,
            table_alias="projects",
        )
        updates.append("modified_date = ?")
        params.append(timestamp())
        params.extend([project_id, *scope_params])
        cursor.execute(
            f"""
            UPDATE projects
            SET {", ".join(updates)}
            WHERE id = ?{scope_sql}
            """,
            params,
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    except Exception as exc:
        print(f"Error updating project {project_id}: {exc}")
        return None
    finally:
        if conn:
            conn.close()

    return load_project(
        project_id,
        db_path=db_path,
        owner_user_id=owner_user_id,
        include_all_for_admin=include_all_for_admin,
    )


def delete_project(
    project_id: int,
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> bool:
    """Delete a project and all related project tasks/transitions."""
    if not isinstance(project_id, int) or project_id <= 0:
        return False

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        scope_sql, scope_params = owner_scope_clause(
            owner_user_id,
            include_all_for_admin,
            table_alias="projects",
        )
        cursor.execute(
            f"DELETE FROM projects WHERE id = ?{scope_sql}",
            (project_id, *scope_params),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        print(f"Error deleting project {project_id}: {exc}")
        return False
    finally:
        if conn:
            conn.close()


def update_task_status(
    task_id: int,
    new_status: str,
    notes: str | None = None,
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> dict[str, Any] | None:
    """Update task status with transition logging and risk recalculation."""
    raw_status = str(new_status or "").strip().lower()
    if raw_status not in TASK_STATUSES:
        raise ValueError(f"Invalid task status: {new_status}")
    normalized_status = raw_status

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        scope_sql, scope_params = owner_scope_clause(
            owner_user_id,
            include_all_for_admin,
            table_alias="p",
        )
        cursor.execute(
            f"""
            SELECT
                pt.id AS id,
                pt.project_id,
                pt.task_name,
                pt.task_order,
                pt.phase,
                pt.status,
                pt.planned_date,
                pt.actual_date,
                pt.notes,
                pt.modified_date
            FROM project_tasks pt
            JOIN projects p ON p.id = pt.project_id
            WHERE pt.id = ?{scope_sql}
            LIMIT 1
            """,
            (task_id, *scope_params),
        )
        existing = cursor.fetchone()
        if not existing:
            return None

        task = dict(existing)
        old_status = _normalize_status(task.get("status"))
        now = timestamp()

        actual_date: str | None = task.get("actual_date")
        if normalized_status == "done":
            actual_date = _today()
        elif old_status == "done" and normalized_status != "done":
            actual_date = None

        if notes is None:
            notes_value = task.get("notes")
        else:
            notes_value = str(notes).strip() or None

        cursor.execute(
            """
            UPDATE project_tasks
            SET status = ?, actual_date = ?, notes = ?, modified_date = ?
            WHERE id = ?
            """,
            (normalized_status, actual_date, notes_value, now, task_id),
        )

        if old_status != normalized_status:
            cursor.execute(
                """
                INSERT INTO task_transitions (
                    project_task_id,
                    from_status,
                    to_status,
                    transitioned_at
                ) VALUES (?, ?, ?, ?)
                """,
                (task_id, old_status, normalized_status, now),
            )

        project_id = int(task["project_id"])
        cursor.execute(
            """
            SELECT
                id,
                project_name,
                customer_name,
                quote_ref,
                machine_summary,
                status,
                risk_level,
                start_date,
                target_end_date,
                actual_end_date,
                gantt_data_json,
                created_date,
                modified_date
            FROM projects
            WHERE id = ?
            LIMIT 1
            """,
            (project_id,),
        )
        project_row = cursor.fetchone()
        if project_row:
            project_payload = dict(project_row)
            tasks = _load_project_tasks(cursor, project_id)
            computed_risk = _derive_risk_level(cursor, project_payload, tasks)
            _upsert_project_risk(cursor, project_id, computed_risk)

        conn.commit()

        cursor.execute(
            """
            SELECT id, project_id, task_name, task_order, phase, status, planned_date, actual_date, notes, modified_date
            FROM project_tasks
            WHERE id = ?
            LIMIT 1
            """,
            (task_id,),
        )
        refreshed = cursor.fetchone()
        return row_to_dict(refreshed)
    except Exception as exc:
        print(f"Error updating task {task_id}: {exc}")
        return None
    finally:
        if conn:
            conn.close()


def save_gantt_data(
    project_id: int,
    gantt_data: dict[str, Any],
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> dict[str, Any] | None:
    """Persist parsed Gantt payload on a project."""
    if not isinstance(project_id, int) or project_id <= 0:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        scope_sql, scope_params = owner_scope_clause(
            owner_user_id,
            include_all_for_admin,
            table_alias="projects",
        )
        cursor.execute(
            f"""
            UPDATE projects
            SET gantt_data_json = ?, modified_date = ?
            WHERE id = ?{scope_sql}
            """,
            (json.dumps(gantt_data or {}), timestamp(), project_id, *scope_params),
        )
        if cursor.rowcount == 0:
            conn.commit()
            return None
        conn.commit()
        return load_project(
            project_id,
            db_path=db_path,
            owner_user_id=owner_user_id,
            include_all_for_admin=include_all_for_admin,
        )
    except Exception as exc:
        print(f"Error saving Gantt data for project {project_id}: {exc}")
        return None
    finally:
        if conn:
            conn.close()


def detect_stalls(
    threshold_days: int = 7,
    project_id: int | None = None,
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> list[dict[str, Any]]:
    """Detect in-progress tasks stalled beyond threshold days."""
    threshold = max(int(threshold_days), 0)
    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        scope_sql, scope_params = owner_scope_clause(
            owner_user_id,
            include_all_for_admin,
            table_alias="p",
        )
        if project_id is None:
            cursor.execute(
                f"""
                SELECT
                    pt.id AS task_id,
                    pt.project_id,
                    pt.task_name,
                    pt.phase,
                    pt.modified_date,
                    p.project_name
                FROM project_tasks pt
                JOIN projects p ON p.id = pt.project_id
                WHERE pt.status = 'in_progress'
                {scope_sql}
                """,
                tuple(scope_params),
            )
        else:
            cursor.execute(
                f"""
                SELECT
                    pt.id AS task_id,
                    pt.project_id,
                    pt.task_name,
                    pt.phase,
                    pt.modified_date,
                    p.project_name
                FROM project_tasks pt
                JOIN projects p ON p.id = pt.project_id
                WHERE pt.status = 'in_progress'
                  AND pt.project_id = ?
                {scope_sql}
                """,
                (project_id, *scope_params),
            )
        rows = rows_to_dicts(cursor.fetchall())

        results: list[dict[str, Any]] = []
        for row in rows:
            task_id = int(row["task_id"])
            cursor.execute(
                """
                SELECT transitioned_at
                FROM task_transitions
                WHERE project_task_id = ?
                  AND to_status = 'in_progress'
                ORDER BY transitioned_at DESC, id DESC
                LIMIT 1
                """,
                (task_id,),
            )
            transition = cursor.fetchone()
            started_at = transition[0] if transition and transition[0] else row.get("modified_date")
            days_stalled = _days_since(str(started_at) if started_at else None)
            if days_stalled is None or days_stalled <= threshold:
                continue
            results.append(
                {
                    "project_id": int(row["project_id"]),
                    "project_name": str(row.get("project_name") or ""),
                    "task_id": task_id,
                    "task_name": str(row.get("task_name") or ""),
                    "phase": str(row.get("phase") or ""),
                    "days_stalled": days_stalled,
                }
            )

        results.sort(key=lambda item: (-int(item["days_stalled"]), item["project_name"], item["task_name"]))
        return results
    except Exception as exc:
        print(f"Error detecting stalls: {exc}")
        return []
    finally:
        if conn:
            conn.close()


def get_at_risk_summary(
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> dict[str, Any]:
    """Return high-level at-risk summary for dashboard alert strip."""
    stalled = detect_stalls(
        threshold_days=7,
        db_path=db_path,
        owner_user_id=owner_user_id,
        include_all_for_admin=include_all_for_admin,
    )
    by_project: dict[int, dict[str, Any]] = {}
    for entry in stalled:
        project_id = int(entry["project_id"])
        existing = by_project.get(project_id)
        if not existing or int(entry["days_stalled"]) > int(existing["days_stalled"]):
            by_project[project_id] = {
                "project_id": project_id,
                "name": entry["project_name"],
                "task": entry["task_name"],
                "phase": entry["phase"],
                "days_stalled": int(entry["days_stalled"]),
            }

    projects = sorted(by_project.values(), key=lambda row: (-row["days_stalled"], row["name"]))
    return {
        "count": len(projects),
        "projects": projects[:5],
    }


def mark_project_task_done_for_quote(
    quote_ref: str,
    task_name: str,
    *,
    notes: str | None = None,
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> dict[str, Any] | None:
    """Mark a named PM task as done for the latest project linked to a quote."""
    normalized_quote_ref = str(quote_ref or "").strip()
    normalized_task_name = str(task_name or "").strip()
    if not normalized_quote_ref or not normalized_task_name:
        return None

    conn = None
    task_id: int | None = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        project_row = _load_latest_project_for_quote_ref(
            cursor,
            normalized_quote_ref,
            owner_user_id=owner_user_id,
            include_all_for_admin=include_all_for_admin,
        )
        if not project_row:
            return None
        project_id = int(project_row["id"])
        cursor.execute(
            """
            SELECT id, status
            FROM project_tasks
            WHERE project_id = ?
              AND LOWER(task_name) = LOWER(?)
            ORDER BY
              CASE WHEN status IN ('done', 'skipped') THEN 1 ELSE 0 END ASC,
              task_order ASC,
              id ASC
            LIMIT 1
            """,
            (project_id, normalized_task_name),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return None
        task_id = int(task_row[0])
        current_status = _normalize_status(task_row[1])
    except Exception as exc:
        print(
            f"Error finding PM task '{normalized_task_name}' for quote_ref '{normalized_quote_ref}': {exc}"
        )
        return None
    finally:
        if conn:
            conn.close()

    if task_id is None:
        return None

    if current_status == "done":
        return None
    return update_task_status(
        task_id,
        "done",
        notes=notes,
        db_path=db_path,
        owner_user_id=owner_user_id,
        include_all_for_admin=include_all_for_admin,
    )
