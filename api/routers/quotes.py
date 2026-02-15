"""Quote and client CRUD router."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from api.models.schemas import QuoteResponse, QuoteUpdateRequest, QuoteUploadResponse
from api.services.processing_service import extract_and_catalog
from src.utils.db import delete_client_record, get_client_by_id, load_all_clients, update_client_record

router = APIRouter(prefix="/api/quotes", tags=["Quotes"])


@router.get("", response_model=list[QuoteResponse])
def list_quotes() -> list[dict]:
    return load_all_clients()


@router.get("/{quote_id}", response_model=QuoteResponse)
def get_quote(quote_id: int) -> dict:
    quote = get_client_by_id(quote_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return quote


@router.put("/{quote_id}", response_model=QuoteResponse)
def update_quote(quote_id: int, payload: QuoteUpdateRequest) -> dict:
    existing = get_client_by_id(quote_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")

    update_payload = payload.model_dump(exclude_none=True)
    if not update_client_record(quote_id, update_payload):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update quote record.",
        )

    updated = get_client_by_id(quote_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quote update succeeded but record could not be reloaded.",
        )
    return updated


@router.delete("/{quote_id}")
def delete_quote(quote_id: int) -> dict[str, bool | int]:
    existing = get_client_by_id(quote_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")

    if not delete_client_record(quote_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete quote.",
        )
    return {"deleted": True, "id": quote_id}


@router.post("/upload", response_model=QuoteUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_quote_pdf(
    file: UploadFile = File(...),
    existing_client_id: int | None = Form(default=None),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF uploads are supported.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    try:
        result = extract_and_catalog(file_bytes, file.filename, existing_client_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract and catalog PDF: {exc}",
        ) from exc

    return {
        "quote_ref": result["quote_ref"],
        "items_count": result["items_count"],
        "linked_existing_client_id": result.get("linked_existing_client_id"),
    }

