"""Shared helpers for API routers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, UploadFile, status

from api.dependencies.auth import is_admin_user
from src.utils.db import get_client_by_id, mark_project_task_done_for_quote

T = TypeVar("T")


def user_id(current_user: dict[str, Any]) -> int:
    """Return the authenticated user's ID."""
    return int(current_user["id"])


def scope_kwargs(current_user: dict[str, Any]) -> dict[str, int | bool]:
    """Build owner-scope kwargs for DB helpers."""
    return {
        "owner_user_id": int(current_user.get("id") or 0),
        "include_all_for_admin": is_admin_user(current_user),
    }


def require(resource: T | None, detail: str = "Resource not found.") -> T:
    """Raise a 404 when a resource is missing."""
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return resource


def load_quote_or_404(quote_id: int, current_user: dict[str, Any]) -> dict[str, Any]:
    """Load a quote visible to the current user or raise 404."""
    return require(get_client_by_id(quote_id, **scope_kwargs(current_user)), "Quote not found.")


async def validate_pdf_upload(file: UploadFile) -> bytes:
    """Validate a PDF upload and return its bytes."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF uploads are supported.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    return file_bytes


def handle_doc_generation(
    func: Callable[..., T],
    *args: Any,
    failure_detail: str = "Document generation failed: {error}",
    not_found_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    **kwargs: Any,
) -> T:
    """Run a document generator and map common failures to HTTP errors."""
    try:
        return func(*args, **kwargs)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=not_found_status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=failure_detail.format(error=exc),
        ) from exc


def try_advance_pm_task(
    quote_ref: str,
    task_name: str,
    source: str,
    current_user: dict[str, Any],
) -> None:
    """Best-effort PM task auto-advance for quote-scoped workflows."""
    normalized_quote_ref = str(quote_ref or "").strip()
    if not normalized_quote_ref:
        return

    try:
        mark_project_task_done_for_quote(
            normalized_quote_ref,
            task_name,
            notes=f"Auto-advanced from {source}",
            owner_user_id=user_id(current_user),
            include_all_for_admin=is_admin_user(current_user),
        )
    except Exception as exc:  # pragma: no cover - defensive logging path
        print(
            f"Warning: failed to auto-advance PM task '{task_name}' "
            f"for quote_ref='{normalized_quote_ref}': {exc}"
        )
