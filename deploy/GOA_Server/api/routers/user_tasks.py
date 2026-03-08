"""Personal task board API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies.auth import require_authenticated_user
from api.models.schemas import UserTaskCreateRequest, UserTaskResponse, UserTaskUpdateRequest
from api.routers._helpers import user_id
from src.utils.db import (
    create_user_task,
    delete_user_task,
    list_client_tags,
    list_user_tasks,
    toggle_user_task,
    update_user_task,
)

router = APIRouter(prefix="/api/user-tasks", tags=["User Tasks"])


@router.get("", response_model=list[UserTaskResponse])
def get_user_tasks(
    status: str | None = None,
    client_tag: str | None = None,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> list[dict[str, Any]]:
    return list_user_tasks(
        owner_user_id=user_id(current_user),
        status_filter=status,
        client_tag_filter=client_tag,
    )


@router.get("/tags", response_model=list[str])
def get_user_task_tags(
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> list[str]:
    return list_client_tags(owner_user_id=user_id(current_user))


@router.post("", response_model=UserTaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: UserTaskCreateRequest,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    created = create_user_task(
        owner_user_id=user_id(current_user),
        title=payload.title,
        description=payload.description,
        client_tag=payload.client_tag,
        priority=payload.priority,
        due_date=payload.due_date,
    )
    if not created:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create task.",
        )
    return created


@router.put("/{task_id}", response_model=UserTaskResponse)
def update_task(
    task_id: int,
    payload: UserTaskUpdateRequest,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update.",
        )

    updated = update_user_task(task_id, user_id(current_user), **updates)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return updated


@router.put("/{task_id}/toggle", response_model=UserTaskResponse)
def toggle_task(
    task_id: int,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    updated = toggle_user_task(task_id, owner_user_id=user_id(current_user))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return updated


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    deleted = delete_user_task(task_id, owner_user_id=user_id(current_user))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return {"deleted": True, "id": task_id}
