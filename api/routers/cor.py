"""COR workflow API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from api.models.schemas import (
    CorGenerateRequest,
    CorLoadResponse,
    CorPrefillResponse,
    CorSaveRequest,
    CorSaveResponse,
)
from api.services.cor_doc_service import build_cor_prefill_data, generate_cor_document
from src.utils.db import (
    get_client_by_id,
    load_cor_document,
    save_cor_document,
)

router = APIRouter(prefix="/api/cor", tags=["COR"])


def _load_quote_or_404(quote_id: int) -> dict[str, Any]:
    quote = get_client_by_id(quote_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return quote


def _prefill_state_for_quote(quote: dict[str, Any]) -> dict[str, Any]:
    return build_cor_prefill_data(quote)


@router.get("/{quote_id}/prefill", response_model=CorPrefillResponse)
def get_cor_prefill(quote_id: int) -> dict[str, Any]:
    quote = _load_quote_or_404(quote_id)
    cor_data = _prefill_state_for_quote(quote)
    return {
        "quote_id": quote_id,
        "quote_ref": quote.get("quote_ref", ""),
        "cor_data": cor_data,
    }


@router.post("/{quote_id}/save", response_model=CorSaveResponse)
def save_cor_state(quote_id: int, payload: CorSaveRequest) -> dict[str, Any]:
    quote = _load_quote_or_404(quote_id)
    quote_ref = str(quote.get("quote_ref") or "")

    cor_data = dict(payload.cor_data or {})
    cor_data["quoteId"] = quote_id
    cor_data["quoteRef"] = quote_ref

    saved_row = save_cor_document(quote_ref, cor_data)
    if not saved_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save COR state.",
        )

    return {
        "quote_id": quote_id,
        "quote_ref": quote_ref,
        "saved_at": saved_row.get("modified_date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cor_data": saved_row.get("cor_data") or cor_data,
    }


@router.get("/{quote_id}/load", response_model=CorLoadResponse)
def load_cor_state(quote_id: int) -> dict[str, Any]:
    quote = _load_quote_or_404(quote_id)
    quote_ref = str(quote.get("quote_ref") or "")

    saved_row = load_cor_document(quote_ref)
    if not saved_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No saved COR state found.")

    return {
        "quote_id": quote_id,
        "quote_ref": quote_ref,
        "created_date": saved_row.get("created_date"),
        "modified_date": saved_row.get("modified_date"),
        "cor_data": saved_row.get("cor_data") or {},
    }


@router.post("/{quote_id}/generate")
def generate_cor_docs(quote_id: int, payload: CorGenerateRequest) -> FileResponse:
    quote = _load_quote_or_404(quote_id)
    quote_ref = str(quote.get("quote_ref") or "")

    if payload.cor_data is not None:
        cor_data = dict(payload.cor_data)
        cor_data["quoteId"] = quote_id
        cor_data["quoteRef"] = quote_ref
        save_cor_document(quote_ref, cor_data)
    else:
        saved_row = load_cor_document(quote_ref)
        cor_data = (
            dict(saved_row.get("cor_data") or {})
            if saved_row
            else _prefill_state_for_quote(quote)
        )

    try:
        artifact = generate_cor_document(
            cor_data=cor_data,
            quote_ref=quote_ref,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate COR document: {exc}",
        ) from exc

    return FileResponse(
        path=str(artifact.path),
        media_type=artifact.media_type,
        filename=artifact.filename,
    )
