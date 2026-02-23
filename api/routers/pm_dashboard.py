"""PM Dashboard API endpoints."""

from __future__ import annotations

import os
import tempfile
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status

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
def get_at_risk() -> dict[str, Any]:
    return get_at_risk_summary()


@router.get("/stalls", response_model=list[StallAlertResponse])
def get_stalls() -> list[dict[str, Any]]:
    return detect_stalls()


@router.get("/projects", response_model=list[ProjectListResponse])
def list_projects() -> list[dict[str, Any]]:
    return load_all_projects()


@router.post(
    "/projects",
    response_model=ProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_record(payload: ProjectCreateRequest) -> dict[str, Any]:
    created = create_project(payload.model_dump())
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project.",
        )
    return created


@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: int) -> dict[str, Any]:
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


@router.put("/projects/{project_id}", response_model=ProjectDetailResponse)
def update_project_record(project_id: int, payload: ProjectUpdateRequest) -> dict[str, Any]:
    updated = update_project(project_id, payload.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return updated


@router.delete("/projects/{project_id}")
def delete_project_record(project_id: int) -> dict[str, Any]:
    deleted = delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return {"deleted": True, "id": project_id}


@router.put("/tasks/{task_id}/status", response_model=ProjectTaskResponse)
def update_project_task_status(task_id: int, payload: TaskStatusUpdateRequest) -> dict[str, Any]:
    try:
        updated_task = update_task_status(task_id, payload.status, notes=payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not updated_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return updated_task


@router.post("/projects/{project_id}/gantt-upload", response_model=ProjectDetailResponse)
async def upload_gantt_pdf(project_id: int, file: UploadFile = File(...)) -> dict[str, Any]:
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF uploads are supported.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

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

    updated = save_gantt_data(project_id, parsed)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save parsed Gantt data.",
        )
    return updated


@router.get("/insights", response_model=list[InsightResponse])
def list_global_insights() -> list[dict[str, Any]]:
    return get_all_insights()


@router.get("/projects/{project_id}/insights", response_model=list[InsightResponse])
def list_project_insights(project_id: int) -> list[dict[str, Any]]:
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return get_all_insights(project_id=project_id)
