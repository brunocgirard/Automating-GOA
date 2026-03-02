"""COR workflow API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from api.dependencies.auth import require_authenticated_user
from api.models.schemas import (
    CorGenerateRequest,
    CorLoadResponse,
    CorPrefillResponse,
    CorRevisionListResponse,
    CorSaveRequest,
    CorSaveResponse,
)
from api.routers._helpers import (
    handle_doc_generation,
    load_quote_or_404,
    require,
    scope_kwargs,
    try_advance_pm_task,
)
from api.services.cor_doc_service import build_cor_prefill_data, generate_cor_document
from src.utils.db import (
    list_cor_documents,
    load_machines_for_quote,
    load_cor_document,
    save_cor_document,
)

router = APIRouter(prefix="/api/cor", tags=["COR"])


def _prefill_state_for_quote(quote: dict[str, Any]) -> dict[str, Any]:
    return build_cor_prefill_data(quote)


def _contact_person_from_quote(quote: dict[str, Any]) -> str:
    return str(quote.get("company") or "").strip()


def _company_from_quote(quote: dict[str, Any]) -> str:
    return str(quote.get("customer_name") or quote.get("company") or "").strip()


def _extract_main_machine_names_for_quote(quote_ref: str, current_user: dict[str, Any]) -> list[str]:
    if not quote_ref:
        return []
    names: list[str] = []
    for machine in load_machines_for_quote(quote_ref, **scope_kwargs(current_user)):
        name = str(machine.get("machine_name") or "").strip()
        if not name:
            continue
        machine_data = machine.get("machine_data")
        machine_type = ""
        has_main_item = False
        if isinstance(machine_data, dict):
            machine_type = str(machine_data.get("machine_type") or "").strip().lower()
            has_main_item = isinstance(machine_data.get("main_item"), dict) and bool(machine_data.get("main_item"))
        is_main = machine_type == "main" or (not machine_type and has_main_item)
        if is_main and name not in names:
            names.append(name)
    return names


def _resolve_machine_for_cor(
    quote: dict[str, Any],
    requested_machine: str,
    quote_ref: str,
    current_user: dict[str, Any],
) -> str:
    options = _extract_main_machine_names_for_quote(quote_ref, current_user)
    requested = requested_machine.strip()
    if requested and requested in options:
        return requested
    if options:
        return options[0]
    return str(quote.get("machine_model") or requested).strip()


def _normalize_cor_client_info(
    cor_data: dict[str, Any],
    quote: dict[str, Any],
    quote_ref: str,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    raw_client = cor_data.get("client")
    client = raw_client if isinstance(raw_client, dict) else {}
    source = str(cor_data.get("initiatorOfChange") or "").strip().lower()
    if source not in {"contact_person", "capmatic_pm"}:
        source = "contact_person"
    machine = _resolve_machine_for_cor(
        quote=quote,
        requested_machine=str(client.get("machine") or ""),
        quote_ref=quote_ref,
        current_user=current_user,
    )
    cor_data["client"] = {
        "company": _company_from_quote(quote),
        "customerPO": str(quote.get("customer_po") or "").strip(),
        "orderDate": str(quote.get("order_date") or "").strip(),
        "ax": str(quote.get("ax") or "").strip(),
        "ox": str(quote.get("ox") or "").strip(),
        "machine": machine,
    }
    cor_data["initiatorOfChange"] = source
    cor_data["contactPerson"] = _contact_person_from_quote(quote)
    return cor_data


@router.get("/{quote_id}/prefill", response_model=CorPrefillResponse)
def get_cor_prefill(
    quote_id: int,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    quote = load_quote_or_404(quote_id, current_user)
    cor_data = _prefill_state_for_quote(quote)
    return {
        "quote_id": quote_id,
        "quote_ref": quote.get("quote_ref", ""),
        "cor_data": cor_data,
    }


@router.get("/{quote_id}/revisions", response_model=CorRevisionListResponse)
def list_cor_revisions(
    quote_id: int,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    quote = load_quote_or_404(quote_id, current_user)
    quote_ref = str(quote.get("quote_ref") or "")
    revisions = list_cor_documents(quote_ref)

    return {
        "quote_id": quote_id,
        "quote_ref": quote_ref,
        "revisions": [
            {
                "cor_document_id": int(entry.get("id") or 0),
                "cor_no": str(entry.get("cor_no") or ""),
                "description": str(entry.get("description") or ""),
                "created_date": entry.get("created_date"),
                "modified_date": entry.get("modified_date"),
            }
            for entry in revisions
            if int(entry.get("id") or 0) > 0
        ],
    }


@router.post("/{quote_id}/save", response_model=CorSaveResponse)
def save_cor_state(
    quote_id: int,
    payload: CorSaveRequest,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    quote = load_quote_or_404(quote_id, current_user)
    quote_ref = str(quote.get("quote_ref") or "")

    cor_data = dict(payload.cor_data or {})
    cor_data["quoteId"] = quote_id
    cor_data["quoteRef"] = quote_ref
    cor_data = _normalize_cor_client_info(cor_data, quote=quote, quote_ref=quote_ref, current_user=current_user)
    if payload.cor_no is not None:
        cor_data["corNo"] = payload.cor_no
    if payload.description is not None:
        cor_data["revisionDescription"] = payload.description

    saved_row = save_cor_document(
        quote_ref,
        cor_data,
        cor_document_id=payload.cor_document_id,
        create_new=payload.create_new,
        cor_no=payload.cor_no,
        description=payload.description,
    )
    if not saved_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save COR state.",
        )

    try_advance_pm_task(quote_ref, "COR Completion", "cor.save", current_user)

    return {
        "quote_id": quote_id,
        "quote_ref": quote_ref,
        "cor_document_id": int(saved_row.get("id") or 0),
        "cor_no": str(saved_row.get("cor_no") or ""),
        "description": str(saved_row.get("description") or ""),
        "saved_at": saved_row.get("modified_date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cor_data": saved_row.get("cor_data") or cor_data,
    }


@router.get("/{quote_id}/load", response_model=CorLoadResponse)
def load_cor_state(
    quote_id: int,
    cor_document_id: int | None = None,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    quote = load_quote_or_404(quote_id, current_user)
    quote_ref = str(quote.get("quote_ref") or "")

    saved_row = load_cor_document(quote_ref, cor_document_id=cor_document_id)
    detail = (
        "No saved COR state found."
        if cor_document_id is None
        else f"No saved COR state found for cor_document_id={cor_document_id}."
    )
    saved_row = require(saved_row, detail)

    cor_data = dict(saved_row.get("cor_data") or {})
    cor_data = _normalize_cor_client_info(cor_data, quote=quote, quote_ref=quote_ref, current_user=current_user)

    return {
        "quote_id": quote_id,
        "quote_ref": quote_ref,
        "cor_document_id": int(saved_row.get("id") or 0),
        "cor_no": str(saved_row.get("cor_no") or ""),
        "description": str(saved_row.get("description") or ""),
        "created_date": saved_row.get("created_date"),
        "modified_date": saved_row.get("modified_date"),
        "cor_data": cor_data,
    }


@router.post("/{quote_id}/generate")
def generate_cor_docs(
    quote_id: int,
    payload: CorGenerateRequest,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> FileResponse:
    quote = load_quote_or_404(quote_id, current_user)
    quote_ref = str(quote.get("quote_ref") or "")

    if payload.cor_data is not None:
        cor_data = dict(payload.cor_data)
        cor_data["quoteId"] = quote_id
        cor_data["quoteRef"] = quote_ref
        cor_data = _normalize_cor_client_info(cor_data, quote=quote, quote_ref=quote_ref, current_user=current_user)
        if payload.cor_document_id is not None:
            save_cor_document(
                quote_ref,
                cor_data,
                cor_document_id=payload.cor_document_id,
                create_new=False,
                cor_no=str(cor_data.get("corNo") or ""),
                description=str(cor_data.get("revisionDescription") or ""),
            )
    else:
        saved_row = load_cor_document(quote_ref, cor_document_id=payload.cor_document_id)
        if payload.cor_document_id is not None and not saved_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No saved COR state found for cor_document_id={payload.cor_document_id}.",
            )
        cor_data = dict(saved_row.get("cor_data") or {}) if saved_row else _prefill_state_for_quote(quote)
        cor_data = _normalize_cor_client_info(cor_data, quote=quote, quote_ref=quote_ref, current_user=current_user)

    artifact = handle_doc_generation(
        generate_cor_document,
        cor_data=cor_data,
        quote_ref=quote_ref,
        failure_detail="Failed to generate COR document: {error}",
    )

    return FileResponse(
        path=str(artifact.path),
        media_type=artifact.media_type,
        filename=artifact.filename,
    )
