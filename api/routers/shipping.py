"""Shipping workflow API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from api.models.schemas import (
    ShippingGenerateRequest,
    ShippingLoadResponse,
    ShippingPrefillResponse,
    ShippingSaveRequest,
    ShippingSaveResponse,
)
from api.services.shipping_doc_service import build_shipping_prefill_data, generate_shipping_documents
from src.utils.db import (
    get_client_by_id,
    load_machines_for_quote,
    load_priced_items_for_quote,
    load_shipping_document,
    mark_project_task_done_for_quote,
    save_shipping_document,
)

router = APIRouter(prefix="/api/shipping", tags=["Shipping"])


def _load_quote_or_404(quote_id: int) -> dict[str, Any]:
    quote = get_client_by_id(quote_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return quote


def _prefill_state_for_quote(quote: dict[str, Any]) -> dict[str, Any]:
    quote_ref = str(quote.get("quote_ref") or "")
    machine_rows = load_machines_for_quote(quote_ref) if quote_ref else []
    line_item_rows = load_priced_items_for_quote(quote_ref) if quote_ref else []
    return build_shipping_prefill_data(quote, machine_rows, line_item_rows)


def _merge_line_item_options(
    shipping_data: dict[str, Any],
    prefill_data: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(shipping_data) if isinstance(shipping_data, dict) else {}
    line_item_options = prefill_data.get("lineItemOptions")
    if isinstance(line_item_options, list):
        merged["lineItemOptions"] = line_item_options
    return merged


@router.get("/{quote_id}/prefill", response_model=ShippingPrefillResponse)
def get_shipping_prefill(quote_id: int) -> dict[str, Any]:
    quote = _load_quote_or_404(quote_id)
    shipping_data = _prefill_state_for_quote(quote)
    return {
        "quote_id": quote_id,
        "quote_ref": quote.get("quote_ref", ""),
        "shipping_data": shipping_data,
    }


@router.post("/{quote_id}/save", response_model=ShippingSaveResponse)
def save_shipping_state(quote_id: int, payload: ShippingSaveRequest) -> dict[str, Any]:
    quote = _load_quote_or_404(quote_id)
    quote_ref = str(quote.get("quote_ref") or "")
    prefill_data = _prefill_state_for_quote(quote)

    shipping_data = dict(payload.shipping_data or {})
    shipping_data["quoteId"] = quote_id
    shipping_data["quoteRef"] = quote_ref
    shipping_data = _merge_line_item_options(shipping_data, prefill_data)

    saved_row = save_shipping_document(quote_ref, shipping_data)
    if not saved_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save shipping state.",
        )

    return {
        "quote_id": quote_id,
        "quote_ref": quote_ref,
        "saved_at": saved_row.get("modified_date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "shipping_data": _merge_line_item_options(saved_row.get("shipping_data") or shipping_data, prefill_data),
    }


@router.get("/{quote_id}/load", response_model=ShippingLoadResponse)
def load_shipping_state(quote_id: int) -> dict[str, Any]:
    quote = _load_quote_or_404(quote_id)
    quote_ref = str(quote.get("quote_ref") or "")
    prefill_data = _prefill_state_for_quote(quote)

    saved_row = load_shipping_document(quote_ref)
    if not saved_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No saved shipping state found.")

    return {
        "quote_id": quote_id,
        "quote_ref": quote_ref,
        "created_date": saved_row.get("created_date"),
        "modified_date": saved_row.get("modified_date"),
        "shipping_data": _merge_line_item_options(saved_row.get("shipping_data") or {}, prefill_data),
    }


@router.post("/{quote_id}/generate")
def generate_shipping_docs(quote_id: int, payload: ShippingGenerateRequest) -> FileResponse:
    quote = _load_quote_or_404(quote_id)
    quote_ref = str(quote.get("quote_ref") or "")

    if payload.shipping_data is not None:
        shipping_data = dict(payload.shipping_data)
        shipping_data["quoteId"] = quote_id
        shipping_data["quoteRef"] = quote_ref
        save_shipping_document(quote_ref, shipping_data)
    else:
        saved_row = load_shipping_document(quote_ref)
        shipping_data = (
            dict(saved_row.get("shipping_data") or {})
            if saved_row
            else _prefill_state_for_quote(quote)
        )

    try:
        artifact = generate_shipping_documents(
            shipping_data=shipping_data,
            quote_ref=quote_ref,
            document_type=payload.document_type,
            output_format=payload.output_format,
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
            detail=f"Failed to generate shipping document(s): {exc}",
        ) from exc

    try:
        mark_project_task_done_for_quote(
            quote_ref,
            "Crating",
            notes="Auto-advanced from shipping.generate",
        )
    except Exception as exc:
        print(
            "Warning: failed to auto-advance PM task 'Crating' "
            f"for quote_ref='{quote_ref}': {exc}"
        )

    return FileResponse(
        path=str(artifact.path),
        media_type=artifact.media_type,
        filename=artifact.filename,
    )
