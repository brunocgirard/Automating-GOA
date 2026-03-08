"""Quote and client CRUD router."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.dependencies.auth import is_admin_user, require_authenticated_user
from api.models.schemas import QuoteResponse, QuoteUpdateRequest, QuoteUploadResponse
from api.routers._helpers import load_quote_or_404, scope_kwargs, user_id, validate_pdf_upload
from api.services.processing_service import extract_and_catalog
from src.utils.db import (
    delete_client_record,
    ensure_project_for_quote,
    get_client_by_id,
    load_all_clients,
    update_client_record,
)

router = APIRouter(prefix="/api/quotes", tags=["Quotes"])


@router.get("", response_model=list[QuoteResponse])
def list_quotes(current_user: dict = Depends(require_authenticated_user)) -> list[dict]:
    return load_all_clients(**scope_kwargs(current_user))


@router.get("/{quote_id}", response_model=QuoteResponse)
def get_quote(quote_id: int, current_user: dict = Depends(require_authenticated_user)) -> dict:
    return load_quote_or_404(quote_id, current_user)


@router.put("/{quote_id}", response_model=QuoteResponse)
def update_quote(
    quote_id: int,
    payload: QuoteUpdateRequest,
    current_user: dict = Depends(require_authenticated_user),
) -> dict:
    load_quote_or_404(quote_id, current_user)

    update_payload = payload.model_dump(exclude_none=True)
    if not update_client_record(quote_id, update_payload, **scope_kwargs(current_user)):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update quote record.",
        )

    updated = get_client_by_id(quote_id, **scope_kwargs(current_user))
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quote update succeeded but record could not be reloaded.",
        )
    return updated


@router.delete("/{quote_id}")
def delete_quote(
    quote_id: int,
    current_user: dict = Depends(require_authenticated_user),
) -> dict[str, bool | int]:
    load_quote_or_404(quote_id, current_user)

    if not delete_client_record(quote_id, **scope_kwargs(current_user)):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete quote.",
        )
    return {"deleted": True, "id": quote_id}


@router.post("/upload", response_model=QuoteUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_quote_pdf(
    file: UploadFile = File(...),
    existing_client_id: int | None = Form(default=None),
    current_user: dict = Depends(require_authenticated_user),
) -> dict:
    file_bytes = await validate_pdf_upload(file)

    try:
        result = extract_and_catalog(
            file_bytes,
            file.filename,
            existing_client_id,
            owner_user_id=user_id(current_user),
            include_all_for_admin=is_admin_user(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract and catalog PDF: {exc}",
        ) from exc

    # Optional PM integration: create a linked PM project automatically for new uploads.
    try:
        quote_ref = str(result.get("quote_ref") or "").strip()
        customer_name = str(result.get("customer_name") or "").strip() or quote_ref
        machine_model = str(result.get("machine_model") or "").strip()
        if quote_ref:
            ensure_project_for_quote(
                quote_ref=quote_ref,
                customer_name=customer_name,
                machine_summary=machine_model or None,
                project_name=f"{customer_name} - {machine_model}" if machine_model else quote_ref,
                start_date=datetime.now().strftime("%Y-%m-%d"),
                owner_user_id=user_id(current_user),
                include_all_for_admin=is_admin_user(current_user),
            )
    except Exception as exc:
        print(
            "Warning: quote upload succeeded but PM project auto-create failed "
            f"for quote_ref='{result.get('quote_ref')}': {exc}"
        )

    return {
        "quote_ref": result["quote_ref"],
        "items_count": result["items_count"],
        "linked_existing_client_id": result.get("linked_existing_client_id"),
    }
