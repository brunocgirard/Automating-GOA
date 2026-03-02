"""Rule-based PM insight generation service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.utils.db import detect_stalls, load_all_projects, load_project

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    formats = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def get_stall_alerts(
    threshold_days: int = 7,
    project_id: int | None = None,
    *,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> list[dict[str, Any]]:
    """Return critical/warning alerts for stalled in-progress tasks."""
    alerts: list[dict[str, Any]] = []
    for entry in detect_stalls(
        threshold_days=threshold_days,
        project_id=project_id,
        owner_user_id=owner_user_id,
        include_all_for_admin=include_all_for_admin,
    ):
        days_stalled = int(entry.get("days_stalled") or 0)
        severity = "critical" if days_stalled >= 14 else "warning"
        alerts.append(
            {
                "project_id": entry.get("project_id"),
                "project_name": entry.get("project_name"),
                "task_id": entry.get("task_id"),
                "task_name": entry.get("task_name"),
                "phase": entry.get("phase"),
                "days_stalled": days_stalled,
                "type": "stall",
                "severity": severity,
                "title": f"{days_stalled} day stall detected",
                "message": f"{entry.get('task_name') or 'Task'} has been in progress for {days_stalled} days.",
            }
        )
    return alerts


def get_critical_path_alerts(
    project_id: int | None = None,
    *,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> list[dict[str, Any]]:
    """Flag pending tasks with near-term planned dates."""
    project_rows = load_all_projects(
        owner_user_id=owner_user_id,
        include_all_for_admin=include_all_for_admin,
    )
    if project_id is not None:
        project_rows = [row for row in project_rows if int(row.get("id") or 0) == project_id]

    alerts: list[dict[str, Any]] = []
    now = datetime.now().date()
    for project_row in project_rows:
        project_detail = load_project(
            int(project_row.get("id") or 0),
            owner_user_id=owner_user_id,
            include_all_for_admin=include_all_for_admin,
        )
        if not project_detail:
            continue

        for task in project_detail.get("tasks") or []:
            status = str(task.get("status") or "").strip().lower()
            if status in {"done", "skipped"}:
                continue

            planned_dt = _to_datetime(str(task.get("planned_date") or "").strip() or None)
            if not planned_dt:
                continue
            days_remaining = (planned_dt.date() - now).days
            if days_remaining > 3:
                continue

            severity = "critical" if days_remaining <= 1 else "warning"
            alerts.append(
                {
                    "project_id": project_detail.get("id"),
                    "project_name": project_detail.get("project_name"),
                    "task_id": task.get("id"),
                    "task_name": task.get("task_name"),
                    "phase": task.get("phase"),
                    "type": "critical_path",
                    "severity": severity,
                    "title": "Upcoming planned task",
                    "message": (
                        f"{task.get('task_name') or 'Task'} is planned for "
                        f"{planned_dt.strftime('%Y-%m-%d')} and is still {status or 'pending'}."
                    ),
                }
            )
    return alerts


def _get_resource_contention_alerts(
    project_id: int | None = None,
    *,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> list[dict[str, Any]]:
    projects = load_all_projects(
        owner_user_id=owner_user_id,
        include_all_for_admin=include_all_for_admin,
    )
    phase_buckets: dict[str, list[dict[str, Any]]] = {}
    for project in projects:
        phase = str(project.get("current_phase") or "").strip()
        if not phase:
            continue
        phase_buckets.setdefault(phase, []).append(project)

    alerts: list[dict[str, Any]] = []
    for phase, phase_projects in phase_buckets.items():
        if len(phase_projects) < 3:
            continue

        for project in phase_projects:
            current_id = int(project.get("id") or 0)
            if project_id is not None and current_id != project_id:
                continue
            alerts.append(
                {
                    "project_id": current_id,
                    "project_name": project.get("project_name"),
                    "task_id": None,
                    "task_name": project.get("current_task"),
                    "phase": phase,
                    "type": "resource_contention",
                    "severity": "info",
                    "title": "Phase congestion",
                    "message": f"{len(phase_projects)} projects are active in phase '{phase}'.",
                }
            )
    return alerts


def get_all_insights(
    project_id: int | None = None,
    *,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> list[dict[str, Any]]:
    """Aggregate and rank insights; capped at 2 per project."""
    combined = (
        get_stall_alerts(
            project_id=project_id,
            owner_user_id=owner_user_id,
            include_all_for_admin=include_all_for_admin,
        )
        + get_critical_path_alerts(
            project_id=project_id,
            owner_user_id=owner_user_id,
            include_all_for_admin=include_all_for_admin,
        )
        + _get_resource_contention_alerts(
            project_id=project_id,
            owner_user_id=owner_user_id,
            include_all_for_admin=include_all_for_admin,
        )
    )
    combined.sort(
        key=lambda row: (
            _SEVERITY_ORDER.get(str(row.get("severity")), 99),
            -int(row.get("days_stalled") or 0),
            str(row.get("project_name") or ""),
            str(row.get("task_name") or ""),
        )
    )

    if project_id is not None:
        return combined[:2]

    result: list[dict[str, Any]] = []
    count_by_project: dict[int | None, int] = {}
    for insight in combined:
        pid_raw = insight.get("project_id")
        pid = int(pid_raw) if isinstance(pid_raw, int) else None
        used = count_by_project.get(pid, 0)
        if used >= 2:
            continue
        result.append(insight)
        count_by_project[pid] = used + 1
    return result
