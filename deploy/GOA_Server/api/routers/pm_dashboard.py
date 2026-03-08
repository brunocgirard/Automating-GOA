"""PM Dashboard API endpoints."""

from __future__ import annotations

import os
import tempfile
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.dependencies.auth import require_authenticated_user
from api.models.schemas import (
    AtRiskSummaryResponse,
    InsightResponse,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectTaskResponse,
    ProjectUpdateRequest,
    StallAlertResponse,
    TaskStatusUpdateRequest,
)
from api.routers._helpers import require, scope_kwargs, user_id, validate_pdf_upload
from api.services.insights_service import get_all_insights
from src.utils.db import (
    create_project,
    delete_project,
    detect_stalls,
    get_at_risk_summary,
    load_all_projects,
    load_project,
    save_gantt_data,
    update_project,
    update_task_status,
)
from src.utils.gantt_parser import parse_gantt_pdf

router = APIRouter(prefix="/api/pm", tags=["PM Dashboard"])


@router.get("/at-risk", response_model=AtRiskSummaryResponse)
def get_at_risk(
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    return get_at_risk_summary(**scope_kwargs(current_user))


@router.get("/stalls", response_model=list[StallAlertResponse])
def get_stalls(
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> list[dict[str, Any]]:
    return detect_stalls(**scope_kwargs(current_user))


@router.get("/projects", response_model=list[ProjectListResponse])
def list_projects(
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> list[dict[str, Any]]:
    return load_all_projects(**scope_kwargs(current_user))


@router.post(
    "/projects",
    response_model=ProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_record(
    payload: ProjectCreateRequest,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    created = create_project(payload.model_dump(), owner_user_id=user_id(current_user))
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project.",
        )
    return created


@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: int,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    return require(load_project(project_id, **scope_kwargs(current_user)), "Project not found.")


@router.put("/projects/{project_id}", response_model=ProjectDetailResponse)
def update_project_record(
    project_id: int,
    payload: ProjectUpdateRequest,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    updated = update_project(
        project_id,
        payload.model_dump(exclude_none=True),
        **scope_kwargs(current_user),
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return updated


@router.delete("/projects/{project_id}")
def delete_project_record(
    project_id: int,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    deleted = delete_project(project_id, **scope_kwargs(current_user))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return {"deleted": True, "id": project_id}


@router.put("/tasks/{task_id}/status", response_model=ProjectTaskResponse)
def update_project_task_status(
    task_id: int,
    payload: TaskStatusUpdateRequest,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    try:
        updated_task = update_task_status(
            task_id,
            payload.status,
            notes=payload.notes,
            **scope_kwargs(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not updated_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return updated_task


@router.post("/projects/{project_id}/gantt-upload", response_model=ProjectDetailResponse)
async def upload_gantt_pdf(
    project_id: int,
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    require(load_project(project_id, **scope_kwargs(current_user)), "Project not found.")
    file_bytes = await validate_pdf_upload(file)

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as handle:
            handle.write(file_bytes)
            temp_path = handle.name
        parsed = parse_gantt_pdf(temp_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse Gantt PDF: {exc}",
        ) from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    updated = save_gantt_data(project_id, parsed, **scope_kwargs(current_user))
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save parsed Gantt data.",
        )
    return updated


@router.get("/insights", response_model=list[InsightResponse])
def list_global_insights(
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> list[dict[str, Any]]:
    return get_all_insights(**scope_kwargs(current_user))


@router.get("/projects/{project_id}/insights", response_model=list[InsightResponse])
def list_project_insights(
    project_id: int,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> list[dict[str, Any]]:
    require(load_project(project_id, **scope_kwargs(current_user)), "Project not found.")
    return get_all_insights(project_id=project_id, **scope_kwargs(current_user))
