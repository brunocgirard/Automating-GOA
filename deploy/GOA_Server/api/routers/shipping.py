"""Shipping workflow API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from api.dependencies.auth import require_authenticated_user
from api.models.schemas import (
    ShippingGenerateRequest,
    ShippingLoadResponse,
    ShippingPrefillResponse,
    ShippingSaveRequest,
    ShippingSaveResponse,
)
from api.routers._helpers import (
    handle_doc_generation,
    load_quote_or_404,
    require,
    scope_kwargs,
    try_advance_pm_task,
)
from api.services.shipping_doc_service import build_shipping_prefill_data, generate_shipping_documents
from src.utils.db import (
    load_machines_for_quote,
    load_priced_items_for_quote,
    load_shipping_document,
    save_shipping_document,
)

router = APIRouter(prefix="/api/shipping", tags=["Shipping"])


def _prefill_state_for_quote(quote: dict[str, Any], current_user: dict[str, Any]) -> dict[str, Any]:
    quote_ref = str(quote.get("quote_ref") or "")
    machine_rows = load_machines_for_quote(quote_ref, **scope_kwargs(current_user)) if quote_ref else []
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
def get_shipping_prefill(
    quote_id: int,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    quote = load_quote_or_404(quote_id, current_user)
    shipping_data = _prefill_state_for_quote(quote, current_user)
    return {
        "quote_id": quote_id,
        "quote_ref": quote.get("quote_ref", ""),
        "shipping_data": shipping_data,
    }


@router.post("/{quote_id}/save", response_model=ShippingSaveResponse)
def save_shipping_state(
    quote_id: int,
    payload: ShippingSaveRequest,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    quote = load_quote_or_404(quote_id, current_user)
    quote_ref = str(quote.get("quote_ref") or "")
    prefill_data = _prefill_state_for_quote(quote, current_user)

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
def load_shipping_state(
    quote_id: int,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    quote = load_quote_or_404(quote_id, current_user)
    quote_ref = str(quote.get("quote_ref") or "")
    prefill_data = _prefill_state_for_quote(quote, current_user)

    saved_row = require(load_shipping_document(quote_ref), "No saved shipping state found.")

    return {
        "quote_id": quote_id,
        "quote_ref": quote_ref,
        "created_date": saved_row.get("created_date"),
        "modified_date": saved_row.get("modified_date"),
        "shipping_data": _merge_line_item_options(saved_row.get("shipping_data") or {}, prefill_data),
    }


@router.post("/{quote_id}/generate")
def generate_shipping_docs(
    quote_id: int,
    payload: ShippingGenerateRequest,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> FileResponse:
    quote = load_quote_or_404(quote_id, current_user)
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
            else _prefill_state_for_quote(quote, current_user)
        )

    artifact = handle_doc_generation(
        generate_shipping_documents,
        shipping_data=shipping_data,
        quote_ref=quote_ref,
        document_type=payload.document_type,
        output_format=payload.output_format,
        failure_detail="Failed to generate shipping document(s): {error}",
    )

    try_advance_pm_task(quote_ref, "Crating", "shipping.generate", current_user)

    return FileResponse(
        path=str(artifact.path),
        media_type=artifact.media_type,
        filename=artifact.filename,
    )
